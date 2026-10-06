from __future__ import annotations

import warnings

import numpy as np


def reduce(F: np.ndarray, axis: int, dv: float) -> np.ndarray:
    all_nan = np.all(np.isnan(F), axis=axis)
    z = np.nansum(F, axis=axis) * dv
    z[all_nan] = np.nan
    return z


def slice_(F: np.ndarray, axis: int, centres: np.ndarray, halfwidth: float, centre: float = 0.0) -> np.ndarray:
    """Mean of the layer |v - centre| <= halfwidth along `axis`; thinner than a cell -> nearest cell(s)."""
    a = np.abs(np.asarray(centres, float) - centre)
    sel = a <= halfwidth
    if not sel.any():
        sel = np.isclose(a, a.min())
    sub = np.compress(sel, F, axis=axis)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns -> NaN, expected
        return np.nanmean(sub, axis=axis)


def contour_levels(z: np.ndarray, decades: float = 3.0, n: int = 5) -> list[float]:
    z = np.asarray(z, float)
    pos = z[np.isfinite(z) & (z > 0)]
    if pos.size == 0:
        return []
    top = float(np.log10(pos.max()))
    return [float(x) for x in np.logspace(top - decades, top, n)]
