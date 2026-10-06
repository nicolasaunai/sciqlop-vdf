from sciqlop_vdf.core.pipeline import Options


def _bar(qapp):
    from sciqlop_vdf.ui.controls import VDFControls
    bar = VDFControls()
    got = {"opts": [], "mode": [], "close": 0}
    bar.options_changed.connect(lambda d: got["opts"].append(d))
    bar.mode_changed.connect(lambda m: got["mode"].append(m))
    bar.close_requested.connect(lambda: got.__setitem__("close", got["close"] + 1))
    return bar, got


def test_set_frames_is_silent(qapp):
    bar, got = _bar(qapp)
    bar.set_frames(["native", "GSE", "field-aligned"], "GSE")
    bar.set_values(Options(frame="GSE", grid_n=96), "marker")
    assert got["opts"] == [] and bar.frame.currentText() == "GSE" and bar.grid.value() == 96


def test_each_control_emits_its_field(qapp):
    bar, got = _bar(qapp)
    bar.set_frames(["native", "GSE"], "native")
    bar.frame.setCurrentText("GSE")
    bar.bulk.setChecked(True)
    bar.projection.setCurrentText("slice")
    bar.grid.setValue(96)
    bar.contours.setValue(0)
    bar.one_count.setChecked(True)
    assert got["opts"] == [{"frame": "GSE"}, {"bulk_frame": True}, {"mode": "slice"},
                           {"grid_n": 96}, {"contour_n": 0}, {"one_count_mask": True}]


def test_zero_spin_values_mean_automatic(qapp):
    bar, got = _bar(qapp)
    bar.vmax.setValue(1500.0); bar.vmax.setValue(0.0)
    bar.halfwidth.setValue(50.0); bar.halfwidth.setValue(0.0)
    assert got["opts"] == [{"vmax": 1500.0}, {"vmax": None}, {"slice_halfwidth": 50.0}, {"slice_halfwidth": None}]


def test_mode_and_close(qapp):
    bar, got = _bar(qapp)
    bar.mode.setCurrentText("interval")
    bar.close_button.click()
    assert got["mode"] == ["interval"] and got["close"] == 1


def test_grid_is_capped_at_128(qapp):
    bar, _ = _bar(qapp)
    bar.grid.setValue(256)
    assert bar.grid.value() == 128


def test_slice_point_boxes(qapp):
    bar, got = _bar(qapp)
    bar.set_values(Options(), "marker")
    assert not any(b.isEnabled() for b in bar.slice_v)            # reduced mode: disabled
    bar.projection.setCurrentText("slice")
    assert all(b.isEnabled() for b in bar.slice_v)
    got["opts"].clear()
    bar.slice_v[2].setValue(300.0)
    assert got["opts"] == [{"slice_point": (0.0, 0.0, 300.0)}]
    bar.set_axes(("v∥", "v⊥1", "v⊥2"))
    assert [l.text() for l in bar.slice_labels] == ["v∥", "v⊥1", "v⊥2"]
    got["opts"].clear()
    bar.set_values(Options(mode="slice", slice_point=(1.0, 2.0, 3.0)), "marker")
    assert got["opts"] == [] and [b.value() for b in bar.slice_v] == [1.0, 2.0, 3.0]
