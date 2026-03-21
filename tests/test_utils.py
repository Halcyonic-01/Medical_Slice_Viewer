"""
test_utils.py
-------------
Tests for synthetic volume generators and the IO router.
"""

import pytest

from src.utils.synthetic import make_gradient_volume, make_sphere_volume
from src.core.volume import Volume


class TestSyntheticSphere:
    def test_shape(self):
        vol = make_sphere_volume(shape=(32, 32, 32))
        assert vol.shape == (32, 32, 32)

    def test_contains_two_intensity_levels(self):
        import numpy as np
        vol = make_sphere_volume(shape=(32, 32, 32))
        unique_vals = np.unique(vol.data)
        assert len(unique_vals) == 2

    def test_spacing_preserved(self):
        vol = make_sphere_volume(shape=(16, 16, 16), spacing=(2.0, 3.0, 4.0))
        assert vol.spacing == (2.0, 3.0, 4.0)

    def test_data_range(self):
        vol = make_sphere_volume(inner_value=200.0, outer_value=-1000.0)
        lo, hi = vol.data_range
        assert lo == pytest.approx(-1000.0, abs=1.0)
        assert hi == pytest.approx(200.0, abs=1.0)

    def test_center_is_sphere(self):
        import numpy as np
        vol = make_sphere_volume(shape=(32, 32, 32), inner_value=100.0, outer_value=0.0)
        ci, cj, ck = vol.center_indices()
        assert vol.data[ci, cj, ck] == pytest.approx(100.0)

    def test_returns_volume_instance(self):
        assert isinstance(make_sphere_volume(), Volume)


class TestSyntheticGradient:
    def test_shape(self):
        vol = make_gradient_volume(shape=(16, 16, 16))
        assert vol.shape == (16, 16, 16)

    def test_gradient_along_k(self):
        import numpy as np
        vol = make_gradient_volume(shape=(4, 4, 10))
        # Values along the K axis should be strictly increasing
        k_values = vol.data[0, 0, :]
        assert np.all(np.diff(k_values) > 0)

    def test_returns_volume_instance(self):
        assert isinstance(make_gradient_volume(), Volume)


class TestIORouter:
    def test_rejects_unknown_extension(self, tmp_path):
        from src.io import load_volume
        dummy = tmp_path / "file.xyz"
        dummy.write_text("data")
        with pytest.raises(ValueError, match="Cannot determine format"):
            load_volume(dummy)

    def test_missing_nifti_raises(self, tmp_path):
        from src.io import load_volume
        with pytest.raises(FileNotFoundError):
            load_volume(tmp_path / "nonexistent.nii")

    def test_missing_dicom_dir_raises(self, tmp_path):
        from src.io import load_volume
        with pytest.raises(FileNotFoundError):
            load_volume(tmp_path / "nonexistent_dir")