from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class VelocityGrid:
    """Cubic Cartesian velocity grid: n cells per axis spanning [-vmax, vmax] km/s."""

    n: int
    vmax: float

    @property
    def dv(self) -> float:
        return 2.0 * self.vmax / self.n

    @property
    def centres(self) -> np.ndarray:
        edges = np.linspace(-self.vmax, self.vmax, self.n + 1)
        return 0.5 * (edges[:-1] + edges[1:])

    def nodes(self) -> np.ndarray:
        c = self.centres
        return np.stack(np.meshgrid(c, c, c, indexing="ij"), axis=-1)
