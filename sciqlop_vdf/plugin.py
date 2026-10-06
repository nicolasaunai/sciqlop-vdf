"""SciQLop entry-point plugin (group `sciqlop.plugins`): discovers VDF sources, adds 'VDF ▾' buttons."""
from __future__ import annotations

import logging
from types import SimpleNamespace

log = logging.getLogger(__name__)


def load(main_window):
    from .registry import discover_sources, sources
    from .ui.attach import install_attach_buttons
    n = discover_sources()
    install_attach_buttons(main_window)
    log.info("VDF viewer: %d source adapter(s), %d source(s)", n, len(sources()))
    return SimpleNamespace(name="sciqlop_vdf", sources=[s.key for s in sources()])
