"""Qt-free text for the VDF viewer: time readout, titles, status (unit-tested)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

_N_SUFFIX = re.compile(r"\s*\(N=\d+\)\s*$")
_ARROW = re.compile(r"\s*(?:→|->)\s*")
_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def fmt_time(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def readout(t0: float, t1: float | None, n: int | None = None) -> str:
    """Marker: full time. Interval: full start → time-of-day stop, optionally (N=…)."""
    if t1 is None:
        return fmt_time(t0)
    text = f"{fmt_time(t0)} → {fmt_time(t1)[11:]}"
    return f"{text} (N={n})" if n is not None else text


def _parse_dt(s: str) -> float:
    s = s.strip().replace("T", " ")
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    raise ValueError(f"not a time: {s!r} (expected YYYY-MM-DD HH:MM:SS[.mmm])")


def parse_readout(text: str, interval: bool) -> tuple[float, float | None]:
    """Inverse of readout(). Interval stop may be a bare time-of-day (same date as start)."""
    text = _N_SUFFIX.sub("", text).strip()
    if not interval:
        return _parse_dt(text), None
    parts = _ARROW.split(text)
    if len(parts) != 2:
        raise ValueError("expected 'start → stop'")
    start, stop = parts[0].strip(), parts[1].strip()
    t0 = _parse_dt(start)
    t1 = _parse_dt(stop if re.match(r"\d{4}-", stop) else f"{start.replace('T', ' ')[:10]} {stop}")
    if t1 <= t0:
        raise ValueError("stop must be after start")
    return t0, t1


def plane_title(plane) -> str:
    title = f"{plane.xlabel} – {plane.ylabel}"
    return f"{title}  ({plane.cut})" if plane.cut else title


def dock_title(source_label: str, panel_name: str) -> str:
    return f"VDF · {source_label} ↔ {panel_name}"


def status_computing(t0: float, t1: float | None) -> str:
    return f"computing … {readout(t0, t1)}"


def status_done(n: int, seconds: float) -> str:
    return f"done · {n} distribution{'' if n == 1 else 's'} · {seconds:.1f} s"
