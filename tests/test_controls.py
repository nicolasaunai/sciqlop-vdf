from sciqlop_vdf.core.pipeline import Options


def _bar(qapp):
    from sciqlop_vdf.ui.controls import VDFControls
    bar = VDFControls()
    got = {"opts": [], "mode": [], "close": 0, "time": [], "plane": []}
    bar.options_changed.connect(lambda d: got["opts"].append(d))
    bar.mode_changed.connect(lambda m: got["mode"].append(m))
    bar.close_requested.connect(lambda: got.__setitem__("close", got["close"] + 1))
    bar.time_edited.connect(lambda v: got["time"].append(v))
    bar.plane_choice_changed.connect(lambda i: got["plane"].append(i))
    return bar, got


def test_set_values_is_silent(qapp):
    bar, got = _bar(qapp)
    bar.set_frames(["native", "GSE", "field-aligned"], "GSE")
    bar.set_values(Options(frame="GSE", grid_n=96, display_decades=5.0), "interval")
    assert got == {"opts": [], "mode": [], "close": 0, "time": [], "plane": []}
    assert bar.frame.currentText() == "GSE" and bar.grid.value() == 96 and bar.decades.value() == 5.0
    assert bar.interval_btn.isChecked() and not bar.marker_btn.isChecked()


def test_each_control_emits_its_field(qapp):
    bar, got = _bar(qapp)
    bar.set_frames(["native", "GSE"], "native")
    bar.frame.setCurrentText("GSE")
    bar.bulk.setChecked(True)
    bar.slice_btn.click()
    bar.grid.setValue(96)
    bar.contours.setValue(0)
    bar.decades.setValue(3.0)
    bar.one_count.setChecked(True)
    assert got["opts"] == [{"frame": "GSE"}, {"bulk_frame": True}, {"mode": "slice"}, {"grid_n": 96},
                           {"contour_n": 0}, {"display_decades": 3.0}, {"one_count_mask": True}]


def test_zero_spin_values_mean_automatic(qapp):
    bar, got = _bar(qapp)
    bar.vmax.setValue(1500.0); bar.vmax.setValue(0.0)
    bar.halfwidth.setValue(50.0); bar.halfwidth.setValue(0.0)
    assert got["opts"] == [{"vmax": 1500.0}, {"vmax": None}, {"slice_halfwidth": 50.0}, {"slice_halfwidth": None}]


def test_mode_buttons_and_close(qapp):
    bar, got = _bar(qapp)
    bar.interval_btn.click()
    bar.marker_btn.click()
    bar.close_button.click()
    assert got["mode"] == ["interval", "marker"] and got["close"] == 1


def test_grid_is_capped_at_128(qapp):
    bar, _ = _bar(qapp)
    bar.grid.setValue(256)
    assert bar.grid.value() == 128


def test_slice_group_hidden_unless_slice(qapp):
    bar, got = _bar(qapp)
    bar.set_values(Options(), "marker")
    assert bar.slice_group.isHidden()
    bar.slice_btn.click()
    assert not bar.slice_group.isHidden()
    got["opts"].clear()
    bar.slice_v[2].setValue(300.0)
    assert got["opts"] == [{"slice_point": (0.0, 0.0, 300.0)}]
    bar.reduced_btn.click()
    assert bar.slice_group.isHidden()


def test_set_axes_names_slice_boxes_and_plane_choice(qapp):
    bar, _ = _bar(qapp)
    bar.set_axes(("v∥", "v⊥1", "v⊥2"))
    assert [l.text() for l in bar.slice_labels] == ["v∥ [km/s]", "v⊥1 [km/s]", "v⊥2 [km/s]"]
    assert [bar.plane_choice.itemText(i) for i in range(3)] == ["v∥ – v⊥1", "v∥ – v⊥2", "v⊥1 – v⊥2"]


def test_single_plane_toggle(qapp):
    bar, got = _bar(qapp)
    bar.set_axes(("vx", "vy", "vz"))
    assert not bar.plane_choice.isEnabled()
    bar.single_btn.click()
    assert bar.plane_choice.isEnabled()
    bar.plane_choice.setCurrentIndex(2)
    bar.single_btn.click()
    assert got["plane"] == [0, 2, -1]


def test_time_edit_valid_marker(qapp):
    bar, got = _bar(qapp)
    bar.set_values(Options(), "marker")
    bar.set_readout("2017-07-11 22:34:02.120")
    assert bar.time_edit.isReadOnly()
    bar.time_edit.begin_edit()
    bar.time_edit.setText("2017-07-11 22:35:00")
    bar.time_edit.editingFinished.emit()
    assert got["time"] == [(1499812500.0, None)] and bar.time_edit.isReadOnly()


def test_time_edit_rejects_garbage_and_reverts(qapp):
    bar, got = _bar(qapp)
    bar.set_values(Options(), "interval")
    bar.set_readout("2017-07-11 22:34:02.120 → 22:34:22.120 (N=67)")
    bar.time_edit.begin_edit()
    bar.time_edit.setText("2017-07-11 22:34:02 → 22:34:00")  # stop before start
    bar.time_edit.editingFinished.emit()
    assert got["time"] == []
    assert bar.time_edit.text() == "2017-07-11 22:34:02.120 → 22:34:22.120 (N=67)"
    assert "stop must be after start" in bar.time_edit.toolTip()


def test_toolbar_wraps_without_overlap_when_narrow(qapp):
    from PySide6.QtCore import QRect
    bar, _ = _bar(qapp)
    lay = bar.layout()
    assert lay.hasHeightForWidth()
    assert lay.heightForWidth(500) > lay.heightForWidth(3000)
    lay.setGeometry(QRect(0, 0, 500, lay.heightForWidth(500)))
    rects = [lay.itemAt(i).geometry() for i in range(lay.count()) if not lay.itemAt(i).isEmpty()]
    assert all(r.right() < 500 for r in rects)
    assert not any(a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1:])
