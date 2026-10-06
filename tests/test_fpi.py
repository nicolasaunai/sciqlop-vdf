import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from sciqlop_vdf_mms.fpi import fpi_to_batch, look_to_velocity


def _raw(nt=2, phi_1d=False):
    f = np.full((nt, 32, 16, 32), 2e-25); f[0, 0, 0, 0] = -1e31; f[0, 1, 0, 0] = 0.0
    err = f / np.sqrt(4.0)  # 4 counts
    phi = 5.625 + 11.25 * np.arange(32)
    return dict(
        time_s=np.array([100.0, 100.15])[:nt], f_cm=f, err_cm=err,
        energy=np.tile(np.logspace(1, 4.45, 32), (nt, 1)),
        theta_look=5.625 + 11.25 * np.arange(16),
        phi_look=phi if phi_1d else np.tile(phi, (nt, 1)),
        species="ion",
    )


def test_look_to_velocity():
    th, ph = look_to_velocity(np.array([90.0, 10.0]), np.array([0.0, 270.0]))
    np.testing.assert_allclose(th, [90.0, 170.0]); np.testing.assert_allclose(ph, [180.0, 90.0])


def test_units_fill_and_one_count():
    b = fpi_to_batch(**_raw())
    assert np.isnan(b.f[0, 0, 0, 0])
    assert b.f[0, 1, 0, 0] == 0.0
    assert b.f[1, 5, 5, 5] == pytest.approx(2e-25 * 1e30)
    assert b.one_count[1, 5, 5, 5] == pytest.approx(2e-25 / 4 * 1e30)
    assert b.one_count[0, 1, 0, 0] == pytest.approx(2e-25 / 4 * 1e30)  # f = 0 bin: filled from same energy
    assert b.mass_amu == pytest.approx(1.007276) and b.native_frame == "DBCS"


def test_fast_mode_phi_broadcast_and_theta_flip():
    b = fpi_to_batch(**_raw(phi_1d=True))
    assert b.phi.shape == (2, 32) and b.theta.shape == (2, 16)
    assert b.theta[0, 0] == pytest.approx(180 - 5.625)
    assert b.phi[1, 0] == pytest.approx(185.625)


def test_aux_interpolation_and_gse_rotation():
    r = _raw()
    q_dbcs = np.array([[0, 0, 0, 1.0]] * 2)
    q_gse = np.tile(Rotation.from_euler("z", 90, degrees=True).as_quat(), (2, 1))  # scalar-last
    b = fpi_to_batch(**r, b=(np.array([99.0, 101.0]), np.array([[0, 0, 10, 10.0], [0, 0, 20, 20.0]])),
                     v=(np.array([99.0, 101.0]), np.array([[100.0, 0, 0], [300.0, 0, 0]])),
                     quats=(np.array([90.0, 110.0]), q_dbcs, q_gse))
    np.testing.assert_allclose(b.b[0], [0, 0, 15.0])
    np.testing.assert_allclose(b.v_bulk[1], [215.0, 0, 0])
    np.testing.assert_allclose(b.rotations["GSE"][0] @ [1.0, 0, 0], [0, 1.0, 0], atol=1e-12)


def test_electron_mass():
    r = _raw(); r["species"] = "electron"
    assert fpi_to_batch(**r).mass_amu == pytest.approx(5.48579909e-4)


def test_bad_quaternions_never_fail_the_fetch():
    r = _raw()
    t = np.array([90.0, 110.0])
    bad = np.array([[np.nan] * 4, [0.0, 0.0, 0.0, 0.0]])
    assert "GSE" not in fpi_to_batch(**r, quats=(t, bad, bad)).rotations  # nothing valid -> no GSE
    one_bad = np.array([[0, 0, 0, 1.0], [np.nan] * 4])
    b = fpi_to_batch(**r, quats=(t, one_bad, one_bad))  # invalid sample dropped, GSE kept
    np.testing.assert_allclose(b.rotations["GSE"][0], np.eye(3), atol=1e-12)
    dup = (np.array([90.0, 90.0, 110.0]), np.tile([0, 0, 0, 1.0], (3, 1)), np.tile([0, 0, 0, 1.0], (3, 1)))
    assert "GSE" in fpi_to_batch(**r, quats=dup).rotations  # duplicate timestamps tolerated


def test_no_data_message_uses_iso_times(monkeypatch):
    from sciqlop_vdf.model import NoDataError
    from sciqlop_vdf_mms.fpi import FPISource
    src = FPISource()
    monkeypatch.setattr(src, "_get", lambda *a, **k: None)
    with pytest.raises(NoDataError, match=r"2015-10-16T13:06:00\.000 and 2015-10-16T13:06:01\.000"):
        src.get(1445000760.0, 1445000761.0)


def test_one_count_filled_per_energy():
    from sciqlop_vdf_mms.fpi import fill_one_count
    oc = np.full((1, 4, 2, 3), np.nan)
    oc[0, 0, 0, 0], oc[0, 1, 1, 0], oc[0, 2, 0, 0] = 1.0, 3.0, 2.0  # energy 0: median 2
    oc[0, 3, 1, 1] = 5.0                                           # energy 1: only one value
    out = fill_one_count(oc)
    assert out[0, 3, 0, 0] == 2.0 and out[0, 0, 0, 0] == 1.0       # filled / untouched
    assert np.all(out[0, :, :, 1] == 5.0)
    assert np.isnan(out[0, :, :, 2]).all()                         # no information at energy 2


def test_one_count_all_zero_energy_filled_along_energy():
    from sciqlop_vdf_mms.fpi import fill_one_count
    E = np.array([[100.0, 200.0, 400.0]])
    oc = np.full((1, 2, 2, 3), np.nan)
    oc[0, :, :, 0] = 4.0                               # finite at 100 eV only
    out = fill_one_count(oc, E)
    np.testing.assert_allclose(out[0, :, :, 1], 1.0)   # f1 ∝ E^-2: 4 * (100/200)^2
    np.testing.assert_allclose(out[0, :, :, 2], 0.25)
