"""One movable vertical line per time-series plot of a panel, kept at the same time (GUI thread only)."""
from __future__ import annotations

from typing import Callable

from SciQLop.user_api.plot import TimeSeriesPlot, VerticalLine
from SciQLop.user_api.threading import unwrap


class SyncedMarker:
    def __init__(self, panel, t: float, on_moved: Callable[[float], None], color: str = "#f39c12"):
        self._panel, self._on_moved, self._color = panel, on_moved, color
        self._t = float(t)
        self._lines: list[tuple[object, VerticalLine]] = []  # (plot impl, line)
        self._syncing = False
        self._refresh()
        self._plot_list_changed = unwrap(panel._impl).plot_list_changed
        self._plot_list_changed.connect(self._refresh)

    @property
    def value(self) -> float:
        return self._t

    def set_value(self, t: float) -> None:
        if self._lines:
            self._lines[0][1].value = float(t)  # fires position_changed -> _moved
        else:
            self._t = float(t)
            self._on_moved(self._t)

    def _refresh(self, *_):
        plots = [p for p in self._panel.plots if isinstance(p, TimeSeriesPlot)]
        impls = [unwrap(p._impl) for p in plots]
        self._lines = [(i, l) for i, l in self._lines if any(i is j for j in impls)]
        for p, impl in zip(plots, impls):
            if not any(impl is i for i, _ in self._lines):
                line = VerticalLine(p, self._t, color=self._color, movable=True)
                unwrap(line._impl).position_changed.connect(self._moved)
                self._lines.append((impl, line))

    def _moved(self, pos) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._t = float(pos)
            for _, line in self._lines:
                if line.value != self._t:
                    line.value = self._t
        finally:
            self._syncing = False
        self._on_moved(self._t)

    def remove(self) -> None:
        try:
            self._plot_list_changed.disconnect(self._refresh)
        except (RuntimeError, TypeError):
            pass
        for _, line in self._lines:
            line.remove()
        self._lines = []
