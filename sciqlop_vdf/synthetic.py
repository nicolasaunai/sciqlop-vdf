"""Synthetic drifting bi-Maxwellian on an FPI-like spherical grid (for tests and demos)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import AMU_KG, QE_C, VDFBatch


@dataclass
class SyntheticSource:
    n_cm3: float = 10.0
    t_par_ev: float = 1000.0
    t_perp_ev: float | None = None
    v_kms: tuple[float, float, float] = (300.0, -100.0, 50.0)
    b_nt: tuple[float, float, float] | None = (0.0, 0.0, 10.0)
    mass_amu: float = 1.007276
    cadence_s: float = 0.15
    alternate_tables: bool = True
    rotations: dict[str, np.ndarray] | None = None
    v_kms_aux: bool = True  # expose v_bulk in the batch
    one_count_level: float | None = None  # constant one-count level, s^3/km^6
    name: str = "synthetic"
    native_frame: str = "SYNTH"

    def cadence(self) -> float:
        return self.cadence_s

    def _bins(self, k: int):
        energy = np.logspace(np.log10(10.0), np.log10(30000.0), 32)
        phi = 5.625 + 11.25 * np.arange(32)
        if self.alternate_tables and k % 2:
            energy = energy * np.sqrt(energy[1] / energy[0])
            phi = phi + 2.8125
        theta = 5.625 + 11.25 * np.arange(16)
        return energy, theta, np.mod(phi, 360.0)

    def f_kms(self, v: np.ndarray) -> np.ndarray:
        m = self.mass_amu * AMU_KG
        t_perp = self.t_par_ev if self.t_perp_ev is None else self.t_perp_ev
        a_par = m * 1e6 / (2 * self.t_par_ev * QE_C)
        a_perp = m * 1e6 / (2 * t_perp * QE_C)
        bdir = np.array(self.b_nt if self.b_nt is not None else (0.0, 0.0, 1.0), float)
        bdir /= np.linalg.norm(bdir)
        w = v - np.asarray(self.v_kms)
        w_par = w @ bdir
        w_perp2 = np.sum(w * w, axis=-1) - w_par ** 2
        norm = self.n_cm3 * 1e15 * np.sqrt(a_par / np.pi) * (a_perp / np.pi)
        return norm * np.exp(-a_par * w_par ** 2 - a_perp * w_perp2)

    def get(self, start: float, stop: float) -> VDFBatch:
        t = np.arange(start, stop, self.cadence_s)
        nt = t.size
        f = np.empty((nt, 32, 16, 32)); E = np.empty((nt, 32)); TH = np.empty((nt, 16)); PH = np.empty((nt, 32))
        for k in range(nt):
            e, th, ph = self._bins(k)
            s = np.sqrt(2 * e * QE_C / (self.mass_amu * AMU_KG)) / 1e3
            P, T, S = np.meshgrid(np.radians(ph), np.radians(th), s, indexing="ij")
            v = np.stack([S * np.sin(T) * np.cos(P), S * np.sin(T) * np.sin(P), S * np.cos(T)], -1)
            f[k], E[k], TH[k], PH[k] = self.f_kms(v), e, th, ph
        rot = {name: np.broadcast_to(r, (nt, 3, 3)).copy() for name, r in (self.rotations or {}).items()}
        return VDFBatch(
            time=(t * 1e9).astype(np.int64).astype("datetime64[ns]"),
            f=f, energy=E, theta=TH, phi=PH, mass_amu=self.mass_amu, charge=1,
            native_frame=self.native_frame, rotations=rot,
            b=None if self.b_nt is None else np.tile(self.b_nt, (nt, 1)).astype(float),
            v_bulk=np.tile(self.v_kms, (nt, 1)).astype(float) if self.v_kms_aux else None,
            one_count=None if self.one_count_level is None else np.full_like(f, self.one_count_level),
            label=self.name,
        )
