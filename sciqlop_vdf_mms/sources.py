"""Registers the MMS FPI sources with sciqlop_vdf (entry point `sciqlop_vdf.sources: mms_fpi`)."""
from __future__ import annotations

from sciqlop_vdf.registry import register_source

from .fpi import SPECIES, FPISource


def register() -> None:
    for sc in ("mms1", "mms2", "mms3", "mms4"):
        for species in ("ion", "electron"):
            inst = SPECIES[species][0]
            for mode in ("brst", "fast"):
                register_source(f"mms/{sc}/{species}/{mode}", f"{sc.upper()} FPI-{inst} {mode}",
                                lambda sc=sc, species=species, mode=mode: FPISource(sc, species, mode),
                                group="MMS", tags=(sc.upper(), inst, mode.upper()))
