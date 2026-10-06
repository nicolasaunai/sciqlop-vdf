import numpy as np
from sciqlop_vdf.core.pipeline import compute_planes
from sciqlop_vdf.synthetic import SyntheticSource
from sciqlop_vdf.ui.format import display_z, titles


def test_display_z_blanks_nonpositive_and_far_tail():
    z = np.array([[1e-12, 1e-8], [0.0, -1.0], [np.nan, 1e-13]])
    out, rng = display_z(z, decades=4)
    assert rng == (1e-12, 1e-8)
    assert out[0, 0] == 1e-12 and out[0, 1] == 1e-8
    assert np.isnan(out[1]).all() and np.isnan(out[2]).all()


def test_display_z_all_empty():
    out, rng = display_z(np.zeros((2, 2)))
    assert rng is None and np.isnan(out).all()


def test_titles_single_and_interval():
    b = SyntheticSource(name="SYN").get(0.0, 1.0)
    one = titles(compute_planes(b, 0.3))
    assert one == ("1970-01-01 00:00:00.300", "native | reduced", "SYN | N=1")
    avg = titles(compute_planes(b, 0.0, 0.45))
    assert avg[0] == "1970-01-01 00:00:00.000–00:00:00.450" and avg[2] == "SYN | N=4"


def test_split_message_over_three_titles():
    from sciqlop_vdf.ui.format import split_message
    msg = "no MMS1 FPI-DIS brst distribution between 2015-07-28T13:05:45.000 and 2015-07-28T13:06:15.000"
    parts = split_message(msg, n=3, width=40)
    assert len(parts) == 3 and all(len(p) <= 40 for p in parts)
    assert " ".join(p for p in parts if p) == msg
    assert split_message("short", n=3) == ("short", "", "")


def test_titles_show_the_cut_when_off_origin():
    from sciqlop_vdf.core.pipeline import Options
    b = SyntheticSource(name="SYN").get(0.0, 1.0)
    t = titles(compute_planes(b, 0.3, options=Options(mode="slice", vmax=1500.0, slice_point=(0.0, 0.0, 300.0))))
    assert t[0].endswith(" | vz SYNTH = 300 km/s") and t[2].endswith(" | vx SYNTH = 0 km/s")
