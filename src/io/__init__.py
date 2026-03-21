"""
src.io – file format readers.

Public API
----------
load_volume(path) → Volume
    Auto-detect whether path is a NIfTI file or a DICOM directory
    and delegate to the appropriate reader.
"""

from __future__ import annotations

from pathlib import Path

from src.core.volume import Volume
from .dicom_reader import load_dicom_series
from .nifti_reader import load_nifti

__all__ = ["load_volume", "load_nifti", "load_dicom_series"]


def load_volume(path: str | Path) -> Volume:
    """
    Load a medical image from *path*.

    Supported formats
    -----------------
    * NIfTI  : ``.nii`` or ``.nii.gz`` file
    * DICOM  : directory containing ``.dcm`` files

    Raises
    ------
    ValueError
        If the format cannot be determined.
    """
    path = Path(path)

    if path.is_dir():
        return load_dicom_series(path)

    suffix = "".join(path.suffixes).lower()
    if suffix in (".nii", ".nii.gz"):
        return load_nifti(path)

    raise ValueError(
        f"Cannot determine format for '{path}'. "
        "Provide a .nii/.nii.gz file or a DICOM directory."
    )