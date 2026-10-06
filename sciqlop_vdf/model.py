"""Data contract between VDF sources (instrument adapters) and the generic core."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable

import numpy as np

AMU_KG = 1.66053906660e-27
QE_C = 1.602176634e-19


class VDFError(ValueError):
    """Invalid VDF data or request."""


class NoDataError(VDFError):
    """No distribution available for the requested time or interval."""


class Cancelled(VDFError):
    """Computation abandoned because a newer request superseded it."""


@dataclass(frozen=True)
class VDFBatch:
    """A time series of spherical-bin velocity distributions.

    f: (Nt, Nphi, Ntheta, NE) in s^3/km^6; NaN = invalid, 0 = measured nothing.
    energy: (Nt, NE) eV bin centres. theta: (Nt, Ntheta) deg, polar angle of the
    velocity from native +z. phi: (Nt, Nphi) deg, azimuth of the velocity.
    rotations: name -> (Nt, 3, 3); rows are the frame axes in native coordinates.
    b: (Nt, 3) nT and v_bulk: (Nt, 3) km/s, both in the native frame.
    """

    time: np.ndarray
    f: np.ndarray
    energy: np.ndarray
    theta: np.ndarray
    phi: np.ndarray
    mass_amu: float
    charge: int
    native_frame: str
    rotations: Mapping[str, np.ndarray] = field(default_factory=dict)
    b: np.ndarray | None = None
    v_bulk: np.ndarray | None = None
    one_count: np.ndarray | None = None
    label: str = ""

    def __post_init__(self) -> None:
        nt = self.time.shape[0]
        if self.f.ndim != 4 or self.f.shape[0] != nt:
            raise VDFError(f"f must be (Nt={nt}, Nphi, Ntheta, NE), got {self.f.shape}")
        _, nphi, ntheta, ne = self.f.shape
        for name, arr, n in (("energy", self.energy, ne), ("theta", self.theta, ntheta), ("phi", self.phi, nphi)):
            if arr.shape != (nt, n):
                raise VDFError(f"{name} must be ({nt}, {n}), got {arr.shape}")
        for name, arr in (("b", self.b), ("v_bulk", self.v_bulk)):
            if arr is not None and arr.shape != (nt, 3):
                raise VDFError(f"{name} must be ({nt}, 3), got {arr.shape}")
        for name, r in self.rotations.items():
            if r.shape != (nt, 3, 3):
                raise VDFError(f"rotation '{name}' must be ({nt}, 3, 3), got {r.shape}")
        if self.one_count is not None and self.one_count.shape != self.f.shape:
            raise VDFError(f"one_count must have the shape of f {self.f.shape}, got {self.one_count.shape}")

    def __len__(self) -> int:
        return int(self.time.shape[0])

    @property
    def time_s(self) -> np.ndarray:
        return self.time.astype("datetime64[ns]").astype(np.int64) / 1e9


@runtime_checkable
class VDFSource(Protocol):
    name: str

    def get(self, start: float, stop: float) -> VDFBatch: ...

    def cadence(self) -> float: ...
