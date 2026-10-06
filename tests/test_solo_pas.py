import numpy as np
import pytest

from sciqlop_vdf_solo.pas import pas_look_to_velocity, pas_to_batch

AZ = np.array([-21.7, -2.7, 3.1, 39.1])          # look azimuth, deg
EL = np.array([-17.1, -0.5, 19.9])               # look elevation, deg
E_DESC = np.array([4000.0, 2000.0, 1000.0])      # PAS stores energies descending
PAS_TO_RTN = np.array([[-1.0, 0, 0], [0, 0.964, -0.265], [0, -0.265, -0.964]])  # typical, rows = RTN axes in PAS


def _raw(nt=2):
    f = np.zeros((nt, AZ.size, EL.size, E_DESC.size))
    f[:, 2, 1, 1] = 5e-9                          # one bin: az 3.1, el -0.5, 2000 eV  (s^3 m^-6)
    f[0, 0, 0, 0] = -1e31                         # fill
    return dict(time_s=np.array([100.0, 101.0])[:nt], f_m=f, energy=E_DESC, azimuth=AZ, elevation=EL,
                pas_to_rtn=np.repeat(PAS_TO_RTN[None], nt, 0))


def _unit(theta_deg, phi_deg):
    th, ph = np.deg2rad(theta_deg), np.deg2rad(phi_deg)
    return np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])


def test_look_to_velocity_is_antipode():
    th, ph = pas_look_to_velocity(np.array([0.0, 10.0]), np.array([0.0, -20.0]))
    np.testing.assert_allclose(th, [90.0, 100.0])          # polar of -look: 90 + elevation
    np.testing.assert_allclose(ph, [180.0, 160.0])
    look = np.array([np.cos(np.deg2rad(10)) * np.cos(np.deg2rad(-20)),
                     np.cos(np.deg2rad(10)) * np.sin(np.deg2rad(-20)), np.sin(np.deg2rad(10))])
    np.testing.assert_allclose(_unit(th[1], ph[1]), -look, atol=1e-12)


def test_units_fill_energy_order_and_shapes():
    b = pas_to_batch(**_raw())
    # one NaN guard bin on each side in azimuth and elevation (limited field of view)
    assert b.f.shape == (2, 6, 5, 3) and b.energy.shape == (2, 3) and b.theta.shape == (2, 5) and b.phi.shape == (2, 6)
    np.testing.assert_allclose(b.energy[0], [1000.0, 2000.0, 4000.0])     # ascending
    assert b.f[1, 3, 2, 1] == pytest.approx(5e-9 * 1e18)                  # s^3 m^-6 -> s^3 km^-6, same bin (+1 pad)
    assert np.isnan(b.f[0, 1, 1, 2])                                      # fill (was 4000 eV, now last)
    assert b.f[1, 1, 1, 0] == 0.0                                         # measured nothing stays 0
    assert b.native_frame == "PAS" and b.mass_amu == pytest.approx(1.007276) and b.charge == 1
    assert b.one_count is None


def test_field_of_view_guard_bins():
    b = pas_to_batch(**_raw())
    assert np.isnan(b.f[:, 0]).all() and np.isnan(b.f[:, -1]).all()          # azimuth guards
    assert np.isnan(b.f[:, :, 0]).all() and np.isnan(b.f[:, :, -1]).all()    # elevation guards
    # guards one edge-spacing beyond the table: az -21.7 - 19.0 and 39.1 + 36.0 (look) -> +180 for velocity
    np.testing.assert_allclose(b.phi[0, [0, -1]], np.mod([-21.7 - 19.0 + 180.0, 39.1 + 36.0 + 180.0], 360.0))
    np.testing.assert_allclose(b.theta[0, [0, -1]], [90.0 + (-17.1 - 16.6), 90.0 + (19.9 + 20.4)])


def test_regrid_is_nan_outside_field_of_view():
    from sciqlop_vdf.core.regrid import regrid_one
    r = _raw()
    r["f_m"][:] = 1e-9                                  # flat inside the field of view
    b = pas_to_batch(**r)
    inside = 400.0 * np.array([-1.0, 0.0, 0.0])         # velocity along -x_PAS = look +x_PAS (FOV centre)
    behind = 400.0 * np.array([1.0, 0.0, 0.0])          # opposite direction: never seen by PAS
    out = regrid_one(b.f[0], b.energy[0], b.theta[0], b.phi[0], b.mass_amu, np.stack([inside, behind]))
    assert np.isfinite(out[0]) and np.isnan(out[1])


def test_rtn_rotation_and_sunward_look_gives_antisunward_velocity():
    b = pas_to_batch(**_raw())
    np.testing.assert_allclose(b.rotations["RTN"][0], PAS_TO_RTN)
    # the populated bin looks almost along +x_PAS (sunward): its velocity must be ~ +R
    v_pas = _unit(b.theta[0, 2], b.phi[0, 3])
    v_rtn = b.rotations["RTN"][0] @ v_pas
    assert v_rtn[0] > 0.99


def test_aux_vectors_rotated_into_pas():
    r = _raw()
    t = np.array([99.0, 102.0])
    b_rtn = np.array([[10.0, 0, 0], [10.0, 0, 0]])
    v_rtn = np.array([[600.0, 0, 0], [600.0, 0, 0]])
    b = pas_to_batch(**r, b_rtn=(t, b_rtn), v_rtn=(t, v_rtn))
    np.testing.assert_allclose(b.b[0], PAS_TO_RTN.T @ [10.0, 0, 0], atol=1e-12)    # = (-10, 0, 0) in PAS
    np.testing.assert_allclose(b.rotations["RTN"][0] @ b.v_bulk[1], [600.0, 0, 0], atol=1e-9)


def test_alpha_species_maps_to_true_alpha_velocity():
    from sciqlop_vdf.core.regrid import speed_from_energy
    p = pas_to_batch(**_raw())
    a = pas_to_batch(**_raw(), species="alpha")
    assert a.mass_amu == pytest.approx(4.001506) and a.charge == 2
    np.testing.assert_allclose(a.energy, 2.0 * p.energy)                     # kinetic energy = Z * E/q
    # same E/q bin: alpha speed = proton-assumed speed / sqrt(2) (m/q = 2)
    ratio = speed_from_energy(a.energy[0], a.mass_amu) / speed_from_energy(p.energy[0], p.mass_amu)
    np.testing.assert_allclose(ratio, np.sqrt(2 * 1.007276 / 4.001506), rtol=1e-12)   # ~ 1/sqrt(2)
    # f ∝ counts v^-4 -> f_alpha = f_proton * (v_p / v_alpha)^4
    k = (2 * 1.007276 / 4.001506) ** -2
    assert a.f[1, 3, 2, 1] == pytest.approx(p.f[1, 3, 2, 1] * k)
    with pytest.raises(ValueError):
        pas_to_batch(**_raw(), species="oxygen")


def test_min_e_per_q_blanks_lower_energy_bins():
    a = pas_to_batch(**_raw(), species="alpha", min_e_per_q=1500.0)
    # E/q 1000 eV (index 0) blanked; 2000 and 4000 eV kept (kinetic energies 4000 / 8000 eV for Z=2)
    assert np.isnan(a.f[:, 1:-1, 1:-1, 0]).all()
    assert a.f[1, 3, 2, 1] > 0 and np.isfinite(a.f[1, 1:-1, 1:-1, 1:]).all()


def test_max_e_per_q_blanks_upper_energy_bins():
    p = pas_to_batch(**_raw(), max_e_per_q=3000.0)
    assert np.isnan(p.f[:, 1:-1, 1:-1, 2]).all()                       # 4000 eV blanked
    assert np.isfinite(p.f[1, 1:-1, 1:-1, :2]).all()


def _planes(z_list, x=np.array([-1.0, 0.0, 1.0])):
    from sciqlop_vdf.core.pipeline import Plane, Planes
    pl = tuple(Plane(x, x, np.asarray(z, float), "a", "b", "s^2/km^5", []) for z in z_list)
    return Planes(pl, "field-aligned", "reduced", True, 0.0, 1.0, 1, "x", ("v∥", "v⊥1", "v⊥2"))


def test_sum_planes_adds_species_and_keeps_nan_only_where_both_missing():
    from sciqlop_vdf_solo.combined import sum_planes
    n = np.nan
    a = _planes([[[1, n, n], [n, 2, n], [n, n, n]]] * 3)
    b = _planes([[[3, 5, n], [n, 4, n], [n, n, n]]] * 3)
    s = sum_planes(a, b, label="p + He++")
    np.testing.assert_allclose(s.planes[0].z, [[4, 5, n], [n, 6, n], [n, n, n]])
    assert s.label == "p + He++" and s.planes[0].levels and max(s.planes[0].levels) == pytest.approx(6.0)
    assert s.frame == "field-aligned" and s.axes == a.axes


def test_sum_planes_rejects_different_grids():
    from sciqlop_vdf.model import VDFError
    from sciqlop_vdf_solo.combined import sum_planes
    a = _planes([np.ones((3, 3))] * 3)
    b = _planes([np.ones((3, 3))] * 3, x=np.array([-2.0, 0.0, 2.0]))
    with pytest.raises(VDFError):
        sum_planes(a, b)


def test_missing_aux_gives_none():
    b = pas_to_batch(**_raw(), b_rtn=None, v_rtn=(np.array([]), np.zeros((0, 3))))
    assert b.b is None and b.v_bulk is None
