"""
volume.py
---------
Central data model for a loaded medical volume.

Stores the raw numpy array, voxel spacing, affine transform, and
metadata.  All coordinate conversions (voxel ↔ world ↔ display) live
here so that every other module can stay coordinate-system-agnostic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VolumeMetadata:
    """Arbitrary key-value metadata harvested from the file header."""
    source_path: str = ""
    modality: str = "UNKNOWN"
    patient_id: str = ""
    series_description: str = ""
    extra: dict = field(default_factory=dict)


class Volume:
    """
    Immutable after construction.  Contains the 3-D array plus geometry.

    Parameters
    ----------
    data : np.ndarray
        Shape (I, J, K) in RAS+ orientation (rows=R, cols=A, slices=S).
        Callers must reorient before construction.
    spacing : tuple[float, float, float]
        Voxel size in mm along axes (i, j, k).
    affine : np.ndarray
        4×4 voxel-to-world affine matrix (world = RAS mm).
    metadata : VolumeMetadata
    """

    def __init__(
        self,
        data: np.ndarray,
        spacing: Tuple[float, float, float],
        affine: np.ndarray,
        metadata: Optional[VolumeMetadata] = None,
    ) -> None:
        if data.ndim != 3:
            raise ValueError(f"Expected 3-D array, got shape {data.shape}")
        self._data = data.astype(np.float32)
        self._spacing = tuple(float(s) for s in spacing)
        self._affine = np.asarray(affine, dtype=np.float64)
        self._inv_affine = np.linalg.inv(self._affine)
        self.metadata = metadata or VolumeMetadata()

        # Pre-compute window/level defaults from percentile statistics
        flat = self._data.ravel()
        self._data_min = float(flat.min())
        self._data_max = float(flat.max())
        p2, p98 = np.percentile(flat, [2, 98])
        self.default_window = float(p98 - p2)
        self.default_level = float((p98 + p2) / 2)

        logger.info(
            "Volume loaded: shape=%s spacing=%s W/L=%.0f/%.0f",
            data.shape, spacing, self.default_window, self.default_level,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def data(self) -> np.ndarray:
        return self._data

    @property
    def shape(self) -> Tuple[int, int, int]:
        return self._data.shape  # type: ignore[return-value]

    @property
    def spacing(self) -> Tuple[float, float, float]:
        return self._spacing  # type: ignore[return-value]

    @property
    def affine(self) -> np.ndarray:
        return self._affine

    @property
    def data_range(self) -> Tuple[float, float]:
        return self._data_min, self._data_max

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def voxel_to_world(self, ijk: np.ndarray) -> np.ndarray:
        """Map voxel indices (I, J, K) → RAS world coordinates (mm)."""
        ijk = np.asarray(ijk, dtype=np.float64)
        homo = np.append(ijk, 1.0)
        return (self._affine @ homo)[:3]

    def world_to_voxel(self, xyz: np.ndarray) -> np.ndarray:
        """Map world coordinates (mm) → voxel indices (float)."""
        xyz = np.asarray(xyz, dtype=np.float64)
        homo = np.append(xyz, 1.0)
        return (self._inv_affine @ homo)[:3]

    # ------------------------------------------------------------------
    # Slice extraction
    # ------------------------------------------------------------------

    def get_slice(self, axis: int, index: int) -> np.ndarray:
        """
        Return a 2-D slice along *axis* at *index*.

        axis=0 → axial (I plane), axis=1 → coronal, axis=2 → sagittal.
        """
        if axis == 0:
            return self._data[index, :, :]
        if axis == 1:
            return self._data[:, index, :]
        if axis == 2:
            return self._data[:, :, index]
        raise ValueError(f"axis must be 0, 1 or 2; got {axis}")

    def center_indices(self) -> Tuple[int, int, int]:
        """Return the voxel indices of the volume centre."""
        return tuple(s // 2 for s in self.shape)  # type: ignore[return-value]