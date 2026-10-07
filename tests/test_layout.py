import numpy as np
import pytest
from sciqlop_vdf.ui.layout import (COLUMN, L, MIN_SIDE, ROW, SINGLE, arrangement, mask_outside, positions,
                                   shared_zrange, side)


@pytest.mark.parametrize("w,h,expected", [(900, 300, ROW), (300, 900, COLUMN), (600, 600, L)])
def test_arrangement_follows_aspect(w, h, expected):
    assert arrangement(w, h, extra_w=0) == expected


def test_side_fits_the_box():
    assert side(ROW, 900, 300, extra_w=0) == 300
    assert side(L, 600, 600, extra_w=0) == 300
    assert side(COLUMN, 300, 900, extra_w=0) == 300
    assert side(SINGLE, 500, 400, extra_w=0) == 400


def test_colorbar_width_is_reserved():
    assert side(ROW, 970, 400, extra_w=70) == 300


@pytest.mark.parametrize("w,h", [(0, 0), (-5, 10), (10, -5), (1, 1)])
def test_degenerate_sizes_never_break(w, h):
    arr = arrangement(w, h)
    assert arr in (ROW, COLUMN, L)
    assert side(arr, w, h) == MIN_SIDE


def test_positions():
    assert positions(ROW) == ((0, 0), (0, 1), (0, 2))
    assert positions(COLUMN) == ((0, 0), (1, 0), (2, 0))
    assert positions(L) == ((0, 0), (0, 1), (1, 0))
    assert positions(SINGLE) == ((0, 0),)


def test_shared_zrange_uses_the_max_over_all_planes():
    a = np.array([[1e-10, 1e-12], [np.nan, 0.0]])
    b = np.array([[1e-8, -1.0], [1e-9, np.nan]])
    assert shared_zrange([a, b, np.full((2, 2), np.nan)], decades=4) == pytest.approx((1e-12, 1e-8))


def test_shared_zrange_all_empty_is_none():
    assert shared_zrange([np.zeros((2, 2)), np.full((2, 2), np.nan)], decades=4) is None
    assert shared_zrange([], decades=4) is None


def test_mask_outside():
    z = np.array([[1e-13, 1e-10], [0.0, 1e-8]])
    out = mask_outside(z, (1e-12, 1e-8))
    assert np.isnan(out[0, 0]) and np.isnan(out[1, 0]) and out[0, 1] == 1e-10 and out[1, 1] == 1e-8
    assert np.isnan(mask_outside(z, None)).all()
    assert z[0, 0] == 1e-13  # input untouched
