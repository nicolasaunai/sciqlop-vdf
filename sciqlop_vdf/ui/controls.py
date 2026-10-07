"""VDF dock toolbar + ⚙ drop-down (PySide6 only; no SciQLop import)."""
from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QSpinBox, QToolButton, QVBoxLayout,
                               QWidget, QWidgetAction)

from ..core.pipeline import PAIRS  # plane i: (x axis, y axis, collapsed axis)
from .flow_layout import FlowLayout
from .format import parse_readout

MARKER_COLOR, SPAN_COLOR = "#f39c12", "#3498db"  # same as ui/marker.py and ui/interval.py


class TimeEdit(QLineEdit):
    """Read-only time readout; double-click to edit. Owner validates on editingFinished."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance("0000-00-00 00:00:00.000 → 00:00:00.000 (N=000)"))
        self.setToolTip("double-click to type a time (marker) or 'start → stop' (interval)")

    def begin_edit(self) -> None:
        self.setReadOnly(False)
        self.selectAll()
        self.setFocus()

    def mouseDoubleClickEvent(self, event):
        self.begin_edit()
        super().mouseDoubleClickEvent(event)


def _toggle(text: str, tip: str, color: str | None = None) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setCheckable(True)
    if color:
        b.setStyleSheet(f"QToolButton:checked {{ color: {color}; font-weight: bold; }}")
    return b


def _group(*widgets) -> QWidget:
    """Keep widgets together when the toolbar wraps."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    for x in widgets:
        lay.addWidget(x)
    return w


def _spin(cls, lo, hi, step, special=None, decimals=None):
    w = cls()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    if special:
        w.setSpecialValueText(special)
    if decimals is not None:
        w.setDecimals(decimals)
    w.setKeyboardTracking(False)
    return w


class VDFControls(QWidget):
    options_changed = Signal(dict)
    mode_changed = Signal(str)
    close_requested = Signal()
    time_edited = Signal(object)          # (t0, t1 | None)
    plane_choice_changed = Signal(int)    # -1: three planes; 0..2: that plane alone

    def __init__(self, parent=None):
        super().__init__(parent)
        self._silent = False
        self._interval = False
        self._readout = ""
        bar = FlowLayout(self)
        bar.setContentsMargins(4, 2, 4, 2)

        # selection
        self.marker_btn = _toggle("● Marker", "distribution closest to the orange line", MARKER_COLOR)
        self.interval_btn = _toggle("▭ Interval", "average over the blue span", SPAN_COLOR)
        self._mode_group = QButtonGroup(self)
        for b in (self.marker_btn, self.interval_btn):
            self._mode_group.addButton(b)
        self.time_edit = TimeEdit()
        bar.addWidget(_group(self.marker_btn, self.interval_btn, self.time_edit))

        # frame
        self.frame = QComboBox()
        self.frame.setToolTip("projection frame")
        self.frame.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        bar.addWidget(_group(QLabel("Frame:"), self.frame))
        self.bulk = QCheckBox("Bulk frame (v − V_bulk)")
        self.bulk.setToolTip("subtract the bulk velocity")
        bar.addWidget(self.bulk)

        # projection
        self.reduced_btn = _toggle("Reduced ∫f dv₃", "reduced distribution, s²/km⁵")
        self.slice_btn = _toggle("Slice", "f in a slab |v₃ − v₃₀| < Δ, s³/km⁶; set the cut in ⚙")
        self._proj_group = QButtonGroup(self)
        for b in (self.reduced_btn, self.slice_btn):
            self._proj_group.addButton(b)
        bar.addWidget(_group(self.reduced_btn, self.slice_btn))

        # planes
        self.single_btn = _toggle("1 plane", "show one plane at full size")
        self.plane_choice = QComboBox()
        self.plane_choice.addItems(["plane 1", "plane 2", "plane 3"])
        self.plane_choice.setEnabled(False)
        self.plane_choice.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        bar.addWidget(_group(self.single_btn, self.plane_choice))

        # settings drop-down
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("slice, grid and display settings")
        self.settings_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.settings_btn)
        action = QWidgetAction(menu)
        action.setDefaultWidget(self._build_settings())
        menu.addAction(action)
        self.settings_btn.setMenu(menu)
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("Close VDF viewer")
        bar.addWidget(_group(self.settings_btn, self.close_button))

        self._connect()

    def _build_settings(self) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)

        self.slice_group = QGroupBox("Slice")
        f = QFormLayout(self.slice_group)
        self.slice_labels, self.slice_v = [], []
        for name in ("v₁", "v₂", "v₃"):
            lbl = QLabel(f"{name} [km/s]")
            w = _spin(QDoubleSpinBox, -1e5, 1e5, 50.0, decimals=0)
            w.setToolTip("slice point along this frame axis (bulk-relative in bulk frame)")
            f.addRow(lbl, w)
            self.slice_labels.append(lbl)
            self.slice_v.append(w)
        self.halfwidth = _spin(QDoubleSpinBox, 0.0, 5000.0, 10.0, special="auto")
        f.addRow("half-thickness Δ [km/s]", self.halfwidth)
        col.addWidget(self.slice_group)

        grid = QGroupBox("Grid")
        f = QFormLayout(grid)
        self.grid = _spin(QSpinBox, 16, 128, 16)  # 128³ ≈ 2.1M nodes; 256³ needs ~2 GB
        self.grid.setValue(64)
        f.addRow("cells per axis", self.grid)
        self.vmax = _spin(QDoubleSpinBox, 0.0, 1e5, 100.0, special="auto")
        f.addRow("|v| max [km/s]", self.vmax)
        col.addWidget(grid)

        disp = QGroupBox("Display")
        f = QFormLayout(disp)
        self.contours = _spin(QSpinBox, 0, 10, 1)
        self.contours.setValue(5)
        f.addRow("contours (log, 3 decades)", self.contours)
        self.decades = _spin(QDoubleSpinBox, 1.0, 8.0, 0.5, decimals=1)
        self.decades.setValue(4.0)
        f.addRow("colour range [decades below max]", self.decades)
        self.one_count = QCheckBox("mask cells < 1 count")
        f.addRow(self.one_count)
        col.addWidget(disp)
        return box

    def _connect(self) -> None:
        self.marker_btn.toggled.connect(lambda on: on and self._emit_mode("marker"))
        self.interval_btn.toggled.connect(lambda on: on and self._emit_mode("interval"))
        self.time_edit.editingFinished.connect(self._on_time_edited)
        self.frame.currentTextChanged.connect(lambda v: self._emit(frame=v) if v else None)
        self.bulk.toggled.connect(lambda v: self._emit(bulk_frame=bool(v)))
        self.reduced_btn.toggled.connect(lambda on: on and self._on_projection("reduced"))
        self.slice_btn.toggled.connect(lambda on: on and self._on_projection("slice"))
        self.halfwidth.valueChanged.connect(lambda v: self._emit(slice_halfwidth=float(v) or None))
        for box in self.slice_v:
            box.valueChanged.connect(lambda _v: self._emit(slice_point=tuple(float(b.value()) for b in self.slice_v)))
        self.grid.valueChanged.connect(lambda v: self._emit(grid_n=int(v)))
        self.vmax.valueChanged.connect(lambda v: self._emit(vmax=float(v) or None))
        self.contours.valueChanged.connect(lambda v: self._emit(contour_n=int(v)))
        self.decades.valueChanged.connect(lambda v: self._emit(display_decades=float(v)))
        self.one_count.toggled.connect(lambda v: self._emit(one_count_mask=bool(v)))
        self.single_btn.toggled.connect(self._on_single)
        self.plane_choice.currentIndexChanged.connect(self._on_plane_choice)
        self.close_button.clicked.connect(self.close_requested.emit)

    # --- slots -------------------------------------------------------------------------------------------
    def _emit_mode(self, mode: str) -> None:
        self._interval = mode == "interval"
        if not self._silent:
            self.mode_changed.emit(mode)

    def _on_projection(self, mode: str) -> None:
        self.slice_group.setHidden(mode != "slice")
        self._emit(mode=mode)

    def _on_single(self, on: bool) -> None:
        self.plane_choice.setEnabled(on)
        if not self._silent:
            self.plane_choice_changed.emit(self.plane_choice.currentIndex() if on else -1)

    def _on_plane_choice(self, i: int) -> None:
        if self.single_btn.isChecked() and not self._silent:
            self.plane_choice_changed.emit(i)

    def _on_time_edited(self) -> None:
        if self.time_edit.isReadOnly():
            return
        try:
            value = parse_readout(self.time_edit.text(), interval=self._interval)
        except ValueError as e:
            self.time_edit.setToolTip(f"rejected: {e}")
            self.time_edit.setStyleSheet("QLineEdit { border: 1px solid #c0392b; }")
            self.time_edit.setText(self._readout)
            self.time_edit.setReadOnly(True)
            return
        self.time_edit.setStyleSheet("")
        self.time_edit.setReadOnly(True)
        self.time_edited.emit(value)

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

    # --- setters (never emit) ----------------------------------------------------------------------------
    def set_readout(self, text: str) -> None:
        self._readout = text
        if self.time_edit.isReadOnly():
            self.time_edit.setText(text)

    def set_axes(self, labels) -> None:
        """Name the slice boxes and the plane choices after the frame axes (e.g. "v∥", "v⊥1")."""
        for lbl, name in zip(self.slice_labels, labels):
            lbl.setText(f"{name} [km/s]")
        if len(labels) == 3:
            with self._quiet():
                for i, (a, b, _) in enumerate(PAIRS):
                    self.plane_choice.setItemText(i, f"{labels[a]} – {labels[b]}")

    def set_frames(self, frames: list[str], current: str) -> None:
        with self._quiet():
            if [self.frame.itemText(i) for i in range(self.frame.count())] != list(frames):
                self.frame.clear()
                self.frame.addItems(list(frames))
            self.frame.setCurrentText(current)

    def set_values(self, options, mode: str) -> None:
        with self._quiet():
            (self.interval_btn if mode == "interval" else self.marker_btn).setChecked(True)
            self._interval = mode == "interval"
            if self.frame.findText(options.frame) < 0:
                self.frame.addItem(options.frame)
            self.frame.setCurrentText(options.frame)
            self.bulk.setChecked(options.bulk_frame)
            (self.slice_btn if options.mode == "slice" else self.reduced_btn).setChecked(True)
            self.slice_group.setHidden(options.mode != "slice")
            self.halfwidth.setValue(options.slice_halfwidth or 0.0)
            for box, v in zip(self.slice_v, options.slice_point):
                box.setValue(float(v))
            self.grid.setValue(options.grid_n)
            self.vmax.setValue(options.vmax or 0.0)
            self.contours.setValue(options.contour_n)
            self.decades.setValue(options.display_decades)
            self.one_count.setChecked(options.one_count_mask)
