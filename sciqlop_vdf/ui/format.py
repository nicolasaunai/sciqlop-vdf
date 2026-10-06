"""Qt-free display helpers for the VDF viewer (unit-tested)."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from ..core.pipeline import Planes

DISPLAY_DECADES = 4.0  # colour range below the maximum; contours span 3 by default


def display_z(z: np.ndarray, decades: float = DISPLAY_DECADES) -> tuple[np.ndarray, tuple[float, float] | None]:
    """Values ≤ 0 or more than `decades` below the max → NaN (transparent). Returns (z, (lo, hi) or None)."""
    z = np.array(z, dtype=float)
    pos = z[np.isfinite(z) & (z > 0)]
    if pos.size == 0:
        return np.full_like(z, np.nan), None
    hi = float(pos.max())
    lo = hi * 10.0 ** (-decades)
    z[~(z >= lo)] = np.nan
    return z, (lo, hi)


def split_message(text: str, n: int = 3, width: int = 45) -> tuple[str, ...]:
    """Split a status line at word boundaries over the n plane titles (last chunk takes the rest)."""
    words, parts, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width and len(parts) < n - 1:
            parts.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    parts.append(cur)
    return tuple(parts + [""] * (n - len(parts)))


def fmt_time(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def titles(planes: Planes) -> tuple[str, str, str]:
    """Short per-plane captions: when / frame and mode / source and number of distributions."""
    if planes.n_used == 1:
        when = fmt_time(planes.t_start)
    else:
        when = f"{fmt_time(planes.t_start)}–{fmt_time(planes.t_stop)[11:]}"
    frame = planes.frame + (", bulk frame" if planes.bulk_frame else "")
    base = (when, f"{frame} | {planes.mode}", f"{planes.label} | N={planes.n_used}")
    return tuple(f"{b} | {pl.cut}" if pl.cut else b for b, pl in zip(base, planes.planes))
