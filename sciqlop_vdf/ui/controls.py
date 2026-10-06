"""Compact one-row control bar for the VDF viewer (PySide6 only; no SciQLop import)."""
from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QSpinBox,
                               QToolButton, QWidget)


class VDFControls(QWidget):
    options_changed = Signal(dict)
    mode_changed = Signal(str)
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._silent = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(6)

        def add(label, w, tip):
            if label:
                lay.addWidget(QLabel(label))
            w.setToolTip(tip)
            lay.addWidget(w)
            return w

        lay.addWidget(QLabel("<b>VDF</b>"))
        self.mode = add("", QComboBox(),
                        "marker: distribution closest to the orange line; interval: average over the blue span")
        self.mode.addItems(["marker", "interval"])
        self.frame = add("frame", QComboBox(), "projection frame")
        self.bulk = add("", QCheckBox("bulk frame"), "subtract the bulk velocity")
        self.projection = add("", QComboBox(), "reduced: ∫f dv₃ (s²/km⁵); slice: f in |v₃| < Δ (s³/km⁶)")
        self.projection.addItems(["reduced", "slice"])
        self.halfwidth = add("Δ", QDoubleSpinBox(), "slice half-thickness, km/s (0 = half a cell)")
        self.halfwidth.setRange(0.0, 5000.0)
        self.halfwidth.setSingleStep(10.0)
        self.halfwidth.setSpecialValueText("auto")
        self.slice_labels, self.slice_v = [], []
        for name in ("v₁", "v₂", "v₃"):
            lbl = QLabel(name)
            lay.addWidget(lbl)
            box = add("", QDoubleSpinBox(), "slice point, km/s along this frame axis (relative to the bulk "
                                            "velocity in bulk frame); each plane is cut through it")
            box.setRange(-1e5, 1e5)
            box.setSingleStep(50.0)
            box.setDecimals(0)
            box.setKeyboardTracking(False)
            self.slice_labels.append(lbl); self.slice_v.append(box)
        self.grid = add("grid", QSpinBox(), "cells per velocity axis")
        self.grid.setRange(16, 128)  # 128³ ≈ 2.1M nodes; 256³ needs ~2 GB
        self.grid.setSingleStep(16)
        self.grid.setValue(64)
        self.vmax = add("|v|max", QDoubleSpinBox(), "half-width of the velocity grid, km/s (0 = automatic)")
        self.vmax.setRange(0.0, 1e5)
        self.vmax.setSingleStep(100.0)
        self.vmax.setSpecialValueText("auto")
        self.contours = add("contours", QSpinBox(), "number of log-spaced contours over 3 decades (0 = none)")
        self.contours.setRange(0, 10)
        self.contours.setValue(5)
        self.one_count = add("", QCheckBox("mask < 1 count"), "hide cells below the one-count level")
        self.close_button = add("", QToolButton(), "remove the VDF viewer from this panel")
        self.close_button.setText("×")
        lay.addStretch(1)

        self.mode.currentTextChanged.connect(self._on_mode)
        self.frame.currentTextChanged.connect(lambda v: self._emit(frame=v) if v else None)
        self.bulk.toggled.connect(lambda v: self._emit(bulk_frame=bool(v)))
        self.projection.currentTextChanged.connect(self._on_projection)
        self.halfwidth.valueChanged.connect(lambda v: self._emit(slice_halfwidth=float(v) or None))
        for box in self.slice_v:
            box.valueChanged.connect(lambda _v: self._emit(slice_point=tuple(float(b.value()) for b in self.slice_v)))
        self.grid.valueChanged.connect(lambda v: self._emit(grid_n=int(v)))
        self.vmax.valueChanged.connect(lambda v: self._emit(vmax=float(v) or None))
        self.contours.valueChanged.connect(lambda v: self._emit(contour_n=int(v)))
        self.one_count.toggled.connect(lambda v: self._emit(one_count_mask=bool(v)))
        self.close_button.clicked.connect(self.close_requested.emit)

    def _on_mode(self, mode: str) -> None:
        if not self._silent:
            self.mode_changed.emit(mode)

    def _on_projection(self, mode: str) -> None:
        self._enable_slice(mode == "slice")
        self._emit(mode=mode)

    def _enable_slice(self, on: bool) -> None:
        for w in (*self.slice_labels, *self.slice_v):
            w.setEnabled(on)

    def set_axes(self, labels) -> None:
        """Name the slice-point boxes after the frame axes (e.g. "vx GSE", "v∥")."""
        for lbl, name in zip(self.slice_labels, labels):
            lbl.setText(name)

    def _emit(self, **field) -> None:
        if not self._silent:
            self.options_changed.emit(field)

    @contextmanager
    def _quiet(self):
        self._silent = True
        try:
            yield
        finally:
            self._silent = False

    def set_frames(self, frames: list[str], current: str) -> None:
        with self._quiet():
            if [self.frame.itemText(i) for i in range(self.frame.count())] != list(frames):
                self.frame.clear()
                self.frame.addItems(list(frames))
            self.frame.setCurrentText(current)

    def set_values(self, options, mode: str) -> None:
        with self._quiet():
            self.mode.setCurrentText(mode)
            if self.frame.findText(options.frame) < 0:
                self.frame.addItem(options.frame)
            self.frame.setCurrentText(options.frame)
            self.bulk.setChecked(options.bulk_frame)
            self.projection.setCurrentText(options.mode)
            self.halfwidth.setValue(options.slice_halfwidth or 0.0)
            for box, v in zip(self.slice_v, options.slice_point):
                box.setValue(float(v))
            self._enable_slice(options.mode == "slice")
            self.grid.setValue(options.grid_n)
            self.vmax.setValue(options.vmax or 0.0)
            self.contours.setValue(options.contour_n)
            self.one_count.setChecked(options.one_count_mask)
