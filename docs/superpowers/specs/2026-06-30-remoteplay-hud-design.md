# Glory Remote Play HUD — Design Spec

**Date:** 2026-06-30
**Status:** Approved design, pending implementation plan
**Location of code:** `C:\Users\dalei\GloryV1\`

## Goal

Give the Remote Play auto-green engine the **same HUD as the original Glory UI**
(`glory_ui.py`, DearPyGui, sidebar-nav, gold/amber theme), driven by the Remote
Play engine instead of the capture-card + Arduino/Zen engine, plus four
improvements the Remote Play path makes worth showing.

This supersedes the headless console runner `glory_remoteplay.py` (which stays as
a minimal CLI/self-test). The new entry is a standalone GUI app.

## Background / why

The project pivoted (2026-06-30) from "drive the physical console through a Cronus
Zen" to "stream the console to the PC via Xbox Remote Play." The game becomes a PC
window (read the meter with `mss`, no capture card) and the controller becomes a
PC **virtual XInput pad** via `vgamepad` → ViGEmBus (driver already installed;
verified `VX360Gamepad()` taps X). The same process owns the eyes and the X button
on one clock, eliminating the pump-fake / wrong-device-release failures. Trigger:
**hold LB** on the physical controller (read via XInput) to let Glory take an
auto-green shot.

## Scope decision

**Standalone Remote Play app.** New entry `glory_remoteplay_app.py` reuses
`glory_ui.py`'s `build_hud`/`update_hud` **verbatim** and `SharedState` from
`2k26_autogreen.py`. The capture-card app (`2k26_autogreen.py`) is left untouched
as a fallback. No Zen/Arduino code runs in the new app.

## Architecture

```
glory_remoteplay_app.py  (new, ~150 lines)
  ├─ SharedState()                     # imported from 2k26_autogreen, unchanged
  ├─ thread: rp_capture_thread         # mss grab Remote Play window → MeterDetector
  │     → draw overlay onto preview → state.preview_frame
  │     → state.gz_state, state.fill, state.meter_pos, state.fsm_state
  ├─ thread: actuator (vgamepad VX360Gamepad)   # X down on arm, X up on release
  ├─ thread: lb_reader (XInput)        # arm flag + FSM transitions
  └─ main loop: build_hud(state); while running: update_hud(state); render frame
```

The engine owns the FSM (IDLE → HOLDING → RELEASE → COOLDOWN), reusing the logic
already in `glory_remoteplay.py` (`_xinput_reader`, `find_window_rect`, the
press/hold/release-on-`release_decision` loop, `MAX_HOLD_MS` safety). Everything it
learns is written into `SharedState`; `update_hud` renders it with the original look.

### Reused, unchanged
- `glory_ui.py` — `build_hud`, `update_hud`, theme, sidebar nav, preview texture.
- `2k26_autogreen.py::SharedState` — imported and constructed; its capture-card and
  Arduino threads are simply **not started**.
- `meter/detector.py::MeterDetector` — same magenta/green detection.
- `glory_v1_config.json` — same config (boxes, meter_colors, release_lead_ms,
  system_latency_ms). Adds `remoteplay_window` (window-title substring, default
  `"Xbox"`).

### SharedState fields populated by the new engine
`preview_frame` (with overlay), `gz_state`, `fill`, `meter_pos`, `fsm_state`,
`last_result`, `last_landing_px`, `release_lead_ms`, `session_shots`,
`shot_history`, `green_count_total`, `config`, `log`, and repurposed capture
fields: `capture_connected` = window-found AND pad-connected,
`capture_backend_actual` = `"RemotePlay"`, `capture_width/height` = window size.
New engine-local flags exposed for the status panel: `rp_lb_held: bool`,
`rp_pad_connected: bool`, `rp_window_locked: bool`.

## Improvements

### 1. Live meter overlay (on the existing Capture preview)
Engine draws onto the preview frame **before** assigning `state.preview_frame`, so
`glory_ui.py` is untouched:
- magenta rectangle around the detected bar (`gz_state.bar_x/bar_w` + fill_y),
- green line at `gz_state.green_bottom_y` (release target),
- cyan line at `gz_state.fill_y` (fill top),
- thin amber line at the predicted landing (`fill_y - predict_landing(...)` mapped),
- corner text `dist=±px  v=…px/f  conf=…`.
Drawn at preview resolution; coordinates scaled from full-frame to preview.

### 2. Auto-green scoreboard (Capture tab right sidebar)
Reads existing `session_shots` / `shot_history` / `green_count_total`:
- large **make %**, shots & greens counters,
- rolling **last-10 strip** (● green / ○ miss) from `shot_history`,
- avg miss-by-px (early/late) from a small running list the engine keeps,
- **Reset** button (zeroes the session counters).

### 3. Latency / lead tuner (Capture sidebar)
- slider bound to `state.release_lead_ms` (live; persisted to
  `glory_v1_config.json` on change via the existing `_save_config` pattern),
- shows live `dist=±px` from the last shot beside it,
- **Auto-tune** toggle: after each shot with a known `last_landing_px`, nudge
  `release_lead_ms` toward zero error by a bounded step (±6 ms/shot, clamp ±150),
  matching the existing feedback-lead idea but driving lead, not green_ms.

### 4. Arm / pad status panel (Capture sidebar top)
Four lights from engine flags:
- **LB held** (`rp_lb_held`), **Virtual pad** (`rp_pad_connected`),
- **Window lock** (`rp_window_locked` + size text),
- **FSM state** (`fsm_state`: IDLE / HOLDING / RELEASE).

### Capture sidebar adaptation
The capture-card-only inputs (capture index, capture backend) in the existing
`cap_quick_sidebar` are replaced for this app by: Remote Play **window-title**
input (`remoteplay_window`), the lead tuner (#3), the scoreboard (#2), and the
status panel (#4). The original tabs (Dashboard, Settings, Detection, Stats) are
unchanged.

## Error handling
- **No Remote Play window found** → `rp_window_locked = False`, status light red,
  engine falls back to full-primary-monitor grab (current `glory_remoteplay.py`
  behavior) and logs a hint.
- **ViGEmBus / pad init fails** → `rp_pad_connected = False`, status light red, log
  the install hint; vision still runs (read-only) so the HUD is usable.
- **No XInput controller** → `rp_lb_held` always False; log once; arming disabled.
- **MAX_HOLD_MS safety** → force X-up, record as SAFETY-TIMEOUT (not counted green).

## Testing / success criteria
1. `glory_remoteplay_app.py --self-test` still proves the virtual pad fires.
2. App launches, shows the original Glory HUD look (sidebar, theme, preview).
3. With a static replay frame fed in, the overlay draws bar/green/release lines at
   the right positions (unit-checkable against `MeterDetector` output).
4. Scoreboard increments and last-10 strip update when results are recorded.
5. Lead slider changes `state.release_lead_ms` and persists to config.
6. Status lights reflect: window found, pad created, LB held (manual check).
7. Live: hold LB on a 2K shot → X holds, releases on green, `dist=±px` printed and
   shown; auto-tune converges lead over several shots. (User live test.)

## Non-goals (YAGNI)
- No capture-card / Zen / Arduino code in this app.
- No new sidebar page (improvements live in the existing Capture tab).
- No physical-controller passthrough beyond reading LB (movement etc. still go
  straight through Remote Play from the real controller).
- No changes to `glory_ui.py` internals beyond what's needed to swap the
  capture-card sidebar inputs for Remote Play ones (kept minimal/additive).

## Open live unknown
Whether the Xbox PC app forwards a **virtual** pad as readily as a physical one
(may need the pad created before the Xbox app launches). The status panel makes
this diagnosable; if it fails, add pre-launch pad init.
