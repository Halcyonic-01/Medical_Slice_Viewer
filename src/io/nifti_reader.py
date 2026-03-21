"""
nifti_reader.py
---------------
Load NIfTI (.nii / .nii.gz) files via nibabel and return a Volume.

The loader:
  1. Reads the file with nibabel.
  2. Reorients to canonical RAS+ orientation (nibabel's as_closest_canonical).
  3. Extracts voxel spacing from the header pixdim field.
  4. Passes the affine and data array to Volume.
"""

from __future__ import annotations

import logging
from pathlib import Path

import nibabel as nib
import numpy as np

from src.core.volume import Volume, VolumeMetadata

logger = logging.getLogger(__name__)


def load_nifti(path: str | Path) -> Volume:
    """
    Load a NIfTI file and return a :class:`~src.core.Volume`.

    Parameters
    ----------
    path : str | Path
        Path to a ``.nii`` or ``.nii.gz`` file.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file cannot be loaded as a NIfTI image.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NIfTI file not found: {path}")

    logger.info("Loading NIfTI: %s", path)
    img = nib.load(str(path))

    # Reorient to RAS+ canonical orientation
    canonical = nib.as_closest_canonical(img)
    data: np.ndarray = canonical.get_fdata(dtype=np.float32)
    affine: np.ndarray = canonical.affine

    # Extract voxel spacing (zooms excludes time dim for 4-D; take first 3)
    zooms = canonical.header.get_zooms()[:3]
    spacing = tuple(float(z) for z in zooms)
    if len(spacing) < 3:
        spacing = spacing + (1.0,) * (3 - len(spacing))

    # Collapse 4-D to 3-D by taking the first volume
    if data.ndim == 4:
        logger.warning("4-D NIfTI detected; using first volume (index 0).")
        data = data[..., 0]

    metadata = VolumeMetadata(
        source_path=str(path),
        modality=_guess_modality(canonical.header),
    )

    return Volume(data=data, spacing=spacing, affine=affine, metadata=metadata)


def _guess_modality(header) -> str:
    """Attempt to read the dim_info / intent_code to name the modality."""
    try:
        # NIfTI intent code is stored as an integer; map common ones
        intent = int(header.get("intent_code", 0))
        intent_map = {0: "UNKNOWN", 2001: "fMRI", 2003: "DTI"}
        return intent_map.get(intent, "MRI")
    except Exception:
        return "UNKNOWN"