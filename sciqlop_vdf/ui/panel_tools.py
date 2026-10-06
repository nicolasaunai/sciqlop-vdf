"""Placement of the control bar in the panel container (private SciQLop layout, isolated here)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from SciQLop.user_api.threading import unwrap


def panel_container(panel):
    """The PanelContainer (QVBoxLayout: [plots, chrome row]) that hosts this panel, or None."""
    node = unwrap(panel._impl)
    while node is not None:
        if type(node).__name__ == "PanelContainer":
            return node
        node = node.parent()
    return None


def insert_controls(panel, widget) -> bool:
    """Insert the bar between the plots and the time-range bar; fall back to a floating tool window."""
    container = panel_container(panel)
    if container is None or container.layout() is None:
        widget.setWindowFlag(Qt.Tool, True)
        widget.show()
        return False
    container.layout().insertWidget(1, widget)
    return True
