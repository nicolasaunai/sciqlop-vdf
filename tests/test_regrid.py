import numpy as np
import pytest
from sciqlop_vdf.core.grid import VelocityGrid
from sciqlop_vdf.core.regrid import regrid_one, speed_from_energy, energy_from_speed
from tests.helpers import ION, fpi_like_bins, bin_velocities, maxwellian_kms


def _maxwellian_on_bins(n=10.0, t=1000.0, v0=(300.0, -100.0, 50.0)):
    e, th, ph = fpi_like_bins()
    f = maxwellian_kms(bin_velocities(e, th, ph), n, t, v0)
    return f, e, th, ph


def test_grid_geometry():
    g = VelocityGrid(4, 100.0)
    np.testing.assert_allclose(g.centres, [-75, -25, 25, 75])
    assert g.dv == pytest.approx(50.0)
    assert g.nodes().shape == (4, 4, 4, 3)
    np.testing.assert_allclose(g.nodes()[0, 1, 2], [-75, -25, 25])


def test_energy_speed_roundtrip():
    s = speed_from_energy(1000.0, ION)
    assert s == pytest.approx(437.7, rel=1e-3)  # 1 keV proton
    assert energy_from_speed(s, ION) == pytest.approx(1000.0)


def test_regrid_recovers_density_and_peak():
    f, e, th, ph = _maxwellian_on_bins()
    g = VelocityGrid(64, float(speed_from_energy(e[-1], ION)))
    F = regrid_one(f, e, th, ph, ION, g.nodes())
    n = np.nansum(F) * g.dv ** 3 * 1e-15
    assert n == pytest.approx(10.0, rel=0.03)
    peak = g.centres[list(np.unravel_index(np.nanargmax(F), F.shape))]
    assert np.all(np.abs(peak - [300, -100, 50]) <= g.dv)


def test_regrid_beam_direction_sign():
    f, e, th, ph = _maxwellian_on_bins(t=20.0, v0=(600.0, 0.0, 0.0))
    g = VelocityGrid(64, 1000.0)
    F = regrid_one(f, e, th, ph, ION, g.nodes())
    i = np.unravel_index(np.nanargmax(F), F.shape)
    assert g.centres[i[0]] > 500


def test_regrid_outside_energy_range_is_nan():
    f, e, th, ph = _maxwellian_on_bins()
    vtop = float(speed_from_energy(e[-1], ION))
    F = regrid_one(f, e, th, ph, ION, np.array([[1.5 * vtop, 0, 0], [0.1, 0, 0]]))
    assert np.isnan(F[0]) and np.isnan(F[1])  # above top / below bottom energy


def test_regrid_phi_wraparound_no_seam():
    f, e, th, ph = _maxwellian_on_bins(t=200.0, v0=(500.0, 0.0, 0.0))  # centred on phi = 0
    g = VelocityGrid(64, 1000.0)
    F = regrid_one(f, e, th, ph, ION, g.nodes())
    k = np.argmin(np.abs(g.centres))  # vz ~ 0 layer
    plane = F[:, :, k]
    assert np.all(np.isfinite(plane[g.centres > 300][:, np.abs(g.centres) < 300]))
    np.testing.assert_allclose(plane, plane[:, ::-1], rtol=0.05, atol=1e-3 * np.nanmax(plane))
