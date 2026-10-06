import numpy as np
import pytest
import speasy as spz
from sciqlop_vdf.core.pipeline import Options, compute_planes
from sciqlop_vdf_mms.fpi import FPISource

T0 = np.datetime64("2015-10-16T13:06:00", "ns").astype(np.int64) / 1e9


@pytest.mark.network
def test_density_matches_fpi_moments():
    batch = FPISource("mms1", "ion", "brst").get(T0, T0 + 1.0)
    assert batch.f.shape[1:] == (32, 16, 32)
    assert set(batch.rotations) == {"GSE"} and batch.b is not None and batch.v_bulk is not None
    t = float(batch.time_s[3])
    plane = compute_planes(batch, t, options=Options(grid_n=64)).planes[0]
    dv = plane.x[1] - plane.x[0]
    n_vdf = np.nansum(plane.z) * dv ** 2 * 1e-15
    mom = spz.get_data(spz.inventories.tree.cda.MMS.MMS1.DIS.MMS1_FPI_BRST_L2_DIS_MOMS.mms1_dis_numberdensity_brst,
                       "2015-10-16T13:06:00", "2015-10-16T13:06:01")
    tm = mom.time.astype("datetime64[ns]").astype(np.int64) / 1e9
    n_mom = float(mom.values[np.argmin(np.abs(tm - t))].squeeze())
    print(f"n_vdf={n_vdf:.3f} cm-3, n_mom={n_mom:.3f} cm-3")
    assert n_vdf == pytest.approx(n_mom, rel=0.2)


@pytest.mark.network
def test_bulk_velocity_matches_fpi_moments():
    """Density is blind to the look->velocity flip; the first moment is not."""
    batch = FPISource("mms1", "ion", "brst").get(T0, T0 + 1.0)
    t = float(batch.time_s[3])
    p = compute_planes(batch, t, options=Options(grid_n=64)).planes
    def mean(plane, axis):
        w = np.nan_to_num(plane.z)
        c = plane.x if axis == 0 else plane.y
        return float(np.sum(w.sum(axis=1 - axis) * c) / np.sum(w))
    v_vdf = np.array([mean(p[0], 0), mean(p[0], 1), mean(p[1], 1)])  # (vx, vy) from xy, vz from xz
    v_mom = batch.v_bulk[3]
    print(f"v_vdf={np.round(v_vdf, 1)} km/s, v_mom(DBCS)={np.round(v_mom, 1)} km/s")
    assert np.linalg.norm(v_vdf - v_mom) < 0.15 * np.linalg.norm(v_mom) + 20.0
