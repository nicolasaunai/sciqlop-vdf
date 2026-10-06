from sciqlop_vdf import registry
from sciqlop_vdf_mms.fpi import FPISource
from sciqlop_vdf_mms.sources import register


def test_registers_all_fpi_sources():
    registry.clear()
    register()
    keys = [e.key for e in registry.sources()]
    assert len(keys) == 16 and keys[0] == "mms/mms1/ion/brst"
    e = registry.get_source("mms/mms3/electron/fast")
    assert e.label == "MMS3 FPI-DES fast" and e.tags == ("MMS3", "DES", "FAST") and e.group == "MMS"
    src = e.factory()
    assert isinstance(src, FPISource) and (src.sc, src.species, src.mode) == ("mms3", "electron", "fast")
    registry.clear()
