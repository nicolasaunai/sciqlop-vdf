"""MMS FPI (DIS/DES) distributions from CDAWeb via speasy -> sciqlop_vdf.VDFBatch."""
from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from sciqlop_vdf.core.average import iso
from sciqlop_vdf.model import NoDataError, VDFBatch

log = logging.getLogger(__name__)

SPECIES = {"ion": ("DIS", "dis", 1.007276, 1), "electron": ("DES", "des", 5.48579909e-4, -1)}
F_CM6_TO_KM6 = 1e30
CADENCE = {("ion", "brst"): 0.15, ("electron", "brst"): 0.03, ("ion", "fast"): 4.5, ("electron", "fast"): 4.5}
MEC_PAD_S = 60.0


def look_to_velocity(theta_look, phi_look):
    """FPI angles are look directions; the particle velocity is the antipode (pySPEDAS mms_get_fpi_dist)."""
    return 180.0 - np.asarray(theta_look, float), np.mod(np.asarray(phi_look, float) + 180.0, 360.0)


def _per_time(a, nt: int) -> np.ndarray:
    a = np.asarray(a, float)
    return np.broadcast_to(a, (nt, a.shape[-1])).copy() if a.ndim == 1 else a


def _interp_vec(aux, t_dst):
    if aux is None:
        return None
    t_src, x = np.asarray(aux[0], float), np.asarray(aux[1], float)
    if t_src.size == 0:
        return None
    return np.stack([np.interp(t_dst, t_src, x[:, i]) for i in range(3)], axis=1)


def _gse_rotation(quats, t_dst):
    if quats is None:
        return None
    t_q, q_dbcs, q_gse = (np.asarray(a, float) for a in quats)
    ok = (np.all(np.isfinite(q_dbcs), axis=1) & np.all(np.isfinite(q_gse), axis=1)
          & (np.linalg.norm(q_dbcs, axis=1) > 0) & (np.linalg.norm(q_gse, axis=1) > 0) & np.isfinite(t_q))
    if not ok.all():
        log.warning("dropping %d invalid MEC quaternion sample(s)", int((~ok).sum()))
    t_q, q_dbcs, q_gse = t_q[ok], q_dbcs[ok], q_gse[ok]
    t_q, first = np.unique(t_q, return_index=True)  # Slerp needs strictly increasing times
    q_dbcs, q_gse = q_dbcs[first], q_gse[first]
    if t_q.size == 0:
        log.warning("no valid MEC quaternion: GSE frame unavailable")
        return None
    if t_q.size == 1:
        r_d = Rotation.from_quat(np.repeat(q_dbcs, t_dst.size, 0))
        r_g = Rotation.from_quat(np.repeat(q_gse, t_dst.size, 0))
    else:
        tc = np.clip(t_dst, t_q[0], t_q[-1])
        r_d, r_g = Slerp(t_q, Rotation.from_quat(q_dbcs))(tc), Slerp(t_q, Rotation.from_quat(q_gse))(tc)
    return (r_g * r_d.inv()).as_matrix()


def fill_one_count(one_count: np.ndarray, energy: np.ndarray | None = None) -> np.ndarray:
    """σ²/f is undefined where f = 0. The one-count level depends mainly on energy, so:
    1. fill from the other angles at the same (time, energy) (nanmedian; ignores the θ dependence of the
       geometric factor);
    2. if `energy` (Nt, NE) is given, energies with no count at any angle are filled from the nearest
       energy with a value, scaled as f1 ∝ E⁻² (one count, constant ΔE/E: f ∝ C / v⁴)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN energies stay NaN at this stage
        med = np.nanmedian(one_count, axis=(1, 2))  # (Nt, NE)
    if energy is not None:
        E = np.broadcast_to(np.asarray(energy, float), med.shape)
        for t in range(med.shape[0]):
            ok = np.isfinite(med[t])
            if ok.any() and not ok.all():
                lE = np.log(E[t]); good = np.nonzero(ok)[0]
                for i in np.nonzero(~ok)[0]:
                    j = good[np.argmin(np.abs(lE[good] - lE[i]))]
                    med[t, i] = med[t, j] * (E[t, j] / E[t, i]) ** 2
    return np.where(np.isfinite(one_count), one_count, med[:, None, None, :])


def fpi_to_batch(*, time_s, f_cm, err_cm, energy, theta_look, phi_look, species,
                 b=None, v=None, quats=None, label="") -> VDFBatch:
    _, _, mass, charge = SPECIES[species]
    time_s = np.asarray(time_s, float)
    nt = time_s.size
    f_cm = np.asarray(f_cm, float)
    f = np.where(f_cm >= 0.0, f_cm, np.nan) * F_CM6_TO_KM6
    one_count = None
    if err_cm is not None:
        err = np.asarray(err_cm, float)
        with np.errstate(divide="ignore", invalid="ignore"):
            one_count = np.where((f_cm > 0) & np.isfinite(err) & (err > 0), err ** 2 / f_cm, np.nan) * F_CM6_TO_KM6
        one_count = fill_one_count(one_count, _per_time(energy, nt))
    theta_v, phi_v = look_to_velocity(theta_look, phi_look)
    rot = _gse_rotation(quats, time_s)
    return VDFBatch(
        time=(time_s * 1e9).astype(np.int64).astype("datetime64[ns]"),
        f=f, energy=_per_time(energy, nt), theta=_per_time(theta_v, nt), phi=_per_time(phi_v, nt),
        mass_amu=mass, charge=charge, native_frame="DBCS",
        rotations={} if rot is None else {"GSE": rot},
        b=_interp_vec(b, time_s), v_bulk=_interp_vec(v, time_s), one_count=one_count, label=label,
    )


def _utc(t: float) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def _time_s(var) -> np.ndarray:
    return var.time.astype("datetime64[ns]").astype(np.int64) / 1e9


class FPISource:
    def __init__(self, sc: str = "mms1", species: str = "ion", mode: str = "brst"):
        if species not in SPECIES or mode not in ("brst", "fast"):
            raise ValueError(f"unsupported species/mode {species}/{mode}")
        self.sc, self.species, self.mode = sc.lower(), species, mode
        inst = SPECIES[species][0]
        self.name = f"{self.sc.upper()} FPI-{inst} {mode}"

    def cadence(self) -> float:
        return CADENCE[(self.species, self.mode)]

    def _node(self, *path):
        import speasy as spz
        node = spz.inventories.tree.cda.MMS
        for p in path:
            node = getattr(node, p)
        return node

    def _get(self, start, stop, *path):
        import speasy as spz
        return spz.get_data(self._node(*path), _utc(start), _utc(stop))

    def _aux(self, start, stop, *path):
        try:
            var = self._get(start, stop, *path)
        except Exception as e:  # missing product or network error: aux data is optional
            log.warning("could not fetch %s: %s", "/".join(path), e)
            return None
        if var is None or len(var.time) == 0:
            return None
        return _time_s(var), np.asarray(var.values, float)

    def get(self, start: float, stop: float) -> VDFBatch:
        S, sc, M = self.sc.upper(), self.sc, self.mode.upper()
        inst, short, _, _ = SPECIES[self.species]
        dist_ds = f"{S}_FPI_{M}_L2_{inst}_DIST"
        dist = self._get(start, stop, S, inst, dist_ds, f"{sc}_{short}_dist_{self.mode}")
        if dist is None or len(dist.time) == 0:
            raise NoDataError(f"no {self.name} distribution between {iso(start)} and {iso(stop)}")
        err = self._get(start, stop, S, inst, dist_ds, f"{sc}_{short}_disterr_{self.mode}")
        err_values = err.values if err is not None and err.values.shape == dist.values.shape else None
        fgm = "BRST" if self.mode == "brst" else "SRVY"
        b = self._aux(start, stop, S, "FGM", f"{S}_FGM_{fgm}_L2", f"{sc}_fgm_b_dmpa_{fgm.lower()}_l2")
        v = self._aux(start, stop, S, inst, f"{S}_FPI_{M}_L2_{inst}_MOMS", f"{sc}_{short}_bulkv_dbcs_{self.mode}")
        mec = f"{S}_MEC_SRVY_L2_EPHT89D"
        qd = self._aux(start - MEC_PAD_S, stop + MEC_PAD_S, S, "MEC", mec, f"{sc}_mec_quat_eci_to_dbcs")
        qg = self._aux(start - MEC_PAD_S, stop + MEC_PAD_S, S, "MEC", mec, f"{sc}_mec_quat_eci_to_gse")
        quats = (qd[0], qd[1], qg[1]) if qd is not None and qg is not None and qd[0].size == qg[0].size else None
        ax = dist.axes
        return fpi_to_batch(
            time_s=_time_s(dist), f_cm=dist.values, err_cm=err_values,
            energy=ax[3].values, theta_look=ax[2].values, phi_look=ax[1].values,
            species=self.species, b=b, v=v, quats=quats, label=self.name,
        )
