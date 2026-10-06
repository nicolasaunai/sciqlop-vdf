"""'VDF ▾' button in each panel's chrome row: attach the viewer for a registered source."""
from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMenu, QToolButton
from SciQLop.user_api.plot import PlotPanel
from SciQLop.user_api.threading import unwrap

from .. import registry
from .controller import attach

log = logging.getLogger(__name__)
BUTTON_NAME = "sciqlop_vdf_attach"


def product_paths(panel: PlotPanel) -> list[str]:
    paths = []
    for p in panel.plots:
        for g in unwrap(p._impl).plottables():
            path = g.property("sqp_product_path")  # private SciQLop property (design §7 O4)
            if path:
                paths.append(str(path))
    return paths


class AttachButton(QToolButton):
    def __init__(self, tsp, parent=None):
        super().__init__(parent)
        self.setObjectName(BUTTON_NAME)
        self.setText("VDF ▾")
        self.setToolTip("Attach a velocity-distribution viewer to this panel")
        self.setPopupMode(QToolButton.InstantPopup)
        self._tsp = tsp
        self.controllers = []
        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self._fill)
        self.setMenu(self._menu)

    def ranked(self) -> list:
        return registry.rank_sources(registry.sources(), product_paths(PlotPanel(self._tsp)))

    def _fill(self) -> None:
        self._menu.clear()
        entries = self.ranked()
        if not entries:
            self._menu.addAction("no VDF source registered").setEnabled(False)
        for e in entries:
            self._menu.addAction(e.label).triggered.connect(lambda _=False, e=e: self.attach(e.key))

    def attach(self, key: str):
        ctl = attach(PlotPanel(self._tsp), registry.get_source(key).factory())
        self.controllers.append(ctl)
        return ctl


def _container(tsp):
    node = tsp
    while node is not None:
        if type(node).__name__ == "PanelContainer":
            return node
        node = node.parent()
    return None


def install(tsp) -> bool:
    """Add the button to the panel's chrome row once; False if the panel has no PanelContainer."""
    container = _container(tsp)
    row = getattr(container, "chrome_row", None)
    if row is None or row.layout() is None:
        return False
    if row.findChild(QToolButton, BUTTON_NAME) is not None:
        return True
    layout = row.layout()
    layout.insertWidget(max(layout.count() - 1, 0), AttachButton(tsp, row))
    return True


def install_attach_buttons(main_window) -> None:
    for name in main_window.plot_panels():
        tsp = main_window.plot_panel(name)
        if tsp is not None:
            install(tsp)
    main_window.panel_added.connect(lambda tsp: QTimer.singleShot(0, lambda: install(tsp)))
