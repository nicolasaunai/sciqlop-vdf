"""Frame bases. Rows of a basis are the frame axes expressed in native coordinates."""
from __future__ import annotations

import numpy as np

from ..model import VDFBatch, VDFError

NATIVE = "native"
FIELD_ALIGNED = "field-aligned"


def field_aligned_basis(b, v=None) -> np.ndarray:
    """(e_par, e_perp1, e_perp2): e_par = b̂, e_perp1 ∝ b̂×(v×b̂) (E×B direction), e_perp2 = e_par×e_perp1."""
    b = np.asarray(b, float)
    nb = np.linalg.norm(b)
    if not np.isfinite(nb) or nb == 0.0:
        raise VDFError("field-aligned frame needs a finite, non-zero B")
    e_par = b / nb
    ref = None
    if v is not None and np.all(np.isfinite(v)):
        v = np.asarray(v, float)
        w = v - (v @ e_par) * e_par
        if np.linalg.norm(w) > 1e-6 * max(np.linalg.norm(v), 1e-12):
            ref = w
    if ref is None:
        x = np.array([1.0, 0.0, 0.0]) if abs(e_par[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        ref = x - (x @ e_par) * e_par
    e1 = ref / np.linalg.norm(ref)
    return np.vstack((e_par, e1, np.cross(e_par, e1)))


def available_frames(batch: VDFBatch) -> list[str]:
    frames = [NATIVE, *batch.rotations.keys()]
    if batch.b is not None:
        frames.append(FIELD_ALIGNED)
    return frames


def axis_labels(frame: str, native_frame: str) -> tuple[str, str, str]:
    if frame == FIELD_ALIGNED:
        return ("v∥", "v⊥1", "v⊥2")
    name = native_frame if frame == NATIVE else frame
    return (f"vx {name}", f"vy {name}", f"vz {name}")
