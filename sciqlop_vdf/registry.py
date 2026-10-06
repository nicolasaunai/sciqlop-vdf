"""Registry of VDF sources (Qt-free). Adapters register through the `sciqlop_vdf.sources` entry-point group."""
from __future__ import annotations

import importlib.metadata
import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .model import VDFSource

log = logging.getLogger(__name__)
ENTRY_POINT_GROUP = "sciqlop_vdf.sources"


@dataclass(frozen=True)
class SourceEntry:
    key: str
    label: str
    group: str
    factory: Callable[[], VDFSource]
    tags: tuple[str, ...] = field(default=())


_REGISTRY: dict[str, SourceEntry] = {}


def register_source(key: str, label: str, factory: Callable[[], VDFSource], group: str = "",
                    tags: Iterable[str] = ()) -> None:
    _REGISTRY.pop(key, None)
    _REGISTRY[key] = SourceEntry(key, label, group, factory, tuple(tags))


def sources() -> list[SourceEntry]:
    return list(_REGISTRY.values())


def get_source(key: str) -> SourceEntry:
    return _REGISTRY[key]


def clear() -> None:
    _REGISTRY.clear()


def discover_sources(entry_points=None) -> int:
    """Call every `sciqlop_vdf.sources` entry point's register(); a broken adapter is logged and skipped."""
    eps = entry_points if entry_points is not None else importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    ok = 0
    for ep in eps:
        try:
            ep.load()()
            ok += 1
        except Exception:
            log.exception("VDF source adapter %r failed to register", getattr(ep, "name", ep))
    return ok


def rank_sources(entries: list[SourceEntry], product_paths: list[str]) -> list[SourceEntry]:
    """Sources whose tags appear in the panel's product paths first (stable).

    Tags are ordered by importance (e.g. spacecraft, instrument, mode): tag i weighs len(tags) - i,
    so a same-spacecraft source outranks a same-mode source on another spacecraft."""
    text = " ".join(product_paths).upper()

    def score(e: SourceEntry) -> int:
        n = len(e.tags)
        return sum(n - i for i, t in enumerate(e.tags) if t.upper() in text)

    return sorted(entries, key=lambda e: -score(e))
