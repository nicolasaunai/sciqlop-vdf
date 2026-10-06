"""Solar Orbiter SWA-PAS L2 3D distributions (CDAWeb `SOLO_L2_SWA-PAS-VDF`) -> sciqlop_vdf.VDFBatch.

Verified on 2025-02-28 11:55-11:57 (114 x 1 s samples) against `SOLO_L2_SWA_PAS_GRND_MOM`:
- Azimuth/Elevation are LOOK directions in the PAS frame (unit look = (cos el cos az, cos el sin az, sin el));
  velocity = -look. With this, first moments rotated by `PAS_to_RTN` give V_R = +628 km/s vs +605 km/s
  (the velocity-direction hypothesis gives -639 km/s).
- `PAS_to_RTN` (Nt, 3, 3) maps PAS -> RTN: v_rtn = M @ v_pas, so its rows are the RTN axes in PAS coordinates.
- Agreement: direction 3.3 deg (median), |V| +4 %, n +11 % (proton part, E/q < 3.5 keV). Cause of the residual
  offset not identified (the same +4 % in speed appears between eflux peak energies and the ground moments).
- f in s^3 m^-6 -> x1e18 -> s^3 km^-6.
Limited field of view: the angle table is surrounded by NaN guard bins so the generic regrid (periodic in phi,
clamped in theta) leaves unseen directions empty instead of smearing the edge bins over the sky.
Approximations: the 1-D Azimuth/Elevation tables are used (the instrument's Full_azimuth varies with elevation by
<= ~2 deg, below the ~3 deg half-bin); the per-energy Elevation_correction (|.| <= 0.83 deg) is ignored; all ions are
treated as protons (He++ appears at sqrt(2) x its true speed); no one-count level (L2 VDF has no counts/errors).
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import numpy as np

from sciqlop_vdf.core.average import iso
from sciqlop_vdf.model import NoDataError, VDFBatch

log = logging.getLogger(__name__)

PROTON_AMU = 1.007276
# PAS measures E/q and converts to velocity with the proton mass. For another species (mass A_amu, charge Z) at
# the same E/q bin: kinetic energy = Z E/q, true speed v_s = v_p sqrt(Z m_p / m_s), and f ∝ counts v^-4 gives
# f_s = f_p (v_p / v_s)^4. He++: v = v_p * 0.7096, f x 3.946.
SPECIES = {"proton": (PROTON_AMU, 1), "alpha": (4.001506, 2)}
F_M6_TO_KM6 = 1e18
CADENCE_S = 1.0          # normal mode on 2025-02-28 (Half_interval 0.5 s); burst/snapshot differ
AUX_PAD_S = 30.0
FILL_ABOVE = 1e30
DATASET = "SOLO_L2_SWA_PAS_VDF"
MAG_PATH = ("MAG", "SOLO_L2_MAG_RTN_NORMAL", "B_RTN")
MOM_PATH = ("SWA_PAS", "SOLO_L2_SWA_PAS_GRND_MOM", "V_RTN")


def pas_look_to_velocity(elevation, azimuth):
    """Polar angle (from +z_PAS) and azimuth of the VELOCITY for PAS look elevation/azimuth (deg)."""
    el, az = np.asarray(elevation, float), np.asarray(azimuth, float)
    return 90.0 + el, np.mod(az + 180.0, 360.0)


def _pad_edges(centres) -> np.ndarray:
    """Add one guard centre beyond each end, one edge spacing away."""
    c = np.asarray(centres, float)
    return np.concatenate(([c[0] - (c[1] - c[0])], c, [c[-1] + (c[-1] - c[-2])]))


def _guard_fov(f) -> np.ndarray:
    """Surround the (az, el) table with NaN bins. The generic regrid wraps phi over 360 deg and clamps theta,
    which is right for full-sky instruments; PAS sees ~64 x 45 deg, so interpolation must hit NaN outside it
    (the outer half of each edge bin becomes NaN as well)."""
    nt, naz, nel, ne = f.shape
    out = np.full((nt, naz + 2, nel + 2, ne), np.nan)
    out[:, 1:-1, 1:-1, :] = f
    return out


def _interp_vec(aux, t_dst):
    if aux is None:
        return None
    t_src, x = np.asarray(aux[0], float), np.asarray(aux[1], float)
    if t_src.size == 0:
        return None
    return np.stack([np.interp(t_dst, t_src, x[:, i]) for i in range(3)], axis=1)


def pas_to_batch(*, time_s, f_m, energy, azimuth, elevation, pas_to_rtn,
                 b_rtn=None, v_rtn=None, species="proton", min_e_per_q=None, max_e_per_q=None,
                 label="SolO SWA-PAS") -> VDFBatch:
    """f_m: (Nt, Naz, Nel, NE) s^3 m^-6 with PAS's energy order (computed by PAS assuming protons); energy (NE,)
    eV per charge; azimuth (Naz,), elevation (Nel,) deg look directions; pas_to_rtn (Nt, 3, 3); b_rtn / v_rtn:
    optional (t_s, (n, 3)) in RTN. species: 'proton' or 'alpha' (re-interprets every bin as that species).
    min_e_per_q / max_e_per_q: eV; bins below / at-or-above are set to NaN (species separation by E/q)."""
    if species not in SPECIES:
        raise ValueError(f"unsupported species {species!r}; expected one of {list(SPECIES)}")
    mass, charge = SPECIES[species]
    f_scale = (charge * PROTON_AMU / mass) ** -2          # (v_p / v_s)^4
    time_s = np.asarray(time_s, float)
    nt = time_s.size
    energy = np.asarray(energy, float).ravel()
    order = np.argsort(energy)
    f = np.asarray(f_m, float)[..., order]
    if min_e_per_q is not None:
        f = np.where(energy[order] >= min_e_per_q, f, np.nan)
    if max_e_per_q is not None:
        f = np.where(energy[order] < max_e_per_q, f, np.nan)
    f = _guard_fov(np.where((f >= 0.0) & (f < FILL_ABOVE), f, np.nan) * (F_M6_TO_KM6 * f_scale))
    theta_v, phi_v = pas_look_to_velocity(_pad_edges(elevation), _pad_edges(azimuth))
    M = np.asarray(pas_to_rtn, float)                         # rows: RTN axes in PAS coordinates
    MT = np.transpose(M, (0, 2, 1))
    b = _interp_vec(b_rtn, time_s)
    v = _interp_vec(v_rtn, time_s)
    return VDFBatch(
        time=(time_s * 1e9).astype(np.int64).astype("datetime64[ns]"),
        f=f,
        energy=np.broadcast_to(charge * energy[order], (nt, energy.size)).copy(),   # kinetic energy, eV
        theta=np.broadcast_to(theta_v, (nt, theta_v.size)).copy(),
        phi=np.broadcast_to(phi_v, (nt, phi_v.size)).copy(),
        mass_amu=mass, charge=charge, native_frame="PAS",
        rotations={"RTN": M},
        b=None if b is None else np.einsum("tij,tj->ti", MT, b),
        v_bulk=None if v is None else np.einsum("tij,tj->ti", MT, v),
        one_count=None, label=label,
    )


def _utc(t: float) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def _time_s(var) -> np.ndarray:
    return var.time.astype("datetime64[ns]").astype(np.int64) / 1e9


class _DayCache:
    """Daily PAS VDF files are ~180 MB compressed / ~3 GB decoded and cannot be read by record range:
    keep the last decoded day(s) in memory."""

    def __init__(self, maxsize: int = 1):
        self.maxsize, self._d = maxsize, OrderedDict()

    def get(self, url, loader):
        if url in self._d:
            self._d.move_to_end(url)
            return self._d[url]
        val = loader(url)
        self._d[url] = val
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)
        return val


_CACHE = _DayCache(1)


def _load_day(url):
    import pycdfpp
    from speasy.core.any_files import any_loc_open
    c = pycdfpp.load(any_loc_open(url, cache_remote_files=True).read())
    t = pycdfpp.to_datetime64(c["Epoch"]).astype("datetime64[ns]").astype(np.int64) / 1e9
    return dict(
        time_s=t,
        f=np.asarray(c["vdf"].values),                         # float32, (Nt, Naz, Nel, NE)
        pas_to_rtn=np.asarray(c["PAS_to_RTN"].values, float),
        energy=np.asarray(c["Energy"].values, float).ravel(),
        azimuth=np.asarray(c["Azimuth"].values, float).ravel(),
        elevation=np.asarray(c["Elevation"].values, float).ravel(),
    )


def _day_urls(start: float, stop: float) -> list[str]:
    """Daily file URLs through speasy's CDAWeb direct-archive listing."""
    import speasy as spz
    import speasy.data_providers.cda as cda
    from speasy.core.direct_archive_downloader.direct_archive_downloader import RandomSplitDirectDownload
    ds = spz.inventories.tree.cda.Solar_Orbiter.SOLO.SWA_PAS.SOLO_L2_SWA_PAS_VDF
    p = cda.to_direct_archive_params(file_naming=ds.filenaming, subdivided_by=ds.subdividedby, url=ds.url)
    return RandomSplitDirectDownload.list_files(
        split_frequency=p["split_frequency"], url_pattern=p["url_pattern"],
        start_time=_utc(start), stop_time=_utc(stop), fname_regex=p["fname_regex"], date_format=p.get("date_format"))


class PASSource:
    def __init__(self, species: str = "proton", min_e_per_q: float | None = None, max_e_per_q: float | None = None):
        if species not in SPECIES:
            raise ValueError(f"unsupported species {species!r}")
        self.species, self.min_e_per_q, self.max_e_per_q = species, min_e_per_q, max_e_per_q
        self.name = "SolO SWA-PAS" if species == "proton" else f"SolO SWA-PAS as {species} (m/q={SPECIES[species][0] / SPECIES[species][1]:.2f})"
        if min_e_per_q is not None:
            self.name += f", E/q>{min_e_per_q / 1e3:g} keV"
        if max_e_per_q is not None:
            self.name += f", E/q<{max_e_per_q / 1e3:g} keV"

    def cadence(self) -> float:
        return CADENCE_S

    def _aux(self, start, stop, path):
        import speasy as spz
        try:
            node = spz.inventories.tree.cda.Solar_Orbiter.SOLO
            for p in path:
                node = getattr(node, p)
            var = spz.get_data(node, _utc(start - AUX_PAD_S), _utc(stop + AUX_PAD_S))
        except Exception as e:  # aux data is optional
            log.warning("could not fetch %s: %s", "/".join(path), e)
            return None
        if var is None or len(var.time) == 0:
            return None
        return _time_s(var), np.asarray(var.values, float)

    def get(self, start: float, stop: float) -> VDFBatch:
        parts = []
        for url in _day_urls(start, stop):
            day = _CACHE.get(url, _load_day)
            m = (day["time_s"] >= start) & (day["time_s"] <= stop)
            if m.any():
                parts.append((day, m))
        if not parts:
            raise NoDataError(f"no {self.name} distribution between {iso(start)} and {iso(stop)}")
        d0 = parts[0][0]
        return pas_to_batch(
            time_s=np.concatenate([d["time_s"][m] for d, m in parts]),
            f_m=np.concatenate([d["f"][m] for d, m in parts]),
            energy=d0["energy"], azimuth=d0["azimuth"], elevation=d0["elevation"],
            pas_to_rtn=np.concatenate([d["pas_to_rtn"][m] for d, m in parts]),
            b_rtn=self._aux(start, stop, MAG_PATH), v_rtn=self._aux(start, stop, MOM_PATH),
            species=self.species, min_e_per_q=self.min_e_per_q, max_e_per_q=self.max_e_per_q, label=self.name,
        )
