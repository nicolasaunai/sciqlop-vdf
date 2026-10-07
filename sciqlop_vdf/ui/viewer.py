"""Three XY colormaps with contours, each in its own standalone SciQLopMultiPlotPanel, laid out by ui.layout.

SciQLop 0.13 quirks handled here (design §7 O3, dock spike §10 of design_dock_ui.md):
- on XY colormap plots the visible vertical axis is "y2"; "y" is hidden;
- `plot.overlay.show` does not render → titles are centre-anchored `Text` items, x on the x axis and y on the
  hidden "y" axis pinned to [0, 1]; the "ColorMap" legend is hidden;
- contours and colour-scale hiding need the C++ objects behind the public wrappers.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from SciQLop.user_api.plot import PlotPanel, PlotType, Text
from SciQLop.user_api.plot.enums import CoordinateSystem
from SciQLop.user_api.threading import unwrap
from SciQLopPlots import SciQLopMultiPlotPanel

from ..core.pipeline import Planes
from . import layout
from .format import plane_title

COLORBAR_PLANE = 2  # the plane that shows the shared colour bar in three-plane mode
GAP = layout.GAP  # px between planes


class PlaneArea(QWidget):
    """GUI thread only. Positions its three plot panels itself (no QLayout: the dock must stay shrinkable)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._choice = -1
        self.arrangement = layout.ROW
        self._impls, self._plots, self._graphs, self._texts = [], [], [], []
        axis = np.array([-1.0, 1.0])
        empty = np.full((2, 2), np.nan)
        for _ in range(3):
            impl = SciQLopMultiPlotPanel(self, synchronize_x=False, synchronize_time=False)
            impl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            impl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            plot, graph = PlotPanel(impl).plot_data(axis, axis, empty, plot_type=PlotType.XY, z_log_scale=True)
            unwrap(plot._impl).legend().set_visible(False)
            plot.set_axis_range("y", 0.0, 1.0)
            self._impls.append(impl)
            self._plots.append(plot)
            self._graphs.append(graph)
        self._set_titles(("", "", ""))
        self._place_colorbar()

    # --- geometry ----------------------------------------------------------------------------------------
    def minimumSizeHint(self) -> QSize:
        return QSize(layout.MIN_SIDE + layout.COLORBAR_PX, layout.MIN_SIDE)

    def sizeHint(self) -> QSize:
        return QSize(3 * 300 + layout.COLORBAR_PX, 300)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        w, h = self.width(), self.height()
        if self._choice >= 0:
            arr, shown = layout.SINGLE, [self._choice]
        else:
            arr, shown = layout.arrangement(w, h), [0, 1, 2]
        self.arrangement = arr
        s = layout.side(arr, w, h)
        for i, impl in enumerate(self._impls):
            impl.setVisible(i in shown)
        for (row, col), i in zip(layout.positions(arr), shown):
            extra = layout.COLORBAR_PX if i == self._colorbar_plane() else 0
            self._impls[i].setGeometry(col * (s + GAP), row * (s + GAP), s + extra, s)

    def _colorbar_plane(self) -> int:
        return self._choice if self._choice >= 0 else COLORBAR_PLANE

    def _place_colorbar(self) -> None:
        bar = self._colorbar_plane()
        for i, plot in enumerate(self._plots):
            impl = unwrap(plot._impl)
            if i == bar:
                impl.show_color_scale()
            else:
                impl.hide_color_scale()

    def set_plane_choice(self, i: int) -> None:
        self._choice = i if i in (0, 1, 2) else -1
        self._place_colorbar()
        self._relayout()

    # --- data --------------------------------------------------------------------------------------------
    def display(self, planes: Planes, decades: float) -> None:
        zr = layout.shared_zrange([pl.z for pl in planes.planes], decades)
        for i, pl in enumerate(planes.planes):
            plot = self._plots[i]
            self._graphs[i].set_data(pl.x, pl.y, layout.mask_outside(pl.z, zr))
            plot.set_axis_label("x", pl.xlabel, "km/s")
            plot.set_axis_label("y2", pl.ylabel, "km/s")
            plot.set_axis_label("z", "f", pl.unit)
            plot.rescale_axes()
            plot.set_axis_range("y", 0.0, 1.0)
            if zr is not None:
                plot.set_axis_range("z", *zr)
            self._set_contours(self._graphs[i], pl.levels)
        self._set_titles(tuple(plane_title(pl) for pl in planes.planes))

    def clear(self) -> None:
        """Empty the planes (no data for the request): a stale image must not stay on screen."""
        axis = np.array([-1.0, 1.0])
        for graph, plot in zip(self._graphs, self._plots):
            graph.set_data(axis, axis, np.full((2, 2), np.nan))
            self._set_contours(graph, [])
            plot.set_axis_label("x", "", "")
            plot.set_axis_label("y2", "", "")
            plot.rescale_axes()
            plot.set_axis_range("y", 0.0, 1.0)
        self._set_titles(("", "", ""))

    def _set_titles(self, texts) -> None:
        for i, plot in enumerate(self._plots):
            if i < len(self._texts):
                self._texts[i].text = texts[i]
            else:
                self._texts.append(Text(plot, texts[i], 0.0, 0.95, coordinate_system=CoordinateSystem.Data))

    @staticmethod
    def _set_contours(graph, levels) -> None:
        impl = unwrap(graph._impl)
        impl.set_contour_levels([float(x) for x in levels])
        impl.set_contour_color(QColor("white"))
