import pytest


@pytest.fixture
def manager(qapp):
    import PySide6QtAds as QtAds
    from PySide6.QtWidgets import QMainWindow
    win = QMainWindow()
    mgr = QtAds.CDockManager(win)
    yield mgr
    win.deleteLater()


def test_two_docks_with_the_same_title_stay_distinct(manager):
    from PySide6.QtWidgets import QWidget
    from sciqlop_vdf.ui.dock import VDFDock
    a = VDFDock(QWidget(), "VDF · X ↔ Panel0", None, manager=manager)
    b = VDFDock(QWidget(), "VDF · X ↔ Panel0", None, manager=manager)
    assert len([d for d in manager.dockWidgetsMap().values() if d.windowTitle() == "VDF · X ↔ Panel0"]) == 2
    a.close()
    assert any(d.windowTitle() == "VDF · X ↔ Panel0" for d in manager.dockWidgetsMap().values())


def test_content_destroyed_elsewhere_reports_closed(manager, qapp):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QWidget
    from sciqlop_vdf.ui.dock import VDFDock
    d = VDFDock(QWidget(), "VDF · Y ↔ Panel0", None, manager=manager)
    fired = []
    d.closed.connect(lambda: fired.append(1))
    d._doc.takeWidget().deleteLater()   # e.g. SciQLop/QtAds tears the dock down without the ×
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert fired == [1]


def test_own_close_does_not_report_closed(manager, qapp):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QWidget
    from sciqlop_vdf.ui.dock import VDFDock
    d = VDFDock(QWidget(), "VDF · Z ↔ Panel0", None, manager=manager)
    fired = []
    d.closed.connect(lambda: fired.append(1))
    d.close()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert fired == []
