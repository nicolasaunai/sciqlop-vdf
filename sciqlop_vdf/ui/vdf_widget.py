"""Content of a VDF dock: toolbar, planes, status line (PySide6 only)."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

ERROR_STYLE = "color: #c0392b;"


class VDFWidget(QWidget):
    def __init__(self, controls: QWidget, planes: QWidget, parent=None):
        super().__init__(parent)
        self.controls, self.planes = controls, planes
        self.status = QLabel("")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(controls, 0)
        lay.addWidget(planes, 1)
        lay.addWidget(self.status, 0)

    def set_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(ERROR_STYLE if error else "")
