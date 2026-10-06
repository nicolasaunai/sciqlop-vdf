# SciQLop VDF viewer — design

Date: 2026-10-05 · Author: N. Aunai (design), Claude (drafting) · Status: approved in chat, pending review of this file

## 1. Purpose

Inside a SciQLop plot panel, show a velocity distribution function (VDF) as 2D colormaps with
contours in three projection planes, for:

- the time under a user-placed vertical marker (closest distribution), or
- an average over a user-selected interval (same interaction as catalog event creation).

The first instrument is MMS FPI-DIS (ions). The representation and interaction workflow must
be instrument-agnostic: adding an instrument must not touch the generic code.

## 2. Verified facts (2026-10-05, live session, SciQLop 0.13.0, speasy 1.8.1)

### 2.1 MMS FPI-DIS via CDA

- Product tree path: `speasy//cda//MMS//MMS1//DIS//MMS1_FPI_BRST_L2_DIS_DIST//mms1_dis_dist_brst`
  (speasy uid `cda/MMS1_FPI_BRST_L2_DIS-DIST/mms1_dis_dist_brst` — note the `-DIST` dash).
  Fast mode: `MMS1_FPI_FAST_L2_DIS_DIST//mms1_dis_dist_fast`.
- Burst, 2015-10-16 13:06:00–13:06:05: values `(33, 32, 16, 32)` = (t, φ, θ, E), cadence 150 ms.
  - `mms1_dis_phi_brst` (t, 32), deg, varies per sample (4.375°, then 7.1875°, …).
  - `mms1_dis_theta_brst` (16,), deg, 5.625–174.375 (polar angle).
  - `mms1_dis_energy_brst` (t, 32), eV, alternates between two step tables
    (lowest step 12.06 vs 10.64 eV, top 2.83e4 eV).
- Fast: `(13, 32, 16, 32)`, cadence 4.5 s, φ (32,) fixed, θ (16,), energy (t, 32).
- `UNITS = "phase-space density"`; magnitudes 2e-27 to 1.6e-20 match s³/cm⁶. FILLVAL -1e31.
  74 % of bins are 0 in the 5 s window.
- Not exposed in the CDA tree: energy_delta, start_delta_time, counts. `mms1_dis_disterr_brst` is
  exposed. If Poisson: N = (f/σ)², one-count level f₁ = σ²/f (inference; verify in M0/M2).
- Angles are given in DBCS. Auxiliary data: `MMS1_FGM_BRST_L2//mms1_fgm_b_dmpa_brst_l2` (DMPA ≈ DBCS,
  standard approximation, to be stated in the UI), `MMS1_FPI_BRST_L2_DIS_MOMS//mms1_dis_bulkv_dbcs_brst`,
  `mms1_dis_numberdensity_brst`.

### 2.2 SciQLop

- Plugins are folders with `plugin.json` and `__init__.py` exposing `load(main_window)`. They are
  searched in the bundled folder, the user plugins folder (`~/Library/Application Support/sciqlop/plugins`)
  and `extra_plugins_folders`. Entry points in group `sciqlop.plugins` also work
  (`SciQLop/components/plugins/backend/loader/loader.py`).
- Virtual products: only `Scalar`, `Vector`, `MultiComponent`, `Spectrogram`. **No distribution type.**
  A VP therefore cannot carry the 4D VDF; it is used only as the product-tree hook (§4.3).
- `SciQLopColorMap` has native contours: `set_contour_levels`, `set_auto_contour_levels`,
  `set_contour_labels_enabled`, `set_contour_color`, `set_contour_width`.
- Panel: `span_created` signal, `set_span_creation_enabled` (catalog Shift-click mechanism),
  `MultiPlotsVerticalSpan` (draggable, `range_changed`), `time_range_changed`.
- No panel-wide vertical line. Per-plot `SciQLopVerticalLine` with `position_changed`.
- `PlotPanel.add_sub_panel(orientation)` for placing the viewer inside the panel.

### 2.3 velocirap (reference for user expectations, not ported)

SolO PAS / PSP SPAN-I. Field-aligned basis `[b̂, b̂×(û×b̂), −û×b̂]`; regridding with
`RegularGridInterpolator`; reduced VDFs (integrate along the 3rd axis); 3×3 corner plot (1D on the
diagonal); LogNorm + 4 log contours over 3 decades below max; ghost-bin removal; bi-Maxwellian
overlay from moments. No averaging, no slices, no φ wrap-around, no one-count level.

## 3. Requirements

R1. Three 2D colormaps (one per plane of the active frame), log colour scale, contours.
R2. Toggle reduced (∫ f dv₃, s²/km⁵) / slice (mean of f over |v₃| < Δ, s³/km⁶).
R3. Single time: distribution closest to a draggable vertical marker shown on all time-series plots of the panel.
R4. Interval: average of all distributions whose time is in [t₀, t₁]; interval set by Shift-click span creation, then draggable.
R5. Frames: native (instrument), any rotation the source provides (MMS: GSE), field-aligned
    (e∥ = b̂, e⊥1 = b̂×(û×b̂)/|·|, e⊥2 = e∥×e⊥1); optional bulk-velocity subtraction.
R6. Controls: source, frame, bulk-frame toggle, reduced/slice, Δ, grid size, |v| range, number of contour levels, one-count contour on/off.
R7. GUI never blocks on fetching or regridding.
R8. Generic code has no mission knowledge; enforced by a test.
R9. Units in the UI: km/s, s³/km⁶ (slice), s²/km⁵ (reduced).

Out of scope for v1: 1D cuts, bi-Maxwellian overlay, ghost removal, PHARE/simulation input, movies.

## 4. Architecture

```
sciqlop_vdf/                     project root (this folder)
  docs/                          design.md, plan.md
  sciqlop_vdf/                   GENERIC — no mission code
    model.py                     VDFBatch, VDFSource protocol
    registry.py                  register_source / get_source / sources (explicit; entry points later, §7 O5)
    core/                        numpy/scipy only, no Qt
      grid.py                    VelocityGrid (Cartesian)
      regrid.py                  spherical bins -> Cartesian grid (per distribution)
      frames.py                  bases: native, provided rotations, field-aligned; bulk shift
      average.py                 interval selection + NaN-aware mean
      project.py                 reduced / slice, contour levels
      pipeline.py                compute_planes(batch, t0, t1, options) -> Planes
    ui/                          Qt / SciQLop
      viewer.py                  sub-panel, 3 colormaps, contours
      marker.py                  synced vertical lines
      interval.py                span creation + draggable span
      controls.py                options widget
      controller.py              wires marker/interval/options -> worker -> viewer
    synthetic.py                 SyntheticSource (drifting bi-Maxwellian on an FPI-like grid)
  sciqlop_vdf_mms/               MMS ADAPTER
    fpi.py                       FPISource(sc, species, mode)
    vp.py                        omni energy spectrogram VPs (tree hook)
  plugin/sciqlop_vdf_plugin/     plugin.json + __init__.load(main_window) (M7)
  tests/
  notebooks/vdf_dev.ipynb
```

### 4.1 Contract (`model.py`)

```python
@dataclass(frozen=True)
class VDFBatch:
    time: np.ndarray            # (Nt,) datetime64[ns]
    f: np.ndarray               # (Nt, Nphi, Ntheta, NE) s^3/km^6, NaN = invalid, 0 allowed
    energy: np.ndarray          # (Nt, NE) eV, bin centres
    theta: np.ndarray           # (Nt, Ntheta) deg, polar angle of VELOCITY from native +z
    phi: np.ndarray             # (Nt, Nphi) deg, azimuth of VELOCITY in native x-y
    mass_amu: float
    charge: int
    native_frame: str           # e.g. "DBCS"
    rotations: Mapping[str, np.ndarray] = {}   # name -> (Nt,3,3), v_frame = R @ v_native
    b: np.ndarray | None = None # (Nt,3) nT, native frame
    v_bulk: np.ndarray | None = None  # (Nt,3) km/s, native frame
    one_count: np.ndarray | None = None  # same shape as f
    label: str = ""

class VDFSource(Protocol):
    name: str                   # "MMS1 FPI-DIS brst"
    def get(self, start: float, stop: float) -> VDFBatch: ...   # POSIX seconds
    def cadence(self) -> float: ...                              # seconds
```

Sources convert to velocity directions and SI-derived km/s units **before** returning; the
generic code never flips signs or converts instrument units.

### 4.2 Algorithm

1. Grid: cubic Cartesian grid, `n` cells per axis (default 64), half-width `vmax` km/s
   (default: speed of the highest energy step).
2. For each distribution k in [t₀, t₁] (or the closest one to t):
   - basis R_k (3×3, rows = frame axes in native coords) from the chosen frame;
   - optional bulk shift: grid node u in frame → v_native = R_kᵀ u + V_k;
   - (|v|, θ, φ) of each node → fractional bin indices (E index via log-energy interpolation on the
     k-th energy table; θ index linear; φ index linear with periodic wrap);
   - f at the node = trilinear interpolation in index space; NaN outside [E_min, E_max].
3. Average: NaN-aware mean over k on the common grid (handles burst table alternation).
   B and V for the frame are the mean over the same distributions. one_count averages / N.
4. Project: reduced = Σ f·dv along axis 3 (NaN treated as 0, × 1 km/s cell size);
   slice = nanmean over cells with |u₃| < Δ.
5. Contours: `levels = logspace(log10(max) - decades, log10(max), n_levels)`, default 3 decades, 5 levels.

### 4.3 MMS adapter

- `FPISource(sc="mms1", species="ion"|"electron", mode="brst"|"fast")`.
- Fetch dist, disterr, energy/θ/φ axes (from the dist variable's axes), FGM B (`b_dmpa`), FPI bulk V
  (`bulkv_dbcs`), MEC quaternions → `rotations["GSE"]` (§7 O2).
- Conversions: f × 1e30 (s³/cm⁶ → s³/km⁶); negative / fill → NaN; θ_v = 180° − θ, φ_v = (φ + 180°) mod 360°
  (§7 O1); one_count = σ²/f × 1e30 where f > 0; mass 1.007276 amu (ion), 5.48580e-4 amu (electron).
- B, V interpolated onto the distribution times.
- `vp.py` registers one `Spectrogram` VP per (sc, species, mode): the omnidirectional mean f vs
  energy, so the source appears in the product tree and gives time context.

### 4.4 UI flow

`Attach VDF viewer` (panel menu, or `attach(panel, source)` from Python) →
creates a horizontal sub-panel with 3 XY colormaps + a controls widget → creates the marker
(default: panel centre). Marker move / span change / option change → debounced (200 ms) job on a
worker thread: `source.get` (cached per window) → `compute_planes` → results marshalled to the GUI
thread → `colormap.set_data`, contour levels, titles (time or interval, frame, N distributions).

## 5. Error handling

- No distribution in range → overlay message on the viewer ("no data in …"), plots cleared.
- Fetch failure → overlay error with the exception text; previous image kept.
- Missing B → field-aligned frames disabled in the controls; missing V → bulk-frame toggle disabled.
- All-NaN projection → overlay warning.

## 6. Testing

- `core/` and adapters: pytest, synthetic bi-Maxwellian on an FPI-like grid (n, V, T known):
  recovered density from the Cartesian grid within 3 %, peak within one cell of V, reduced
  plane integral = n within 3 %, slice symmetric for an isotropic Maxwellian, bases orthonormal.
- Sign convention: a cold beam along native +x appears at u_x > 0.
- Import boundary: `sciqlop_vdf` must not import `sciqlop_vdf_mms` (test greps the AST).
- MMS integration (network, marked): density from f vs `mms1_dis_numberdensity_brst`, 2015-10-16 13:06:00–13:06:05, within 20 %.
- UI: manual checks via screenshots in the dev notebook.

## 7. M0 spike results (2026-10-05)

- O1 Look direction → velocity: **antipode**. pySPEDAS `pyspedas/projects/mms/fpi_tools/mms_get_fpi_dist.py`
  l.130, 169–170: θ_lat = 90 − θ, then φ → φ + 180, θ_lat → −θ_lat. In this design's polar-angle
  convention: θ_v = 180° − θ, φ_v = (φ + 180°) mod 360°. (Primary source, FPI Data Products Guide,
  not yet read; pySPEDAS is the community reference implementation.)
  **Verified against data (M2):** first moment of the regridded VDF, MMS1 brst 2015-10-16 13:06:00.585,
  (−147.4, 150.6, −132.3) km/s vs `mms1_dis_bulkv_dbcs_brst` (−145.9, 153.0, −133.8) km/s; with the flip
  disabled the sign reverses exactly. Density 11.31 vs `mms1_dis_numberdensity_brst` 11.12 cm⁻³ (1.7 %).
- O2 DBCS→GSE: `MMS1_MEC_SRVY_L2_EPHT89D//mms1_mec_quat_eci_to_dbcs` and `…_eci_to_gse`, scalar-last
  (qx, qy, qz, qw), 30 s cadence. With scipy `Rotation.from_quat`, R = R_gse · R_dbcs⁻¹ maps
  `mms1_dis_bulkv_dbcs_brst` to `mms1_dis_bulkv_gse_brst` with 0.1 % relative error (2015-10-16 13:06:00).
  Quaternions must be slerp-interpolated to distribution times.
- O3 Rendering: `sub = panel.add_sub_panel(Orientation.Horizontal)` appends a row to the panel's
  stack and lays its plots side by side; it needs `setMinimumHeight` (≈380 px) on the unwrapped
  impl. `sub.plot_data(x, y, z, plot_type=PlotType.XY, z_log_scale=True)` → `(XYPlot, ColorMap)`,
  `z[i, j]` ↔ `(x[i], y[j])`. Call `plot.rescale_axes()` after data. Contours: `unwrap(graph._impl)`
  is a `SciQLopColorMap`; `set_contour_levels(list)`, `set_contour_color(QColor)` work on the GUI
  thread (`invoke_on_main_thread`). `Orientation` is in `SciQLop.user_api.plot.enums`.
  NaN cells render transparent; zeros render in the lowest colour → display maps f ≤ 0 to NaN.
  Quirks found in M0, resolved in M3 (`ui/viewer.py`):
  - on XY colormap plots the visible vertical axis is `y2`; `y` is hidden → label `y2`, unit on `z`;
  - `plot.overlay.show` never renders → titles are `Text` items, centre-anchored; their y maps to the
    hidden `y` axis, which the viewer pins to [0, 1] (title at y = 0.95);
  - the "ColorMap" legend overlaps titles → hidden via `legend().set_visible(False)`;
  - default colour range spans ~16 decades → clamped to [max·10⁻⁴, max], lower values NaN;
  - `set_equal_aspect_ratio(True)` still has no visible effect: planes are not 1:1 when the viewer row
    is tall. Open, for M6.
- M3 observations (2015-10-16 13:06, MMS1 brst ions):
  - slice mode shows isolated zero-count holes inside the core of a single 150 ms distribution
    (4 of 72 core cells within 350 km/s); these are real zeros, not regridding NaN. Reduced mode and
    interval averages hide them. Display choice (zero = transparent vs lowest colour) open for M6.
  - default vmax (speed of the top energy step, 2292 km/s for 28 keV ions) gives 72 km/s cells while
    the magnetosheath core spans ±700 km/s → a data-driven default vmax is needed (M6).
  - compute time: 20 burst distributions, 64³, GSE: 2.15 s → must run off the GUI thread (M4, R7).
  - viewer rows stack in creation order; the attach flow (M7) must add the viewer after the time series.
- O4 Product behind a graph: Qt dynamic property `sqp_product_path` on each plottable
  (`unwrap(plot._impl).plottables()`), `//`-joined; a VP created at `spike/vdf_omni_test` reports
  `spike//vdf_omni_test`. **Not public API** — isolate behind one helper (`ui/panel_tools.py`).
- O5 `create_virtual_product(path, cb, VirtualProductType.Spectrogram)` works from Python and the VP
  plots. Entry points need an installed distribution, which a folder plugin is not → v1 registers
  sources explicitly from the plugin's `load()`; entry-point discovery deferred until packaging as a wheel.
- One-count level: (f/σ)² from `mms1_dis_disterr_brst` gives min 1.0001, median 1.0001 counts on
  2015-10-16 13:06:00–01 → σ = f/√N confirmed; f₁ = σ²/f.
- Regridding tolerance: Maxwellian n = 10 cm⁻³, T = 1 keV, V = (300, −100, 50) km/s on an FPI-like
  32E×16θ×32φ grid, trilinear in index space: n recovered 10.11–10.12 cm⁻³ for 48³–96³ grids; peak
  within one cell of V.
