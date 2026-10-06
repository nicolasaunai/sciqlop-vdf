import pytest
from sciqlop_vdf.core.cache import WindowCache
from sciqlop_vdf.model import NoDataError
from sciqlop_vdf.synthetic import SyntheticSource


class Counting:
    def __init__(self, src=None):
        self.src = src or SyntheticSource()
        self.name = self.src.name
        self.calls = []

    def cadence(self):
        return self.src.cadence()

    def get(self, start, stop):
        self.calls.append((start, stop))
        return self.src.get(start, stop)


def test_default_window_from_cadence():
    assert WindowCache(Counting()).window_s == pytest.approx(30.0)  # 200 x 0.15 s


def test_reuses_window():
    s = Counting(); c = WindowCache(s)
    c.batch_for(100.0); c.batch_for(105.0); c.batch_for(101.0, 103.0)
    assert len(s.calls) == 1
    a, b = s.calls[0]
    assert a == pytest.approx(85.0) and b == pytest.approx(115.0)


def test_request_near_window_edge_refetches():
    s = Counting(); c = WindowCache(s)
    c.batch_for(100.0)
    c.batch_for(114.95)  # inside [85, 115] but within one cadence of its edge
    assert len(s.calls) == 2


def test_interval_longer_than_window_fetches_exact_range():
    s = Counting(); c = WindowCache(s)
    c.batch_for(0.0, 100.0)
    a, b = s.calls[0]
    assert a == pytest.approx(-0.15) and b == pytest.approx(100.15)


def test_lru_eviction():
    s = Counting(); c = WindowCache(s, max_entries=2)
    for t in (100.0, 200.0, 300.0, 100.0):
        c.batch_for(t)
    assert len(s.calls) == 4  # 100 evicted by 300, refetched


def test_errors_propagate_and_are_not_cached():
    class Failing(Counting):
        def get(self, start, stop):
            self.calls.append((start, stop)); raise NoDataError("gap")
    s = Failing(); c = WindowCache(s)
    for _ in range(2):
        with pytest.raises(NoDataError):
            c.batch_for(100.0)
    assert len(s.calls) == 2


def test_interval_longer_than_window_is_not_cached():
    s = Counting(); c = WindowCache(s)
    c.batch_for(100.0)                 # normal window, cached
    c.batch_for(0.0, 600.0); c.batch_for(0.0, 600.0)
    assert len(s.calls) == 3           # long interval fetched twice, never stored
    c.batch_for(101.0)
    assert len(s.calls) == 3           # the normal window is still cached
