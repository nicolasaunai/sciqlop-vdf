"""Fetch-window cache in front of a VDFSource (Qt-free, thread-safe)."""
from __future__ import annotations

import threading

from ..model import VDFBatch, VDFSource


class WindowCache:
    def __init__(self, source: VDFSource, window_s: float | None = None, max_entries: int = 3):
        self._source = source
        self._window = float(window_s) if window_s is not None else max(10.0, 200.0 * source.cadence())
        self._max = max_entries
        self._entries: list[tuple[float, float, VDFBatch]] = []  # least recently used first
        self._lock = threading.Lock()

    @property
    def window_s(self) -> float:
        return self._window

    def batch_for(self, t0: float, t1: float | None = None) -> VDFBatch:
        lo, hi = (t0, t0) if t1 is None else (min(t0, t1), max(t0, t1))
        pad = self._source.cadence()
        with self._lock:
            for i, (a, b, batch) in enumerate(self._entries):
                if a <= lo - pad and hi + pad <= b:
                    self._entries.append(self._entries.pop(i))
                    return batch
            if hi - lo >= self._window:
                # long interval: fetch exactly, never store (one 10 min burst interval ≈ 0.5 GB of f)
                return self._source.get(lo - pad, hi + pad)
            mid, half = 0.5 * (lo + hi), 0.5 * self._window
            a, b = mid - half, mid + half
            batch = self._source.get(a, b)
            self._entries.append((a, b, batch))
            del self._entries[:-self._max]
            return batch
