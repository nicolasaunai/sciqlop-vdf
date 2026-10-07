# sciqlop-vdf — dockable viewer UI (design)

Date: 2026-10-07. Status: approved in conversation, pending written-spec review.

## 1. Problem

Current UI (M3–M7, `sciqlop_vdf/ui/`):

- `viewer.py` puts the three planes in `panel.add_sub_panel(Horizontal)` with `setMinimumHeight(380)`: they
  take a fixed, large share of the panel, cannot be resized against the time series, cannot be moved, and
  make the panel's vertical scrolling awkward.
- `controls.py` packs ~15 widgets in one row inserted into SciQLop's private `PanelContainer` layout
  (`panel_tools.py`); labels are terse (`Δ`, `|v|max`, `grid`), slice boxes are always visible.
- Status messages ("computing …", errors) are split over the three plot titles (`split_message`).

## 2. Goal and success criteria

The user can see the time series and the VDF at useful sizes simultaneously, arranged freely (resize,
move, tab, float), with readable controls. The time-series panel remains the driver (marker / span live
on it). Several viewers per panel keep working. `attach(panel, source, options, t)` keeps its signature.

## 3. Decisions

| # | Decision |
|---|---|
| D1 | Each viewer is its own QtAds dock widget, linked to one time-series panel. |
| D2 | New dock opens split to the right of its panel's dock, ~40 % of the width. |
| D3 | Controls: compact toolbar at the top of the dock + ⚙ drop-down for advanced options; status line at the bottom. |
| D4 | Planes: adaptive layout (row / column / L by dock aspect), 1:1 velocity aspect, one shared colour bar (common z range), optional single-plane mode. |
| D5 | No persistence of dock position/options across workspace reloads in this round. |

## 4. Architecture

```
┌─ Panel3 (dock) ───────────────┐┌─ VDF · MMS1 FPI-DIS brst ↔ Panel3 (dock) ─┐
│ time series …  │ orange marker││ [toolbar: mode·time·frame·bulk·proj  ⚙ ×] │
│                │ blue span    ││   ┌─────┐ ┌─────┐ ┌─────┐  ║colour bar║   │
│                │              ││   │ ∥–⊥1│ │ ∥–⊥2│ │⊥1–⊥2│               │
│ [time bar | crosshair | VDF▾] ││   └─────┘ └─────┘ └─────┘                 │
└───────────────────────────────┘│ status: computing … 22:34:02.120          │
                                 └───────────────────────────────────────────┘
```

| Unit | Change | Responsibility |
|---|---|---|
| `ui/dock.py` | new | Only place touching private SciQLop docking (`main_window.addWidgetIntoDock`, `dock_manager`, QtAds). API: `open_dock(widget, title, beside_panel) -> handle`; `handle.close()`; `handle.closed` signal. Splits right of the panel's `CDockWidget` at 40 %; fallback: right dock area + status notice. |
| `ui/vdf_widget.py` | new | Plain QWidget: toolbar (from `controls.py`) + plane area (from `viewer.py`) + status `QLabel`. No SciQLop import except via the viewer. |
| `ui/viewer.py` | rewrite | Standalone `SciQLopMultiPlotPanel(None, synchronize_x=False, synchronize_time=False)` wrapped in `PlotPanel`. Three XY colormaps with contours; adaptive layout; 1:1 aspect; colour scale shown on one plane only, z range locked on all three to the common range; single-plane mode; short titles. |
| `ui/controls.py` | rewrite | Toolbar + ⚙ drop-down (§5). Still PySide6-only. |
| `ui/layout.py` | new | Qt-free: `arrangement(width, height) -> "row" | "column" | "L"` and grid positions; `shared_zrange(planes, decades)`. Unit-tested. |
| `ui/controller.py` | small change | Builds `VDFWidget` + dock instead of sub-panel + inserted bar. Worker, debounce, generation counter, marker, span unchanged. `close()` tears down the dock. |
| `ui/format.py` | small change | `titles()` → short plane titles + toolbar/dock-title strings; `split_message` removed. |
| `ui/panel_tools.py` | delete | No more insertion into `PanelContainer`. |
| `ui/marker.py`, `ui/interval.py`, `ui/attach.py`, `core/*`, adapters | unchanged | (`combined_ui.py` inherits the controller and needs no change beyond the controller's.) |

Private SciQLop dependencies after the change: docking (`ui/dock.py`), colormap contours and hidden-axis
title `Text` (`ui/viewer.py`), `sqp_product_path` + `chrome_row` (`ui/attach.py`). Each isolated in one file.

## 5. Controls, labels, status

Toolbar (always visible):

| Control | Widget | Text |
|---|---|---|
| Selection | 2-button toggle `● Marker` / `▭ Interval` | colours match the orange line / blue span |
| Time | read-only, editable on double-click | marker: `2017-07-11 22:34:02.120`; interval: `22:33:50 → 22:34:10 (N=67)`; editing moves marker/span |
| Frame | combo | `Frame:` + available frames |
| Bulk frame | checkbox | `Bulk frame (v − V_bulk)` |
| Projection | 2-button toggle | `Reduced ∫f dv₃` / `Slice` |
| Planes | toggle + combo | three planes / one plane (choose which) |
| ⚙ | drop-down | see below |
| × | button, far right | tooltip `Close VDF viewer` |

⚙ drop-down (form, full labels with units):

- Slice (visible only when Projection = Slice): point `v₁ v₂ v₃ [km/s]` named after frame axes
  (`set_axes`), half-thickness `Δ [km/s]` (`auto` = 0).
- Grid: `cells per axis` 16–128 step 16; `|v| max [km/s]` (`auto` = 0).
- Display: `contours` 0–10 (log-spaced, 3 decades); `colour range [decades below max]` (default 4, was
  the constant `DISPLAY_DECADES`); `mask cells < 1 count`.

Labels: plane titles `v∥ – v⊥1` (frame axis names); axis labels with `[km/s]`; colour bar `f [s²/km⁵]`
(reduced) or `f [s³/km⁶]` (slice). Time / frame / source / N go to the toolbar and the dock title
(`VDF · <source label> ↔ <panel name>`).

Status line: `computing … <time>` → `done · <N> distributions · <t> s`; errors in red; no-data clears
the planes (unchanged behaviour).

## 6. Lifecycle

- Attach ("VDF ▾" or `attach(...)`): controller → `VDFWidget` → dock beside the panel → marker at panel
  centre → first computation.
- Close dock (× or dock close): remove marker/span, shut down worker, dispose plots.
- Close panel: existing `destroyed` hook closes every linked VDF dock first, then shuts down; no access to
  deleted Qt objects.
- Multiple viewers per panel: each has its own dock, marker, controller (as today).

## 7. Errors

Unchanged classes: `NoDataError` → clear planes + message; `VDFError` / other → keep last image +
message; display exception → status line error, never a stuck "computing …". All logged.

## 8. Testing

1. **Spike first (throwaway):** standalone `SciQLopMultiPlotPanel` with 3 XY colormaps, contours, one
   colour scale hidden/shown, inside a QtAds dock — docked, floated, tabbed. Failure → stop and report.
2. Unit tests (pytest-qt, no SciQLop): `tests/test_layout.py` (arrangement by aspect, `shared_zrange`);
   `tests/test_controls.py` (slice group visibility, time readout round-trip, emitted option fields).
3. Existing suite passes (`test_format` updated for removed `split_message`).
4. Manual check in running SciQLop: MMS1 FPI-DIS brst on an FGM panel; drag marker and span; float /
   tab / resize (tall, wide, square); close dock; close panel; two viewers on one panel.

## 9. Out of scope

- Persisting dock layout and options in the workspace.
- Upstreaming a public docking API to SciQLop.
- One-count mask vs contour (open item in `HANDOVER.md`).
