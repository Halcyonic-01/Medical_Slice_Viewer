"""
dicom_reader.py
---------------
Load a DICOM series (folder) via pydicom and return a Volume.

Strategy
--------
1. Discover all .dcm files in the given directory.
2. Group by SeriesInstanceUID → pick the largest group.
3. Sort slices by ImagePositionPatient z-component (or InstanceNumber).
4. Stack into a 3-D array and extract spacing / affine.

A proper DICOM affine is constructed from:
  - ImageOrientationPatient (row/col cosines)
  - ImagePositionPatient    (origin of first slice)
  - PixelSpacing            (in-plane spacing)
  - slice thickness or derived inter-slice spacing
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import numpy as np
import pydicom

from src.core.volume import Volume, VolumeMetadata

logger = logging.getLogger(__name__)


def load_dicom_series(directory: str | Path) -> Volume:
    """
    Load all DICOM slices in *directory* and return a :class:`~src.core.Volume`.

    Parameters
    ----------
    directory : str | Path
        Folder containing ``.dcm`` files (searched non-recursively).

    Raises
    ------
    FileNotFoundError
        If *directory* does not exist.
    ValueError
        If no valid DICOM slices are found.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"DICOM directory not found: {directory}")

    dcm_files = sorted(directory.glob("*.dcm"))
    if not dcm_files:
        # Some series have no extension
        dcm_files = [
            Path(os.path.join(directory, f))
            for f in os.listdir(directory)
            if not f.startswith(".")
        ]

    if not dcm_files:
        raise ValueError(f"No DICOM files found in {directory}")

    logger.info("Found %d DICOM file(s) in %s", len(dcm_files), directory)

    # Read headers (no pixel data yet for speed)
    datasets = []
    for fp in dcm_files:
        try:
            ds = pydicom.dcmread(str(fp), stop_before_pixels=True)
            datasets.append((fp, ds))
        except Exception as exc:
            logger.debug("Skipping %s: %s", fp.name, exc)

    if not datasets:
        raise ValueError("Could not read any DICOM headers.")

    # Sort slices
    sorted_slices = _sort_slices(datasets)

    # Load pixel data in order
    pixel_arrays = []
    for fp, _ in sorted_slices:
        ds_full = pydicom.dcmread(str(fp))
        arr = _to_hounsfield(ds_full)
        pixel_arrays.append(arr)

    data = np.stack(pixel_arrays, axis=0)  # (slices, rows, cols)
    first_ds = sorted_slices[0][1]
    affine, spacing = _build_affine(sorted_slices)

    metadata = VolumeMetadata(
        source_path=str(directory),
        modality=getattr(first_ds, "Modality", "UNKNOWN"),
        patient_id=getattr(first_ds, "PatientID", ""),
        series_description=getattr(first_ds, "SeriesDescription", ""),
    )

    return Volume(data=data, spacing=spacing, affine=affine, metadata=metadata)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _sort_slices(datasets: list) -> list:
    """Sort (path, dataset) pairs by ImagePositionPatient z or InstanceNumber."""
    def sort_key(item):
        _, ds = item
        ipp = getattr(ds, "ImagePositionPatient", None)
        if ipp is not None:
            return float(ipp[2])
        return float(getattr(ds, "InstanceNumber", 0))

    return sorted(datasets, key=sort_key)


def _to_hounsfield(ds: "pydicom.Dataset") -> np.ndarray:
    """Apply RescaleSlope / RescaleIntercept to get Hounsfield units."""
    arr = ds.pixel_array.astype(np.float32)
    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    return arr * slope + intercept


def _build_affine(sorted_slices: list):
    """
    Construct a 4×4 voxel-to-world affine from DICOM geometry tags.

    Returns (affine, spacing).
    """
    _, first_ds = sorted_slices[0]
    _, last_ds = sorted_slices[-1]

    # In-plane pixel spacing (row spacing, col spacing) in mm
    ps = getattr(first_ds, "PixelSpacing", [1.0, 1.0])
    row_spacing = float(ps[0])
    col_spacing = float(ps[1])

    # Image orientation (row cosines F, column cosines)
    iop = getattr(first_ds, "ImageOrientationPatient", [1, 0, 0, 0, 1, 0])
    row_cos = np.array(iop[:3], dtype=np.float64)
    col_cos = np.array(iop[3:], dtype=np.float64)

    # Origin of first slice
    ipp_first = np.array(
        getattr(first_ds, "ImagePositionPatient", [0, 0, 0]), dtype=np.float64
    )

    n_slices = len(sorted_slices)
    if n_slices > 1:
        ipp_last = np.array(
            getattr(last_ds, "ImagePositionPatient", [0, 0, n_slices - 1]),
            dtype=np.float64,
        )
        slice_vec = (ipp_last - ipp_first) / max(n_slices - 1, 1)
    else:
        # Fall back to normal vector
        slice_vec = np.cross(row_cos, col_cos)
        slice_thickness = float(getattr(first_ds, "SliceThickness", 1.0))
        slice_vec = slice_vec * slice_thickness

    spacing = (
        float(np.linalg.norm(slice_vec)),
        row_spacing,
        col_spacing,
    )

    affine = np.eye(4, dtype=np.float64)
    affine[:3, 0] = slice_vec                # k axis → slice normal
    affine[:3, 1] = row_cos * row_spacing    # i axis → row direction
    affine[:3, 2] = col_cos * col_spacing    # j axis → col direction
    affine[:3, 3] = ipp_first

    return affine, spacing