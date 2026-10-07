"""Qt-free geometry of the three VDF planes and their shared colour range (unit-tested)."""
from __future__ import annotations

import numpy as np

ROW, COLUMN, L, SINGLE = "row", "column", "L", "single"
MIN_SIDE = 80     # px; a plane is never drawn smaller
COLORBAR_PX = 70  # px reserved for the one visible colour bar

_GRID = {ROW: (1, 3), COLUMN: (3, 1), L: (2, 2), SINGLE: (1, 1)}
_POSITIONS = {
    ROW: ((0, 0), (0, 1), (0, 2)),
    COLUMN: ((0, 0), (1, 0), (2, 0)),
    L: ((0, 0), (0, 1), (1, 0)),
    SINGLE: ((0, 0),),
}


def _raw_side(arr: str, width: int, height: int, extra_w: int) -> float:
    rows, cols = _GRID[arr]
    return min((width - extra_w) / cols, height / rows)


def side(arr: str, width: int, height: int, extra_w: int = COLORBAR_PX) -> int:
    """Largest square plane side for this arrangement inside width x height (clamped to MIN_SIDE)."""
    return max(int(_raw_side(arr, width, height, extra_w)), MIN_SIDE)


def arrangement(width: int, height: int, extra_w: int = COLORBAR_PX) -> str:
    """ROW, COLUMN or L: whichever gives the largest planes (ties: ROW, then L, then COLUMN)."""
    best, best_side = ROW, float("-inf")
    for arr in (ROW, L, COLUMN):
        s = _raw_side(arr, width, height, extra_w)
        if s > best_side:
            best, best_side = arr, s
    return best


def positions(arr: str) -> tuple[tuple[int, int], ...]:
    return _POSITIONS[arr]


def shared_zrange(zs, decades: float) -> tuple[float, float] | None:
    """(max / 10**decades, max) over the positive finite values of all planes; None if there are none."""
    hi = None
    for z in zs:
        z = np.asarray(z, dtype=float)
        pos = z[np.isfinite(z) & (z > 0)]
        if pos.size:
            m = float(pos.max())
            hi = m if hi is None else max(hi, m)
    if hi is None:
        return None
    return hi * 10.0 ** (-decades), hi


def mask_outside(z, zrange) -> np.ndarray:
    """Copy of z with values below zrange[0] (and ≤ 0, NaN) set to NaN; all NaN when zrange is None."""
    z = np.array(z, dtype=float)
    if zrange is None:
        return np.full_like(z, np.nan)
    z[~(z >= zrange[0])] = np.nan
    return z
