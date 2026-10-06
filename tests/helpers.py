import numpy as np
from sciqlop_vdf.model import AMU_KG, QE_C

ION = 1.007276


def fpi_like_bins(phi_offset=0.0, energy_scale=1.0):
    energy = np.logspace(np.log10(10.0), np.log10(30000.0), 32) * energy_scale
    theta = 5.625 + 11.25 * np.arange(16)
    phi = (5.625 + 11.25 * np.arange(32) + phi_offset) % 360.0
    return energy, theta, phi


def bin_velocities(energy, theta, phi, mass_amu=ION):
    """(Nphi, Ntheta, NE, 3) km/s velocity of each bin centre."""
    s = np.sqrt(2 * energy * QE_C / (mass_amu * AMU_KG)) / 1e3
    P, T, S = np.meshgrid(np.radians(phi), np.radians(theta), s, indexing="ij")
    return np.stack([S * np.sin(T) * np.cos(P), S * np.sin(T) * np.sin(P), S * np.cos(T)], -1)


def maxwellian_kms(v, n_cm3, t_ev, v0, mass_amu=ION):
    """Isotropic Maxwellian in s^3/km^6 at velocities v (..., 3) km/s."""
    m = mass_amu * AMU_KG
    kt = t_ev * QE_C
    a = m * 1e6 / (2 * kt)  # s^2/km^2
    w2 = np.sum((v - np.asarray(v0)) ** 2, axis=-1)
    return n_cm3 * 1e15 * (a / np.pi) ** 1.5 * np.exp(-a * w2)
