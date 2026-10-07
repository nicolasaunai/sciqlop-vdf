"""Marker / interval / options -> worker thread -> viewer."""
from __future__ import annotations

import dataclasses
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal
from SciQLop.user_api.threading import on_main_thread, unwrap

from ..core.cache import WindowCache
from ..core.frames import available_frames
from ..core.pipeline import Options, compute_planes
from ..model import Cancelled, NoDataError, VDFError
from .controls import VDFControls
from .dock import VDFDock
from .format import dock_title, readout, status_computing, status_done
from .interval import IntervalSpan
from .marker import SyncedMarker
from .vdf_widget import VDFWidget
from .viewer import PlaneArea

log = logging.getLogger(__name__)
DEBOUNCE_MS = 200
MODES = ("marker", "interval")


class _Bridge(QObject):
    done = Signal(int, object)
    failed = Signal(int, str, bool)  # generation, message, clear plots (no data) vs keep last image


class VDFController:
    """Create with attach(); all public methods run on the GUI thread."""

    def __init__(self, panel, source, options: Options = Options(), t: float | None = None):
        self._panel, self._source, self._options = panel, source, options
        self._cache = WindowCache(source)
        self._viewer = PlaneArea()
        self._controls = VDFControls()
        self._controls.set_values(options, "marker")
        self._widget = VDFWidget(self._controls, self._viewer)
        self._dock = VDFDock(self._widget, dock_title(self._source_label(), panel.name), panel.name)
        if not self._dock.placed_beside:
            self._widget.set_status("could not place the viewer beside its panel; opened on the right")
        self._dock.closed.connect(self.close)
        self._controls.options_changed.connect(lambda d: self.set_options(**d))
        self._controls.mode_changed.connect(self.set_mode)
        self._controls.close_requested.connect(self.close)
        self._controls.time_edited.connect(self._on_time_edited)
        self._controls.plane_choice_changed.connect(self._viewer.set_plane_choice)
        self._t_submit = 0.0
        self._last_request = (0.0, None)
        if t is None:
            tr = panel.time_range
            t = 0.5 * (tr.start() + tr.stop())
        self._marker = SyncedMarker(panel, t, lambda _t: self._schedule())
        self._span: IntervalSpan | None = None
        self._mode = "marker"
        self._gen = 0
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vdf")
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_done)
        self._bridge.failed.connect(self._on_failed)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._submit)
        self._closed = False
        # Panel closed by the user: stop everything without touching its (dying) Qt children.
        unwrap(panel._impl).destroyed.connect(self._on_panel_destroyed)
        self._schedule()

    def _on_panel_destroyed(self, *_):
        if self._closed:
            return
        self._shutdown()  # never touch the dying panel's children (marker, span)
        self._dock.close()

    def _source_label(self) -> str:
        return getattr(self, "label", None) or getattr(self._source, "name", None) or type(self._source).__name__

    def _on_time_edited(self, value) -> None:
        t0, t1 = value
        if t1 is None:
            self.set_marker(t0)
        else:
            self.set_interval(t0, t1)

    def _shutdown(self) -> None:
        self._closed = True
        self._gen += 1  # invalidate in-flight results
        self._timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def options(self) -> Options:
        return self._options

    @property
    def viewer(self) -> PlaneArea:
        return self._viewer

    @property
    def widget(self) -> VDFWidget:
        return self._widget

    @property
    def dock(self) -> VDFDock:
        return self._dock

    @on_main_thread
    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        if mode == "interval" and self._span is None:
            t, w = self._marker.value, 5.0 * self._source.cadence()
            self._span = IntervalSpan(self._panel, t - w, t + w, lambda a, b: self._schedule())
        elif mode == "marker" and self._span is not None:
            self._span.remove()
            self._span = None
        self._mode = mode
        self._controls.set_values(self._options, self._mode)
        self._schedule()

    @on_main_thread
    def set_marker(self, t: float) -> None:
        self._marker.set_value(t)

    @on_main_thread
    def set_interval(self, t0: float, t1: float) -> None:
        if self._span is None:
            raise VDFError("set_mode('interval') first")
        self._span.set_range(t0, t1)

    @on_main_thread
    def set_options(self, **changes) -> None:
        self._options = dataclasses.replace(self._options, **changes)
        self._controls.set_values(self._options, self._mode)
        self._schedule()

    @on_main_thread
    def close(self) -> None:
        if self._closed:
            return
        self._shutdown()
        self._marker.remove()
        if self._span is not None:
            self._span.remove()
            self._span = None
        self._dock.close()

    def _request(self) -> tuple[float, float | None]:
        if self._mode == "interval" and self._span is not None:
            return self._span.range
        return self._marker.value, None

    def _schedule(self) -> None:
        if not self._closed:
            self._timer.start()  # restart: debounce

    def _submit(self) -> None:
        if self._closed:
            return
        self._gen += 1
        gen = self._gen
        t0, t1 = self._request()
        self._t_submit = time.monotonic()
        self._last_request = (t0, t1)
        self._controls.set_readout(readout(t0, t1))
        self._widget.set_status(status_computing(t0, t1))
        self._pool.submit(self._work, gen, t0, t1, self._options)

    def _work(self, gen: int, t0: float, t1: float | None, options: Options) -> None:
        if gen != self._gen:
            return  # superseded before it started
        superseded = lambda: gen != self._gen  # noqa: E731 — polled between distributions
        try:
            batch = self._cache.batch_for(t0, t1)
            planes = compute_planes(batch, t0, t1, options, should_cancel=superseded)
        except Cancelled:
            return
        except NoDataError as e:
            self._bridge.failed.emit(gen, str(e), True)
            return
        except VDFError as e:
            self._bridge.failed.emit(gen, str(e), False)
            return
        except Exception as e:  # network, parsing: report, keep last image, never kill the worker
            log.exception("VDF computation failed")
            self._bridge.failed.emit(gen, f"{type(e).__name__}: {e}", False)
            return
        self._bridge.done.emit(gen, (planes, available_frames(batch)))

    def _on_done(self, gen: int, payload) -> None:
        if gen != self._gen or self._closed:
            return
        planes, frames = payload
        self._controls.set_frames(frames, self._options.frame)
        self._controls.set_axes(planes.axes)
        t0, t1 = self._last_request
        try:
            self._viewer.display(planes, self._options.display_decades)
        except Exception as e:  # never leave "computing …" behind
            log.exception("VDF display failed")
            self._widget.set_status(f"display error: {type(e).__name__}: {e}", error=True)
            return
        self._controls.set_readout(readout(t0, t1, planes.n_used if t1 is not None else None))
        self._widget.set_status(status_done(planes.n_used, time.monotonic() - self._t_submit))

    def _on_failed(self, gen: int, message: str, clear: bool) -> None:
        if gen == self._gen and not self._closed:
            if clear:
                self._viewer.clear()
            self._widget.set_status(message, error=not clear)


@on_main_thread
def attach(panel, source, options: Options = Options(), t: float | None = None) -> VDFController:
    """Open a VDF viewer dock beside the panel, with a marker at t (default: panel centre)."""
    return VDFController(panel, source, options, t)
