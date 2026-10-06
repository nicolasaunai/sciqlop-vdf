import numpy as np
import pytest
from sciqlop_vdf.core.average import select
from sciqlop_vdf.model import NoDataError

T = np.array([0.0, 0.15, 0.30, 0.45])


def test_select_nearest():
    assert select(T, 0.2).tolist() == [1]


def test_select_nearest_respects_max_gap():
    with pytest.raises(NoDataError, match="10"):
        select(T, 10.0, max_gap=0.3)


def test_select_interval_inclusive_and_unordered():
    assert select(T, 0.30, 0.15).tolist() == [1, 2]


def test_select_empty_interval_raises():
    with pytest.raises(NoDataError, match="0.16"):
        select(T, 0.16, 0.20)


def test_select_no_data_raises():
    with pytest.raises(NoDataError):
        select(np.array([]), 0.0)


def test_select_messages_use_iso_times():
    with pytest.raises(NoDataError, match=r"1970-01-01T00:00:10\.000"):
        select(T, 10.0, max_gap=0.3)
    with pytest.raises(NoDataError, match=r"1970-01-01T00:00:00\.160.*1970-01-01T00:00:00\.200"):
        select(T, 0.16, 0.20)
