"""Batch + time selection + options -> three projected planes."""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..model import Cancelled, VDFBatch, VDFError
from .average import select
from .frames import FIELD_ALIGNED, NATIVE, available_frames, axis_labels, field_aligned_basis
from .grid import VelocityGrid
from .project import contour_levels, reduce, slice_
from .regrid import bin_velocities, regrid_one, speed_from_energy

PAIRS = ((0, 1, 2), (0, 2, 1), (1, 2, 0))  # (x axis, y axis, collapsed axis)
UNITS = {"reduced": "s^2/km^5", "slice": "s^3/km^6"}


@dataclass(frozen=True)
class Options:
    frame: str = NATIVE
    bulk_frame: bool = False
    mode: str = "reduced"
    slice_halfwidth: float | None = None  # km/s; None -> half a cell (the two central cells)
    grid_n: int = 64
    vmax: float | None = None  # km/s; None -> speed of the highest energy step
    contour_decades: float = 3.0
    contour_n: int = 5
    max_gap: float | None = None  # s; for single-time selection
    one_count_mask: bool = False  # hide cells below the one-count level
    slice_point: tuple[float, float, float] = (0.0, 0.0, 0.0)  # km/s, frame axes (bulk-relative in bulk frame)


@dataclass(frozen=True)
class Plane:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray  # z[i, j] at (x[i], y[j])
    xlabel: str
    ylabel: str
    unit: str
    levels: list
    cut: str = ""  # slice mode off the origin: "<normal axis> = <v> km/s"


@dataclass(frozen=True)
class Planes:
    planes: tuple
    frame: str
    mode: str
    bulk_frame: bool
    t_start: float
    t_stop: float
    n_used: int
    label: str
    axes: tuple = ()  # the three frame axis labels


def _nanmean3(a: np.ndarray) -> np.ndarray:
    """Mean over samples ignoring NaN; all-NaN components stay NaN (callers raise VDFError)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=0)


AUTO_VMAX_FRACTION = 0.99  # 99.9 % reaches into one-count noise in burst data (M6 measurement)


def auto_vmax(batch: VDFBatch, idx, shift, fraction: float = AUTO_VMAX_FRACTION, margin: float = 1.1) -> float:
    """Speed |v - shift| enclosing `fraction` of the density of the selected distributions (each sample
    weighted equally), x margin, capped at the top-energy speed. Density weight of a bin ∝ f v³ dlnE sinθ."""
    top = float(speed_from_energy(np.nanmax(batch.energy[idx]), batch.mass_amu))
    speeds, weights = [], []
    for k in idx:
        f = np.nan_to_num(np.asarray(batch.f[k], float), nan=0.0)
        f[f < 0] = 0.0
        if not f.any():
            continue
        e = np.asarray(batch.energy[k], float)
        order = np.argsort(e)
        dl = np.empty_like(e)
        dl[order] = np.abs(np.gradient(np.log(e[order]))) if e.size > 1 else 1.0
        v = bin_velocities(e, batch.theta[k], batch.phi[k], batch.mass_amu)
        s3 = np.linalg.norm(v, axis=-1) ** 3
        w = f * s3 * np.sin(np.radians(batch.theta[k]))[None, :, None] * dl[None, None, :]
        if not w.sum() > 0:
            continue
        speeds.append(np.linalg.norm(v - shift, axis=-1).ravel())
        weights.append((w / w.sum()).ravel())
    if not speeds:
        return top
    sp, wt = np.concatenate(speeds), np.concatenate(weights)
    order = np.argsort(sp)
    cw = np.cumsum(wt[order])
    r = float(sp[order][min(np.searchsorted(cw, fraction * cw[-1]), sp.size - 1)])
    return min(top, margin * r)


def _validate(batch: VDFBatch, o: Options) -> None:
    if o.mode not in UNITS:
        raise VDFError(f"mode must be one of {sorted(UNITS)}, got {o.mode!r}")
    frames = available_frames(batch)
    if o.frame not in frames:
        raise VDFError(f"frame {o.frame!r} unavailable for {batch.label or 'this source'}; available: {frames}")
    if o.bulk_frame and batch.v_bulk is None:
        raise VDFError("bulk-frame requested but the source provides no bulk velocity")
    if o.one_count_mask and batch.one_count is None:
        raise VDFError("one-count mask requested but the source provides no one-count level")
    if len(o.slice_point) != 3 or not np.all(np.isfinite(np.asarray(o.slice_point, float))):
        raise VDFError(f"slice_point must be 3 finite velocities (km/s), got {o.slice_point!r}")


def compute_planes(batch: VDFBatch, t0: float, t1: float | None = None, options: Options = Options(),
                   should_cancel: Callable[[], bool] | None = None) -> Planes:
    """should_cancel is polled before each distribution; True raises Cancelled (long interval superseded)."""
    _validate(batch, options)
    ts_all = batch.time_s
    max_gap = options.max_gap
    if t1 is None and max_gap is None and ts_all.size >= 2:
        max_gap = 1.5 * float(np.median(np.diff(ts_all)))  # a marker in a data gap must not pick a far sample
    idx = select(ts_all, t0, t1, max_gap)

    v_mean = _nanmean3(batch.v_bulk[idx]) if batch.v_bulk is not None else None
    if options.bulk_frame and not np.all(np.isfinite(v_mean)):
        raise VDFError("bulk-frame requested but the bulk velocity is not finite over the selected distributions")
    shift = v_mean if options.bulk_frame else np.zeros(3)
    vmax = options.vmax or auto_vmax(batch, idx, shift)
    grid = VelocityGrid(options.grid_n, vmax)
    labels = axis_labels(options.frame, batch.native_frame)
    point = tuple(float(x) for x in options.slice_point)
    if options.mode == "slice":
        for i, p in enumerate(point):
            if abs(p) > vmax:
                raise VDFError(f"slice point {labels[i]} = {p:g} km/s is outside the grid (|v|max = {vmax:.0f} km/s)")
    show_cut = options.mode == "slice" and any(point)
    u = grid.nodes()
    fixed = None
    if options.frame == NATIVE:
        fixed = np.eye(3)
    elif options.frame == FIELD_ALIGNED:
        fixed = field_aligned_basis(_nanmean3(batch.b[idx]), v_mean)

    acc = np.zeros(u.shape[:-1]); cnt = np.zeros(u.shape[:-1])
    acc1 = np.zeros(u.shape[:-1]); cnt1 = np.zeros(u.shape[:-1])
    for k in idx:
        if should_cancel is not None and should_cancel():
            raise Cancelled("superseded by a newer request")
        R = fixed if fixed is not None else batch.rotations[options.frame][k]
        nodes = u @ R + shift
        F = regrid_one(batch.f[k], batch.energy[k], batch.theta[k], batch.phi[k], batch.mass_amu, nodes)
        ok = np.isfinite(F)
        acc[ok] += F[ok]; cnt[ok] += 1
        if options.one_count_mask:
            F1 = regrid_one(batch.one_count[k], batch.energy[k], batch.theta[k], batch.phi[k], batch.mass_amu, nodes)
            ok1 = np.isfinite(F1)
            acc1[ok1] += F1[ok1]; cnt1[ok1] += 1
    F = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    if options.one_count_mask:
        # F = acc/cnt, so one count in one of the cnt samples is mean(f1)/cnt; unknown f1 keeps the cell
        F1 = np.where((cnt1 > 0) & (cnt > 0), acc1 / np.maximum(cnt1, 1) / np.maximum(cnt, 1), np.nan)
        F = np.where(np.isfinite(F1) & (F < F1), np.nan, F)

    c = grid.centres
    half = options.slice_halfwidth if options.slice_halfwidth is not None else 0.5 * grid.dv
    planes = []
    for ax_x, ax_y, ax_z in PAIRS:
        z = reduce(F, ax_z, grid.dv) if options.mode == "reduced" else slice_(F, ax_z, c, half, point[ax_z])
        cut = f"{labels[ax_z]} = {point[ax_z]:g} km/s" if show_cut else ""
        planes.append(Plane(c, c, z, labels[ax_x], labels[ax_y], UNITS[options.mode],
                            contour_levels(z, options.contour_decades, options.contour_n), cut))
    ts = batch.time_s[idx]
    return Planes(tuple(planes), options.frame, options.mode, options.bulk_frame,
                  float(ts[0]), float(ts[-1]), int(idx.size), batch.label, tuple(labels))
