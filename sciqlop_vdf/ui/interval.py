"""Draggable panel-wide time span selecting the averaging interval (GUI thread only)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QColor
from SciQLop.user_api.threading import unwrap
from SciQLopPlots import MultiPlotsVerticalSpan, SciQLopPlotRange


class IntervalSpan:
    def __init__(self, panel, t0: float, t1: float, on_changed: Callable[[float, float], None],
                 color: str = "#3498db", label: str = "VDF average"):
        c = QColor(color)
        c.setAlpha(60)
        self._span = MultiPlotsVerticalSpan(unwrap(panel._impl), SciQLopPlotRange(float(t0), float(t1), True),
                                            c, False, True, label)
        self._span.range_changed.connect(lambda r: on_changed(r.start(), r.stop()))

    @property
    def range(self) -> tuple[float, float]:
        r = self._span.range  # property on MultiPlotsVerticalSpan (not a method)
        return (r.start(), r.stop())

    def set_range(self, t0: float, t1: float) -> None:
        self._span.set_range(SciQLopPlotRange(float(t0), float(t1), True))

    def remove(self) -> None:
        self._span.deleteLater()
