def test_layout_and_status(qapp):
    from PySide6.QtWidgets import QWidget
    from sciqlop_vdf.ui.controls import VDFControls
    from sciqlop_vdf.ui.vdf_widget import VDFWidget
    planes = QWidget()
    w = VDFWidget(VDFControls(), planes)
    lay = w.layout()
    assert [lay.itemAt(i).widget() for i in range(3)] == [w.controls, planes, w.status]
    assert lay.stretch(1) == 1 and lay.stretch(0) == 0 and lay.stretch(2) == 0
    w.set_status("no data", error=False)
    assert w.status.text() == "no data" and w.status.styleSheet() == ""
    w.set_status("ValueError: boom", error=True)
    assert w.status.text() == "ValueError: boom" and "#c0392b" in w.status.styleSheet()
