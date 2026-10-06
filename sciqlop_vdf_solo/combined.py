"""PAS protons + He++ in one velocity-space view, each species at its true velocity (Qt-free part).

PAS measures E/q only. Bins below a split E/q are read as protons, bins at or above as He++ (m/q = 2). The two
species cannot share one spherical grid (re-read alpha bins fall on the proton-equivalent energies of proton bins),
so each species is projected separately onto the same Cartesian grid and the planes are added. Reduced planes are
integrals, so the sum is exact; slice planes are layer means, so a cell where only one species is defined keeps that
species' value. The split is event specific: choose it between the highest proton-beam and lowest alpha-core E/q.
"""
from __future__ import annotations

import dataclasses

import numpy as np

from sciqlop_vdf.core.pipeline import Planes
from sciqlop_vdf.core.project import contour_levels
from sciqlop_vdf.model import VDFError


def sum_planes(a: Planes, b: Planes, contour_decades: float = 3.0, contour_n: int = 5, label: str | None = None) -> Planes:
    out = []
    for pa, pb in zip(a.planes, b.planes):
        if pa.x.shape != pb.x.shape or not (np.allclose(pa.x, pb.x) and np.allclose(pa.y, pb.y)):
            raise VDFError("cannot add planes computed on different velocity grids")
        za, zb = np.asarray(pa.z, float), np.asarray(pb.z, float)
        z = np.where(np.isnan(za) & np.isnan(zb), np.nan, np.nan_to_num(za) + np.nan_to_num(zb))
        out.append(dataclasses.replace(pa, z=z, levels=contour_levels(z, contour_decades, contour_n)))
    return dataclasses.replace(a, planes=tuple(out), label=a.label if label is None else label)


def grid_vmax(planes: Planes) -> float:
    """|v|max of the Cartesian grid a Planes was computed on (outer cell edge)."""
    c = np.asarray(planes.planes[0].x, float)
    return float(c[-1] + 0.5 * (c[1] - c[0]))
