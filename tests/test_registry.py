import pytest
from sciqlop_vdf import registry
from sciqlop_vdf.synthetic import SyntheticSource


@pytest.fixture(autouse=True)
def _clean():
    registry.clear(); yield; registry.clear()


def test_register_and_get():
    registry.register_source("syn/a", "Synthetic A", SyntheticSource, group="SYN", tags=("A",))
    e = registry.get_source("syn/a")
    assert e.label == "Synthetic A" and isinstance(e.factory(), SyntheticSource)
    assert [s.key for s in registry.sources()] == ["syn/a"]


def test_register_same_key_replaces():
    registry.register_source("k", "one", SyntheticSource)
    registry.register_source("k", "two", SyntheticSource)
    assert [s.label for s in registry.sources()] == ["two"]


def test_discover_skips_broken_entry_points():
    class EP:
        def __init__(self, name, fn): self.name, self._fn = name, fn
        def load(self): return self._fn
    def good(): registry.register_source("g", "good", SyntheticSource)
    def bad(): raise RuntimeError("boom")
    class Unloadable(EP):
        def load(self): raise ImportError("missing")
    n = registry.discover_sources([EP("bad", bad), Unloadable("u", None), EP("good", good)])
    assert n == 1 and [s.key for s in registry.sources()] == ["g"]


def test_rank_by_panel_products():
    for key, tags in (("mms1/ion/brst", ("MMS1", "DIS", "BRST")), ("mms2/ion/brst", ("MMS2", "DIS", "BRST")),
                      ("mms1/ion/fast", ("MMS1", "DIS", "FAST"))):
        registry.register_source(key, key, SyntheticSource, tags=tags)
    paths = ["speasy//cda//MMS//MMS1//FGM//MMS1_FGM_BRST_L2//mms1_fgm_b_gse_brst_l2"]
    ranked = [e.key for e in registry.rank_sources(registry.sources(), paths)]
    assert ranked == ["mms1/ion/brst", "mms1/ion/fast", "mms2/ion/brst"]


def test_rank_without_products_keeps_order():
    for k in ("b", "a", "c"):
        registry.register_source(k, k, SyntheticSource, tags=("X",))
    assert [e.key for e in registry.rank_sources(registry.sources(), [])] == ["b", "a", "c"]
