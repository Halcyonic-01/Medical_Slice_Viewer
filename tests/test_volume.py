"""
test_volume.py
--------------
Unit tests for src.core.volume.Volume.

These tests are pure numpy – no VTK or Qt required.
"""

import numpy as np
import pytest

from src.core.volume import Volume, VolumeMetadata


@pytest.fixture()
def simple_volume() -> Volume:
    """64x64x64 identity-spaced volume with a ramp."""
    data = np.arange(64 ** 3, dtype=np.float32).reshape(64, 64, 64)
    affine = np.eye(4)
    return Volume(data=data, spacing=(1.0, 1.0, 1.0), affine=affine)


class TestVolumeConstruction:
    def test_shape(self, simple_volume):
        assert simple_volume.shape == (64, 64, 64)

    def test_spacing(self, simple_volume):
        assert simple_volume.spacing == (1.0, 1.0, 1.0)

    def test_rejects_2d_input(self):
        with pytest.raises(ValueError, match="3-D"):
            Volume(data=np.zeros((10, 10)), spacing=(1, 1, 1), affine=np.eye(4))

    def test_data_dtype_is_float32(self, simple_volume):
        assert simple_volume.data.dtype == np.float32


class TestSliceExtraction:
    def test_axial_slice_shape(self, simple_volume):
        slc = simple_volume.get_slice(axis=0, index=10)
        assert slc.shape == (64, 64)

    def test_coronal_slice_shape(self, simple_volume):
        slc = simple_volume.get_slice(axis=1, index=10)
        assert slc.shape == (64, 64)

    def test_sagittal_slice_shape(self, simple_volume):
        slc = simple_volume.get_slice(axis=2, index=10)
        assert slc.shape == (64, 64)

    def test_invalid_axis(self, simple_volume):
        with pytest.raises(ValueError):
            simple_volume.get_slice(axis=3, index=0)


class TestCoordinateTransforms:
    def test_voxel_to_world_identity(self, simple_volume):
        world = simple_volume.voxel_to_world(np.array([1.0, 2.0, 3.0]))
        np.testing.assert_allclose(world, [1.0, 2.0, 3.0], atol=1e-6)

    def test_world_to_voxel_identity(self, simple_volume):
        voxel = simple_volume.world_to_voxel(np.array([5.0, 10.0, 15.0]))
        np.testing.assert_allclose(voxel, [5.0, 10.0, 15.0], atol=1e-6)

    def test_round_trip(self, simple_volume):
        ijk = np.array([7.0, 13.0, 31.0])
        world = simple_volume.voxel_to_world(ijk)
        ijk2 = simple_volume.world_to_voxel(world)
        np.testing.assert_allclose(ijk, ijk2, atol=1e-5)

    def test_anisotropic_spacing(self):
        data = np.zeros((10, 10, 10), dtype=np.float32)
        affine = np.diag([2.0, 3.0, 4.0, 1.0])
        vol = Volume(data=data, spacing=(2.0, 3.0, 4.0), affine=affine)
        world = vol.voxel_to_world(np.array([1.0, 1.0, 1.0]))
        np.testing.assert_allclose(world, [2.0, 3.0, 4.0], atol=1e-6)


class TestCenterIndices:
    def test_center_is_half_shape(self, simple_volume):
        ci, cj, ck = simple_volume.center_indices()
        assert ci == 32
        assert cj == 32
        assert ck == 32


class TestDataRange:
    def test_data_range(self, simple_volume):
        lo, hi = simple_volume.data_range
        assert lo == pytest.approx(0.0, abs=1.0)
        assert hi == pytest.approx(64 ** 3 - 1, rel=0.01)


class TestWindowLevel:
    def test_defaults_are_set(self, simple_volume):
        assert simple_volume.default_window > 0
        # Level should be within the data range
        lo, hi = simple_volume.data_range
        assert lo <= simple_volume.default_level <= hi