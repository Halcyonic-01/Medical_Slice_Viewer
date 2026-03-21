"""
synthetic.py
------------
Generate synthetic 3-D volumes for testing and demos.

No real patient data required – useful for CI pipelines and quick demos.
"""

from __future__ import annotations

import numpy as np

from src.core.volume import Volume, VolumeMetadata


def make_sphere_volume(
    shape: tuple = (64, 64, 64),
    spacing: tuple = (2.0, 2.0, 2.0),
    radius_frac: float = 0.3,
    inner_value: float = 200.0,
    outer_value: float = -1000.0,
) -> Volume:
    """
    Create a Volume containing a solid sphere (CT-like HU values).

    Parameters
    ----------
    shape        : (I, J, K) voxel dimensions.
    spacing      : Voxel size in mm.
    radius_frac  : Sphere radius as a fraction of the smallest dimension.
    inner_value  : Intensity inside the sphere (default: soft tissue ~200 HU).
    outer_value  : Intensity outside the sphere (default: air ~-1000 HU).
    """
    ni, nj, nk = shape
    ci, cj, ck = ni / 2, nj / 2, nk / 2
    si, sj, sk = spacing

    radius = min(ni * si, nj * sj, nk * sk) * radius_frac

    iz, jz, kz = np.ogrid[:ni, :nj, :nk]
    dist = np.sqrt(
        ((iz - ci) * si) ** 2 + ((jz - cj) * sj) ** 2 + ((kz - ck) * sk) ** 2
    )
    data = np.where(dist <= radius, inner_value, outer_value).astype(np.float32)

    affine = np.diag([si, sj, sk, 1.0])
    metadata = VolumeMetadata(source_path="synthetic:sphere", modality="CT")
    return Volume(data=data, spacing=spacing, affine=affine, metadata=metadata)


def make_gradient_volume(
    shape: tuple = (64, 64, 64),
    spacing: tuple = (1.0, 1.0, 1.0),
) -> Volume:
    """
    Create a Volume with a simple intensity gradient along the K axis.
    Useful for testing window/level and slice navigation.
    """
    ni, nj, nk = shape
    data = np.linspace(0, 1000, nk, dtype=np.float32)[np.newaxis, np.newaxis, :]
    data = np.broadcast_to(data, shape).copy()

    affine = np.diag([*spacing, 1.0])
    metadata = VolumeMetadata(source_path="synthetic:gradient", modality="MR")
    return Volume(data=data, spacing=spacing, affine=affine, metadata=metadata)