"""Spherical-bin distribution -> values at arbitrary Cartesian velocity nodes."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates

from ..model import AMU_KG, QE_C


def speed_from_energy(energy_ev, mass_amu: float):
    return np.sqrt(2.0 * np.asarray(energy_ev, dtype=float) * QE_C / (mass_amu * AMU_KG)) / 1e3


def energy_from_speed(speed_kms, mass_amu: float):
    return 0.5 * mass_amu * AMU_KG * (np.asarray(speed_kms, dtype=float) * 1e3) ** 2 / QE_C


def bin_velocities(energy, theta, phi, mass_amu: float) -> np.ndarray:
    """(Nphi, Ntheta, NE, 3) km/s velocity of each bin centre (angles = velocity directions, deg)."""
    s = speed_from_energy(energy, mass_amu)
    P, T, S = np.meshgrid(np.radians(phi), np.radians(theta), s, indexing="ij")
    return np.stack([S * np.sin(T) * np.cos(P), S * np.sin(T) * np.sin(P), S * np.cos(T)], -1)


def _periodic_index(angle_deg: np.ndarray, centres_sorted: np.ndarray) -> np.ndarray:
    """Fractional index into an array padded with one wrapped bin on each side."""
    n = centres_sorted.size
    ext = np.concatenate(([centres_sorted[-1] - 360.0], centres_sorted, [centres_sorted[0] + 360.0]))
    return np.interp(angle_deg, ext, np.arange(-1, n + 1, dtype=float)) + 1.0


def regrid_one(f, energy, theta, phi, mass_amu: float, v_native) -> np.ndarray:
    """Trilinear interpolation of one distribution in (phi, theta, log E) index space.

    Angles are velocity directions in degrees (theta polar from +z). Nodes whose energy
    lies more than half a bin outside the energy table are NaN.
    """
    energy = np.asarray(energy, float)
    theta = np.asarray(theta, float)
    phi = np.mod(np.asarray(phi, float), 360.0)
    ie, it, ip = np.argsort(energy), np.argsort(theta), np.argsort(phi)
    f = np.asarray(f, float)[ip][:, it][:, :, ie]
    e_s, t_s, p_s = energy[ie], theta[it], phi[ip]
    f_pad = np.concatenate((f[-1:], f, f[:1]), axis=0)

    v_native = np.asarray(v_native, float)
    shape = v_native.shape[:-1]
    v = v_native.reshape(-1, 3)
    speed = np.maximum(np.linalg.norm(v, axis=1), 1e-12)

    log_e = np.log(np.maximum(energy_from_speed(speed, mass_amu), 1e-300))
    log_c = np.log(e_s)
    lo = log_c[0] - 0.5 * (log_c[1] - log_c[0])
    hi = log_c[-1] + 0.5 * (log_c[-1] - log_c[-2])
    outside = (log_e < lo) | (log_e > hi)
    i_e = np.interp(log_e, log_c, np.arange(e_s.size, dtype=float))

    th = np.degrees(np.arccos(np.clip(v[:, 2] / speed, -1.0, 1.0)))
    i_t = np.interp(th, t_s, np.arange(t_s.size, dtype=float))

    ph = np.mod(np.degrees(np.arctan2(v[:, 1], v[:, 0])), 360.0)
    i_p = _periodic_index(ph, p_s)

    out = map_coordinates(f_pad, np.vstack((i_p, i_t, i_e)), order=1, mode="nearest")
    out[outside] = np.nan
    return out.reshape(shape)
