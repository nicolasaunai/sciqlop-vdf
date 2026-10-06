"""Three XY colormaps with contours in a sub-panel of a SciQLop plot panel.

SciQLop 0.13 quirks handled here (design §7 O3, M3 findings):
- on XY colormap plots the visible vertical axis is "y2" (next to the colour bar); "y" is hidden;
- `plot.overlay.show` does not render → titles are centre-anchored `Text` items, x on the x axis and
  y on the hidden "y" axis (pinned to [0, 1]); the "ColorMap" legend is hidden;
- contours need the C++ `SciQLopColorMap` behind the public wrapper.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor
from SciQLop.user_api.plot import PlotType, Text
from SciQLop.user_api.plot.enums import CoordinateSystem, Orientation
from SciQLop.user_api.threading import invoke_on_main_thread, unwrap

from ..core.pipeline import Planes
from .format import display_z, split_message, titles


def _colormap_impl(graph):
    return unwrap(graph._impl)


class VDFViewer:
    def __init__(self, panel, height_px: int = 380):
        self._panel = panel
        self._sub = panel.add_sub_panel(Orientation.Horizontal)
        invoke_on_main_thread(lambda: unwrap(self._sub._impl).setMinimumHeight(height_px))
        self._plots, self._graphs, self._texts = [], [], []
        self._create_plots()

    @property
    def sub_panel(self):
        return self._sub

    def _create_plots(self) -> None:
        """Empty planes up front so message() works before the first show()."""
        axis = np.array([-1.0, 1.0])
        empty = np.full((2, 2), np.nan)
        for _ in range(3):
            plot, graph = self._sub.plot_data(axis, axis, empty, plot_type=PlotType.XY, z_log_scale=True)
            invoke_on_main_thread(lambda p=plot: unwrap(p._impl).legend().set_visible(False))
            plot.set_axis_range("y", 0.0, 1.0)  # hidden axis that anchors the title Text
            self._plots.append(plot); self._graphs.append(graph)

    def show(self, planes: Planes) -> None:
        for i, pl in enumerate(planes.planes):
            z, zrange = display_z(pl.z)
            self._graphs[i].set_data(pl.x, pl.y, z)
            plot = self._plots[i]
            plot.set_axis_label("x", pl.xlabel, "km/s")
            plot.set_axis_label("y2", pl.ylabel, "km/s")
            plot.set_axis_label("z", "f", pl.unit)
            plot.rescale_axes()
            plot.set_axis_range("y", 0.0, 1.0)  # hidden axis that anchors the title Text
            if zrange is not None:
                plot.set_axis_range("z", *zrange)
            self._set_contours(self._graphs[i], pl.levels)
        self._set_titles(titles(planes))

    def message(self, text: str) -> None:
        """Status line (errors, 'no data', 'computing'), spread over the three plane titles."""
        self._set_titles(split_message(text, n=3))

    def dispose(self) -> None:
        """Remove the viewer row from its panel."""
        parent_impl = unwrap(self._panel._impl)
        sub_impl = unwrap(self._sub._impl)
        invoke_on_main_thread(lambda: parent_impl.remove_panel(sub_impl))

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

    def _set_titles(self, texts) -> None:
        # Text is centre-anchored; its (x, y) map to the x axis and the HIDDEN "y" axis, which we pin
        # to [0, 1] in show(). So (0, 0.95) is the top centre of each plane.
        for i, plot in enumerate(self._plots):
            if i < len(self._texts):
                self._texts[i].text = texts[i]
            else:
                self._texts.append(Text(plot, texts[i], 0.0, 0.95, coordinate_system=CoordinateSystem.Data))

    @staticmethod
    def _set_contours(graph, levels) -> None:
        impl = _colormap_impl(graph)

        def apply():
            impl.set_contour_levels([float(x) for x in levels])
            impl.set_contour_color(QColor("white"))

        invoke_on_main_thread(apply)
