from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from ..model import NoDataError


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def select(time_s, t0: float, t1: float | None = None, max_gap: float | None = None) -> np.ndarray:
    time_s = np.asarray(time_s, float)
    if time_s.size == 0:
        raise NoDataError("no distribution in the fetched data")
    if t1 is None:
        k = int(np.argmin(np.abs(time_s - t0)))
        gap = abs(time_s[k] - t0)
        if max_gap is not None and gap > max_gap:
            raise NoDataError(f"no distribution within {max_gap:.3f} s of {iso(t0)} (closest {gap:.3f} s away)")
        return np.array([k])
    lo, hi = min(t0, t1), max(t0, t1)
    idx = np.nonzero((time_s >= lo) & (time_s <= hi))[0]
    if idx.size == 0:
        raise NoDataError(f"no distribution between {iso(lo)} and {iso(hi)}")
    return idx
