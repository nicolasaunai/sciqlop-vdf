"""One VDF viewer showing PAS protons (E/q < split) + He++ (E/q >= split), each at its true velocity."""
from __future__ import annotations

import dataclasses
import logging

from SciQLop.user_api.threading import on_main_thread

from sciqlop_vdf.core.cache import WindowCache
from sciqlop_vdf.core.frames import available_frames
from sciqlop_vdf.core.pipeline import Options, compute_planes
from sciqlop_vdf.model import Cancelled, NoDataError, VDFError
from sciqlop_vdf.ui.controller import VDFController

from .combined import grid_vmax, sum_planes
from .pas import PASSource

log = logging.getLogger(__name__)


class CombinedPASController(VDFController):
    def __init__(self, panel, split_e_per_q: float, options: Options = Options(), t: float | None = None):
        self.split = float(split_e_per_q)
        self._alpha_cache = WindowCache(PASSource("alpha", min_e_per_q=self.split))
        self.label = f"SolO SWA-PAS: p (E/q<{self.split / 1e3:g} keV) + He++ (E/q≥{self.split / 1e3:g} keV)"
        super().__init__(panel, PASSource("proton", max_e_per_q=self.split), options, t)

    def _work(self, gen: int, t0: float, t1: float | None, options: Options) -> None:
        if gen != self._gen:
            return
        superseded = lambda: gen != self._gen  # noqa: E731
        try:
            bp = self._cache.batch_for(t0, t1)
            ba = self._alpha_cache.batch_for(t0, t1)
            pp = compute_planes(bp, t0, t1, options, should_cancel=superseded)
            # same Cartesian grid for both species (auto |v|max is taken from the proton part)
            pa = compute_planes(ba, t0, t1, dataclasses.replace(options, vmax=grid_vmax(pp)), should_cancel=superseded)
            planes = sum_planes(pp, pa, options.contour_decades, options.contour_n, label=self.label)
        except Cancelled:
            return
        except NoDataError as e:
            self._bridge.failed.emit(gen, str(e), True)
            return
        except VDFError as e:
            self._bridge.failed.emit(gen, str(e), False)
            return
        except Exception as e:
            log.exception("combined PAS VDF computation failed")
            self._bridge.failed.emit(gen, f"{type(e).__name__}: {e}", False)
            return
        self._bridge.done.emit(gen, (planes, available_frames(bp)))


@on_main_thread
def attach_combined(panel, split_e_per_q: float, options: Options = Options(), t: float | None = None) -> CombinedPASController:
    return CombinedPASController(panel, split_e_per_q, options, t)
