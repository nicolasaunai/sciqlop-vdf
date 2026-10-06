import numpy as np
import pytest
from sciqlop_vdf.core.project import reduce, slice_, contour_levels


def test_reduce_sums_and_keeps_all_nan_columns_nan():
    F = np.ones((2, 2, 3)); F[1, 1, :] = np.nan; F[0, 0, 0] = np.nan
    z = reduce(F, axis=2, dv=2.0)
    assert z[0, 0] == pytest.approx(4.0) and z[0, 1] == pytest.approx(6.0)
    assert np.isnan(z[1, 1])


def test_slice_selects_central_cells():
    c = np.array([-1.5, -0.5, 0.5, 1.5])
    F = np.zeros((4, 4, 4)); F[:, :, 1] = 1.0; F[:, :, 2] = 3.0
    np.testing.assert_allclose(slice_(F, 2, c, 0.5), 2.0)
    np.testing.assert_allclose(slice_(F, 2, c, 0.1), 2.0)  # thinner than a cell -> central cells


def test_contour_levels():
    z = np.array([[1e-12, 1e-9], [0.0, np.nan]])
    np.testing.assert_allclose(contour_levels(z, decades=3, n=4), [1e-12, 1e-11, 1e-10, 1e-9])


def test_contour_levels_all_zero_or_nan():
    assert contour_levels(np.zeros((3, 3))) == []
    assert contour_levels(np.full((3, 3), np.nan)) == []


def test_slice_at_offset_centre():
    c = np.array([-1.5, -0.5, 0.5, 1.5])
    F = np.zeros((4, 4, 4)); F[:, :, 3] = 7.0; F[:, :, 2] = 1.0
    np.testing.assert_allclose(slice_(F, 2, c, 0.1, centre=1.5), 7.0)   # exactly one cell
    np.testing.assert_allclose(slice_(F, 2, c, 0.5, centre=1.0), 4.0)   # two cells around 1.0
    np.testing.assert_allclose(slice_(F, 2, c, 0.1, centre=1.2), 7.0)   # thinner than a cell -> nearest
