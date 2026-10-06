import numpy as np
import pytest
from sciqlop_vdf.core.frames import field_aligned_basis, axis_labels, FIELD_ALIGNED, NATIVE
from sciqlop_vdf.model import VDFError


def _check_orthonormal(R):
    np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert np.linalg.det(R) == pytest.approx(1.0)


def test_field_aligned_basis_general():
    b = np.array([0.0, 0.0, 10.0]); v = np.array([300.0, -100.0, 50.0])
    R = field_aligned_basis(b, v)
    _check_orthonormal(R)
    np.testing.assert_allclose(R[0], [0, 0, 1])
    np.testing.assert_allclose(R[1], np.array([300, -100, 0]) / np.hypot(300, 100))
    assert R[1] @ v > 0


def test_field_aligned_degenerate_v_parallel_b():
    R = field_aligned_basis(np.array([1.0, 0, 0]), np.array([5.0, 0, 0]))
    _check_orthonormal(R)
    np.testing.assert_allclose(R[0], [1, 0, 0])


def test_field_aligned_without_v():
    R = field_aligned_basis(np.array([0.3, 0.4, 0.5]), None)
    _check_orthonormal(R)


def test_field_aligned_zero_b_raises():
    with pytest.raises(VDFError, match="B"):
        field_aligned_basis(np.zeros(3), np.ones(3))


def test_axis_labels():
    assert axis_labels(NATIVE, "DBCS") == ("vx DBCS", "vy DBCS", "vz DBCS")
    assert axis_labels("GSE", "DBCS") == ("vx GSE", "vy GSE", "vz GSE")
    assert axis_labels(FIELD_ALIGNED, "DBCS") == ("v∥", "v⊥1", "v⊥2")
