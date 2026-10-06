"""Registers the Solar Orbiter SWA-PAS sources with sciqlop_vdf (entry point `sciqlop_vdf.sources: solo_pas`)."""
from __future__ import annotations

from sciqlop_vdf.registry import register_source

from .pas import PASSource


def register() -> None:
    register_source("solo/swa/pas", "SolO SWA-PAS (protons)", PASSource, group="Solar Orbiter",
                    tags=("SOLAR_ORBITER", "SWA_PAS", "PAS"))
    register_source("solo/swa/pas/alpha", "SolO SWA-PAS as He++ (m/q=2)", lambda: PASSource("alpha"),
                    group="Solar Orbiter", tags=("SOLAR_ORBITER", "SWA_PAS", "PAS"))
