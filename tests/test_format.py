import pytest
from sciqlop_vdf.core.pipeline import Options, compute_planes
from sciqlop_vdf.synthetic import SyntheticSource
from sciqlop_vdf.ui.format import (dock_title, parse_readout, plane_title, readout, status_computing,
                                   status_done)

T = 1499812442.12  # 2017-07-11 22:34:02.120 UTC


def test_readout_marker_and_interval():
    assert readout(T, None) == "2017-07-11 22:34:02.120"
    assert readout(T, T + 20.0) == "2017-07-11 22:34:02.120 → 22:34:22.120"
    assert readout(T, T + 20.0, n=67) == "2017-07-11 22:34:02.120 → 22:34:22.120 (N=67)"


def test_parse_round_trips():
    assert parse_readout(readout(T, None), interval=False) == (pytest.approx(T), None)
    t0, t1 = parse_readout(readout(T, T + 20.0, n=67), interval=True)
    assert (t0, t1) == (pytest.approx(T), pytest.approx(T + 20.0))


def test_parse_accepts_iso_and_full_stop_date():
    assert parse_readout("2017-07-11T22:34:02", interval=False)[0] == pytest.approx(1499812442.0)
    t0, t1 = parse_readout("2017-07-11 23:59:50 -> 2017-07-12 00:00:10", interval=True)
    assert t1 - t0 == pytest.approx(20.0)


@pytest.mark.parametrize("text,interval", [
    ("yesterday", False), ("", False), ("2017-07-11 22:34:02", True),
    ("2017-07-11 22:34:02 → 22:34:00", True), ("2017-07-11 22:34:02 → 22:34:02", True),
])
def test_parse_rejects_bad_input(text, interval):
    with pytest.raises(ValueError):
        parse_readout(text, interval=interval)


def test_plane_titles():
    b = SyntheticSource(name="SYN").get(0.0, 1.0)
    p = compute_planes(b, 0.3)
    assert [plane_title(pl) for pl in p.planes] == [f"{pl.xlabel} – {pl.ylabel}" for pl in p.planes]
    s = compute_planes(b, 0.3, options=Options(mode="slice", vmax=1500.0, slice_point=(0.0, 0.0, 300.0)))
    assert plane_title(s.planes[0]).endswith("(vz SYNTH = 300 km/s)")


def test_dock_title_and_status():
    assert dock_title("MMS1 FPI-DIS brst", "Panel3") == "VDF · MMS1 FPI-DIS brst ↔ Panel3"
    assert status_computing(T, None) == "computing … 2017-07-11 22:34:02.120"
    assert status_done(67, 0.43) == "done · 67 distributions · 0.4 s"
    assert status_done(1, 0.06) == "done · 1 distribution · 0.1 s"


def test_display_decades_default():
    assert Options().display_decades == 4.0
