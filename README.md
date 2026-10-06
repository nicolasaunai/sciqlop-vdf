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

**Requirements:** SciQLop ≥ 0.14 (tested with 0.14.0) · `git` on the PATH (the package is fetched from GitHub)
· network access to github.com, and to CDAWeb for the data.

SciQLop plugins are installed **per workspace**: each workspace has its own Python environment and a manifest
(`workspace.sciqlop`) listing its packages. Install through SciQLop so the package is recorded there; a plain
`pip install` is not recorded and disappears when SciQLop rebuilds the environment.

1. Start SciQLop and open the workspace you want the plugin in.
2. Open a notebook (or the IPython console) **in that workspace** and run — the quotes are required:

   ```
   %install "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.2.0"
   ```

   Expected output: `Installed and recorded: sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.2.0`.
   Drop `@v0.2.0` to follow the latest commit on `main` instead of the release.
3. **Restart SciQLop** (plugins are loaded at start-up).
4. Check:
   * `%workspace deps` lists `sciqlop-vdf @ git+…`;
   * every plot panel has a **VDF ▾** button at the right end of its bottom row; its menu lists the MMS FPI
     sources and *SolO SWA-PAS (protons)* / *SolO SWA-PAS as He++ (m/q=2)*.

<details>
<summary>Other ways to install</summary>

* **Python** (same effect as `%install`), in a cell of the workspace:

  ```python
  from SciQLop.user_api.packages import install_packages
  install_packages("sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.2.0")
  ```

* **Manifest by hand**: with SciQLop closed, add the line to the `requires` list of `workspace.sciqlop` in the
  workspace directory (`%workspace status` prints its path), then start SciQLop; it installs what the manifest lists.

  ```toml
  [dependencies]
  requires = [
      "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.2.0",
  ]
  ```

* **Update** to a newer release: run `%install` with the new tag, then restart.
</details>

## Quick start

* **Interactive:** plot any product on a panel, click **VDF ▾**, pick a source. An orange marker appears at the
  panel centre: drag it to step through distributions; the control bar above the time axis switches
  marker ↔ interval (averaging over a draggable blue span), frame (native / RTN or GSE / field-aligned), bulk
  frame, reduced ↔ slice, grid, |v|max and contours; **×** removes the viewer.
* **Worked example:** run [`notebooks/solo_2025-02-28_event.ipynb`](notebooks/solo_2025-02-28_event.ipynb) top to
  bottom (needs ~3 GB of free memory for the Solar Orbiter distributions).

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
