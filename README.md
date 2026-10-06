# sciqlop-vdf

Velocity distribution function (VDF) viewer for [SciQLop](https://github.com/SciQLop/SciQLop).

It adds a **VDF ▾** button to every plot panel. Pick a source, and a row of three 2-D velocity-space planes
(reduced or sliced, with contours) appears under the panel, following a draggable time marker or averaged
over a draggable interval. Frames: instrument native, any frame the source provides (GSE, RTN, …), and
field-aligned, optionally in the plasma bulk frame.

| Source | Data (CDAWeb via speasy) | Notes |
|---|---|---|
| MMS1–4 FPI-DIS / FPI-DES, brst / fast | `MMSx_FPI_{BRST,FAST}_L2_{DIS,DES}_DIST` | one-count mask, GSE from MEC quaternions |
| Solar Orbiter SWA-PAS (protons) | `SOLO_L2_SWA_PAS_VDF` | native PAS frame + RTN |
| Solar Orbiter SWA-PAS as He²⁺ | same, re-read with m/q = 2 | see below |

## Install

In a SciQLop workspace (SciQLop ≥ 0.14), install the package with SciQLop's package installer so it is
recorded in the workspace manifest, e.g. from a notebook cell or the agent:

```
sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf
```

Restart SciQLop: every panel gets a **VDF ▾** button.

## Python API

```python
import sciqlop_vdf.ui.controller as vctl
import sciqlop_vdf.core.pipeline as vpipe
from sciqlop_vdf_solo.pas import PASSource

ctl = vctl.attach(panel, PASSource("proton"),
                  vpipe.Options(frame="field-aligned", bulk_frame=True, vmax=700.0), t=t_epoch_seconds)
ctl.set_mode("interval"); ctl.set_interval(t0, t1)   # average over an interval
ctl.set_mode("marker");   ctl.set_marker(t)          # single distribution
ctl.close()
```

## Solar Orbiter SWA-PAS: conventions (verified on 2025-02-28 11:55–11:57)

* `Azimuth` / `Elevation` are **look directions** in the PAS frame; velocity = −look. `PAS_to_RTN` rows are the RTN
  axes in PAS coordinates. VDF moments vs `SOLO_L2_SWA_PAS_GRND_MOM`: direction 3.3°, |V| +4 %, n +11 %
  (offset not explained).
* PAS sees ~64° × 45°: the angle table is padded with NaN guard bins so unseen directions stay empty.
* The archived f assumes **protons**; He²⁺ then appears at √2 × its speed. `PASSource("alpha")` re-reads every bin as
  He²⁺ (kinetic energy 2 E/q, m = 4.0015 amu, f × 3.95); `min_e_per_q` / `max_e_per_q` select species by E/q.
* Daily files are ~180 MB on disk and ~3 GB decoded; the last day is kept in memory.

## Example

[`notebooks/solo_2025-02-28_event.ipynb`](notebooks/solo_2025-02-28_event.ipynb) — case study of field-aligned proton
and alpha beams at a solar-wind current sheet (Solar Orbiter, 2025-02-28): locating the interval, identifying
the populations in the PAS spectra, and field-aligned VDFs with this plugin.

## Development

```
python -m pytest -q -W error::RuntimeWarning           # offline tests
env -u SPEASY_SKIP_INIT_PROVIDERS python -m pytest -m network   # CDAWeb tests
```

`sciqlop_vdf/` is instrument-agnostic and never imports an adapter (enforced by `tests/test_boundary.py`).
Adapters register sources through the `sciqlop_vdf.sources` entry-point group; see `docs/design.md`.

## License

MIT
