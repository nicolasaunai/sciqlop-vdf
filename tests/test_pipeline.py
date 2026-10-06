import numpy as np
import pytest
from sciqlop_vdf.core.pipeline import Options, compute_planes
from sciqlop_vdf.core.frames import FIELD_ALIGNED, available_frames
from sciqlop_vdf.model import VDFError, VDFSource
from sciqlop_vdf.synthetic import SyntheticSource

RZ90 = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])  # u = R v: x -> y


def _density(plane):
    dv = plane.x[1] - plane.x[0]
    return np.nansum(plane.z) * dv ** 2 * 1e-15


def _peak(plane):
    i, j = np.unravel_index(np.nanargmax(plane.z), plane.z.shape)
    return np.array([plane.x[i], plane.y[j]]), plane.x[1] - plane.x[0]


def test_source_protocol():
    assert isinstance(SyntheticSource(), VDFSource)


def test_reduced_native_density_and_peak():
    b = SyntheticSource().get(0.0, 1.0)
    p = compute_planes(b, 0.3)
    assert p.n_used == 1 and p.mode == "reduced"
    assert p.planes[0].unit == "s^2/km^5"
    assert p.planes[0].xlabel == "vx SYNTH" and p.planes[2].ylabel == "vz SYNTH"
    for plane in p.planes:
        assert _density(plane) == pytest.approx(10.0, rel=0.03)
    pk, dv = _peak(p.planes[0])
    assert np.all(np.abs(pk - [300, -100]) <= 1.5 * dv)
    assert len(p.planes[0].levels) == 5


def test_interval_average_over_alternating_tables():
    b = SyntheticSource(alternate_tables=True).get(0.0, 2.0)
    p = compute_planes(b, 0.0, 1.5)
    assert p.n_used == 11
    assert _density(p.planes[0]) == pytest.approx(10.0, rel=0.03)


def test_rotation_frame():
    b = SyntheticSource(rotations={"ROT": RZ90}).get(0.0, 1.0)
    assert available_frames(b) == ["native", "ROT", FIELD_ALIGNED]
    p = compute_planes(b, 0.3, options=Options(frame="ROT"))
    pk, dv = _peak(p.planes[0])
    assert np.all(np.abs(pk - [100, 300]) <= 1.5 * dv)


def test_bulk_frame_centres_peak():
    b = SyntheticSource().get(0.0, 1.0)
    p = compute_planes(b, 0.3, options=Options(bulk_frame=True))
    pk, dv = _peak(p.planes[0])
    assert np.all(np.abs(pk) <= 1.5 * dv)


def test_field_aligned_anisotropy():
    src = SyntheticSource(t_par_ev=2000.0, t_perp_ev=500.0, v_kms=(200.0, 0.0, 0.0), b_nt=(0.0, 0.0, 10.0))
    p = compute_planes(src.get(0.0, 1.0), 0.3, options=Options(frame=FIELD_ALIGNED, bulk_frame=True, grid_n=96))
    plane = p.planes[0]  # (v_par, v_perp1)
    assert (plane.xlabel, plane.ylabel) == ("v∥", "v⊥1")
    w = np.nan_to_num(plane.z)
    X, Y = np.meshgrid(plane.x, plane.y, indexing="ij")
    ratio = np.sum(w * X ** 2) / np.sum(w * Y ** 2)
    assert ratio == pytest.approx(4.0, rel=0.15)


def test_slice_mode_units_and_peak():
    b = SyntheticSource().get(0.0, 1.0)
    p = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True))
    assert p.planes[0].unit == "s^3/km^6"
    pk, dv = _peak(p.planes[0])
    assert np.all(np.abs(pk) <= 1.5 * dv)


def test_compute_planes_missing_b_or_v():
    b = SyntheticSource(b_nt=None, v_kms_aux=False).get(0.0, 1.0)
    assert FIELD_ALIGNED not in available_frames(b)
    with pytest.raises(VDFError, match="frame"):
        compute_planes(b, 0.3, options=Options(frame=FIELD_ALIGNED))
    with pytest.raises(VDFError, match="bulk velocity"):
        compute_planes(b, 0.3, options=Options(bulk_frame=True))


def test_compute_planes_all_zero_distribution():
    b = SyntheticSource(n_cm3=0.0).get(0.0, 1.0)
    p = compute_planes(b, 0.3)
    assert all(pl.levels == [] for pl in p.planes)


def test_invalid_mode():
    with pytest.raises(VDFError, match="mode"):
        compute_planes(SyntheticSource().get(0.0, 1.0), 0.3, options=Options(mode="cut"))


def test_far_marker_raises_by_default():
    b = SyntheticSource().get(0.0, 1.0)  # samples 0.00 .. 0.90 s, cadence 0.15 s
    from sciqlop_vdf.model import NoDataError
    with pytest.raises(NoDataError):
        compute_planes(b, 1e6)
    assert compute_planes(b, 0.95).n_used == 1  # within 1.5 cadences of the last sample


def test_bulk_frame_with_nan_velocity_raises():
    import dataclasses
    b = SyntheticSource().get(0.0, 1.0)
    b = dataclasses.replace(b, v_bulk=np.full_like(b.v_bulk, np.nan))
    with pytest.raises(VDFError, match="bulk velocity"):
        compute_planes(b, 0.3, options=Options(bulk_frame=True))


def test_compute_planes_can_be_cancelled():
    from sciqlop_vdf.model import Cancelled
    b = SyntheticSource().get(0.0, 2.0)
    calls = []
    def should_cancel():
        calls.append(1)
        return len(calls) > 2
    with pytest.raises(Cancelled):
        compute_planes(b, 0.0, 1.5, should_cancel=should_cancel)
    assert len(calls) == 3  # stopped at the third distribution, not after all 11


def test_auto_vmax_tracks_the_distribution():
    from sciqlop_vdf.core.pipeline import auto_vmax
    from sciqlop_vdf.core.regrid import speed_from_energy
    b = SyntheticSource().get(0.0, 1.0)  # T = 1 keV, |V| = 320 km/s
    top = float(speed_from_energy(30000.0, 1.007276))
    lab = auto_vmax(b, np.array([2]), np.zeros(3))
    bulk = auto_vmax(b, np.array([2]), b.v_bulk[2])
    assert 1300.0 < lab < 2100.0 < top   # 99 % density radius about 0 (|V| = 320 km/s), x1.1
    assert 1000.0 < bulk < lab          # chi-3 99 % quantile 3.37 sigma = 1042 km/s, x1.1 = 1146


def test_auto_vmax_falls_back_on_empty():
    from sciqlop_vdf.core.pipeline import auto_vmax
    from sciqlop_vdf.core.regrid import speed_from_energy
    b = SyntheticSource(n_cm3=0.0).get(0.0, 1.0)
    assert auto_vmax(b, np.array([0]), np.zeros(3)) == pytest.approx(float(speed_from_energy(30000.0, 1.007276)))


def test_compute_planes_uses_auto_vmax_by_default():
    b = SyntheticSource().get(0.0, 1.0)
    p = compute_planes(b, 0.3, options=Options(bulk_frame=True))
    assert p.planes[0].x[-1] < 1700.0  # well inside the 2397 km/s top-energy speed


def test_one_count_mask_removes_cells_below_level():
    src = SyntheticSource(one_count_level=1e4)
    b = src.get(0.0, 1.0)
    off = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True))
    on = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True, one_count_mask=True))
    z_off, z_on = off.planes[0].z, on.planes[0].z
    assert np.isfinite(z_on).sum() < np.isfinite(z_off).sum()
    assert np.nanmin(z_on) >= 1e4 * 0.999


def test_one_count_level_scales_with_number_of_samples():
    b = SyntheticSource(one_count_level=1e4).get(0.0, 2.0)
    one = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True, one_count_mask=True))
    four = compute_planes(b, 0.3, 0.75, options=Options(mode="slice", bulk_frame=True, one_count_mask=True))
    assert four.n_used == 4
    assert np.isfinite(four.planes[0].z).sum() > np.isfinite(one.planes[0].z).sum()


def test_one_count_mask_without_level_raises():
    with pytest.raises(VDFError, match="one-count"):
        compute_planes(SyntheticSource().get(0.0, 1.0), 0.3, options=Options(one_count_mask=True))


def test_one_count_threshold_divides_by_samples_averaged_in_f():
    import dataclasses
    b = SyntheticSource(one_count_level=1e4).get(0.0, 2.0)
    oc = b.one_count.copy(); oc[1:4] = np.nan          # f1 known in 1 of the 4 averaged samples
    b = dataclasses.replace(b, one_count=oc)
    p = compute_planes(b, 0.0, 0.45, options=Options(mode="slice", bulk_frame=True, one_count_mask=True))
    z = p.planes[0].z
    assert p.n_used == 4
    assert np.nanmin(z) < 0.9e4                         # threshold is f1/4, not f1/1
    assert np.nanmin(z) >= 2.5e3 * 0.999


def test_auto_vmax_keeps_a_hot_halo_under_a_cold_beam():
    from sciqlop_vdf.core.pipeline import auto_vmax
    from sciqlop_vdf.model import VDFBatch
    from tests.helpers import fpi_like_bins, bin_velocities, maxwellian_kms
    e, th, ph = fpi_like_bins()
    v = bin_velocities(e, th, ph)
    f = maxwellian_kms(v, 5.0, 10.0, (0, 0, 0)) + maxwellian_kms(v, 5.0, 1000.0, (0, 0, 0))
    b = VDFBatch(time=np.array([0], dtype="datetime64[ns]"), f=f[None], energy=e[None], theta=th[None],
                 phi=ph[None], mass_amu=1.007276, charge=1, native_frame="T")
    assert auto_vmax(b, np.array([0]), np.zeros(3)) > 1000.0  # ~98 % of the halo density: 3.0-3.4 sigma (309 km/s), x1.1


def test_zero_slice_point_reproduces_default_slice():
    b = SyntheticSource().get(0.0, 1.0)
    ref = compute_planes(b, 0.3, options=Options(mode="slice", vmax=1500.0))
    zero = compute_planes(b, 0.3, options=Options(mode="slice", vmax=1500.0, slice_point=(0.0, 0.0, 0.0)))
    for a, z in zip(ref.planes, zero.planes):
        np.testing.assert_array_equal(a.z, z.z)


def test_slice_through_the_drift_velocity_finds_the_peak():
    src = SyntheticSource(v_kms=(300.0, -100.0, 500.0))
    b = src.get(0.0, 1.0)
    o = Options(mode="slice", vmax=2000.0, grid_n=80)
    at0 = compute_planes(b, 0.3, options=o)
    atv = compute_planes(b, 0.3, options=Options(mode="slice", vmax=2000.0, grid_n=80,
                                                 slice_point=(300.0, -100.0, 500.0)))
    p0 = atv.planes[0]                       # (vx, vy) plane cut at vz = 500
    assert np.nanmax(p0.z) > 1.5 * np.nanmax(at0.planes[0].z)
    pk, dv = _peak(p0)
    assert np.all(np.abs(pk - [300, -100]) <= 1.5 * dv)
    # the three cuts pass through the same point: every plane peaks at the drift
    pk1, _ = _peak(atv.planes[1]); pk2, _ = _peak(atv.planes[2])
    assert np.all(np.abs(pk1 - [300, 500]) <= 1.5 * dv) and np.all(np.abs(pk2 - [-100, 500]) <= 1.5 * dv)
    assert np.nanmax(p0.z) == pytest.approx(src.f_kms(np.array([300.0, -100.0, 500.0])), rel=0.1)


def test_slice_point_outside_grid_raises():
    b = SyntheticSource().get(0.0, 1.0)
    with pytest.raises(VDFError, match="outside the grid"):
        compute_planes(b, 0.3, options=Options(mode="slice", vmax=1000.0, slice_point=(0.0, 0.0, 1500.0)))
    # reduced mode ignores the slice point
    compute_planes(b, 0.3, options=Options(mode="reduced", vmax=1000.0, slice_point=(0.0, 0.0, 1500.0)))


def test_slice_point_is_relative_to_bulk_in_bulk_frame():
    b = SyntheticSource(v_kms=(300.0, -100.0, 500.0)).get(0.0, 1.0)
    p = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True, vmax=1500.0,
                                               slice_point=(0.0, 0.0, 400.0)))
    q = compute_planes(b, 0.3, options=Options(mode="slice", bulk_frame=True, vmax=1500.0))
    assert np.nanmax(p.planes[0].z) < 0.5 * np.nanmax(q.planes[0].z)   # 400 km/s off the bulk: fainter


def test_planes_carry_axes_and_cut_text():
    b = SyntheticSource().get(0.0, 1.0)
    p = compute_planes(b, 0.3, options=Options(mode="slice", vmax=1500.0, slice_point=(0.0, 0.0, 300.0)))
    assert p.axes == ("vx SYNTH", "vy SYNTH", "vz SYNTH")
    assert p.planes[0].cut == "vz SYNTH = 300 km/s"
    assert p.planes[2].cut == "vx SYNTH = 0 km/s"
    assert all(pl.cut == "" for pl in compute_planes(b, 0.3, options=Options(mode="slice")).planes)
    assert all(pl.cut == "" for pl in compute_planes(
        b, 0.3, options=Options(mode="reduced", slice_point=(0.0, 0.0, 300.0))).planes)
