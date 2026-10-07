"""The only module touching SciQLop's private docking (the main window's QtAds dock manager)."""
from __future__ import annotations

import logging
import uuid

import PySide6QtAds as QtAds
from PySide6.QtCore import QObject, QTimer, Signal
from SciQLop.user_api.gui import get_main_window
from SciQLop.user_api.threading import unwrap

log = logging.getLogger(__name__)
SPLIT_FRACTION = 0.4  # share of the panel+viewer width given to the viewer


class VDFDock(QObject):
    """GUI thread only. `closed` fires when the user clicks the dock's × (not on close())."""
    closed = Signal()

    def __init__(self, widget, title: str, beside: str | None, manager=None):
        super().__init__()
        self._mgr = manager if manager is not None else unwrap(get_main_window()).dock_manager
        self._done = False
        self._doc = QtAds.CDockWidget(title)
        self._doc.setObjectName(f"vdf-{uuid.uuid4().hex}")  # QtAds keys docks by object name (= title)
        widget.destroyed.connect(self._on_content_destroyed)
        self._doc.setWidget(widget, QtAds.CDockWidget.ForceNoScrollArea)
        self._doc.setFeature(QtAds.CDockWidget.CustomCloseHandling, True)
        self._doc.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
        self._doc.closeRequested.connect(self.closed.emit)
        target = self._mgr.findDockWidget(beside) if beside else None
        target_area = target.dockAreaWidget() if target is not None else None
        self.placed_beside = target_area is not None
        if self.placed_beside:
            area = self._mgr.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, self._doc, target_area)
            QTimer.singleShot(0, lambda: self._split(area))
        else:
            self._mgr.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, self._doc)

    def _on_content_destroyed(self, *_):
        """Content deleted by someone else (QtAds/SciQLop teardown): report it like a user close."""
        if not self._done:
            self._done = True
            self.closed.emit()

    def _split(self, area) -> None:
        if self._done:
            return
        try:
            sizes = list(self._mgr.splitterSizes(area))
        except RuntimeError:  # area already gone
            return
        if len(sizes) == 2 and sum(sizes) > 0:
            total = sum(sizes)
            right = int(SPLIT_FRACTION * total)
            self._mgr.setSplitterSizes(area, [total - right, right])

    def close(self) -> None:
        """Take the content out and delete it before the dock (and a floating window) goes away."""
        if self._done:
            return
        self._done = True
        try:
            w = self._doc.takeWidget()
            if w is not None:
                w.hide()
                w.deleteLater()
            self._doc.closeDockWidget()
        except RuntimeError:  # C++ dock already deleted (application shutdown)
            log.debug("VDF dock already gone")
