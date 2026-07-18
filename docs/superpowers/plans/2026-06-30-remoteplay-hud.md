# Remote Play HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Remote Play auto-green engine the original Glory UI (`glory_ui.py`) as its HUD, plus a live meter overlay, auto-green scoreboard, latency/lead tuner, and arm/pad status panel.

**Architecture:** A standalone app (`glory_remoteplay_app.py`) reuses `glory_ui.py`'s `build_hud`/`update_hud` and `2k26_autogreen.py`'s `SharedState` **verbatim** (zero edits to either). A single engine thread (`glory_rp_engine.RPEngine`) grabs the Remote Play window with `mss`, runs `MeterDetector`, drives a `vgamepad` virtual Xbox pad (X hold/release on LB arm), and writes results into `SharedState`. Pure logic (overlay geometry, scoreboard math, auto-tune) lives in `glory_rp_logic.py` and is unit-tested. HUD additions are injected into the existing Capture tab by parent tag in `glory_rp_hud.py`.

**Tech Stack:** Python 3.12, DearPyGui, OpenCV, mss, vgamepad (+ViGEmBus, already installed), XInput via ctypes, pytest.

## Global Constraints

- Python interpreter: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe` (run everything with this).
- Working dir for code: `C:\Users\dalei\GloryV1\`.
- **Do NOT edit** `glory_ui.py` or `2k26_autogreen.py` — reuse by import only. New per-app state lives as dynamic attributes on the `SharedState` instance (`state.rp_lb_held`, `state.rp_pad_connected`, `state.rp_window_locked`).
- Reuse existing helpers from `glory_remoteplay.py`: `find_window_rect(title_substr)` and `_xinput_reader()`.
- Landing-px convention (matches `glory_calibrate.py`): `landing_px = fill_y - green_bottom_y`; `>0` = short (EARLY release), `<0` = overshoot (LATE), `|px|<=6` = GREEN.
- Auto-tune convention (matches existing FB_WAIT logic): `late` → `lead += step`, `early` → `lead -= step`, step 6 ms, clamp `[-150, 150]`.
- Result strings are exactly `'green' | 'early' | 'late'`; record via `state.record_result('standstill', result)` (Remote Play does not classify shot type; the `'standstill'` bucket already exists in `SHOT_TYPES`).
- Only ONE process may hold the Remote Play window / virtual pad at a time. Close other runners before launching.
- Config file: `C:\Users\dalei\GloryV1\glory_v1_config.json`. New key `remoteplay_window` (string, default `"Xbox"`).
- One green basketball-court color must never be mistaken for the cap — detector already handles this; do not loosen its thresholds.

---

### Task 1: Pure logic module (`glory_rp_logic.py`)

**Files:**
- Create: `C:\Users\dalei\GloryV1\glory_rp_logic.py`
- Test: `C:\Users\dalei\GloryV1\tests\test_rp_logic.py`

**Interfaces:**
- Consumes: a `GreenZoneState`-like object with attrs `bar_x, bar_w, fill_y, green_top_y, green_bottom_y, confidence` (from `meter/detector.py`).
- Produces:
  - `classify_landing(landing_px: int, tol: int = 6) -> str` → `'green'|'early'|'late'`
  - `autotune_lead(lead_ms: float, result: str, step: float = 6.0, lo: float = -150.0, hi: float = 150.0) -> float`
  - `scoreboard_summary(session_shots: dict, miss_px: list) -> dict` with keys `shots, greens, pct, avg_early_px, avg_late_px`
  - `draw_overlay(preview_bgr, gz, full_h: int, full_w: int, landing_y: int | None = None)` → mutates and returns the preview image

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rp_logic.py
import os, sys, importlib.util
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

L = _load('glory_rp_logic', 'glory_rp_logic.py')

class FakeGZ:
    def __init__(self, **k): self.__dict__.update(k)

def test_classify_landing():
    assert L.classify_landing(0) == 'green'
    assert L.classify_landing(5) == 'green'
    assert L.classify_landing(20) == 'early'   # short of green
    assert L.classify_landing(-20) == 'late'   # overshoot

def test_autotune_lead_direction_and_clamp():
    assert L.autotune_lead(0.0, 'late') == 6.0
    assert L.autotune_lead(0.0, 'early') == -6.0
    assert L.autotune_lead(0.0, 'green') == 0.0
    assert L.autotune_lead(148.0, 'late') == 150.0     # clamp hi
    assert L.autotune_lead(-148.0, 'early') == -150.0  # clamp lo

def test_scoreboard_summary():
    ss = {'standstill': {'shots': 4, 'g': 2, 'l': 1, 'e': 1},
          'deep_3': {'shots': 0, 'g': 0, 'l': 0, 'e': 0}}
    out = L.scoreboard_summary(ss, [20, 30, -10])
    assert out['shots'] == 4 and out['greens'] == 2
    assert abs(out['pct'] - 50.0) < 1e-6
    assert abs(out['avg_early_px'] - 25.0) < 1e-6   # mean of +20,+30
    assert abs(out['avg_late_px'] - (-10.0)) < 1e-6

def test_draw_overlay_marks_green_line():
    prev = np.zeros((360, 640, 3), dtype=np.uint8)
    gz = FakeGZ(bar_x=900, bar_w=60, fill_y=600, green_top_y=520,
                green_bottom_y=560, confidence=0.85)
    L.draw_overlay(prev, gz, full_h=1080, full_w=1920)
    gy = int(560 * 360 / 1080)              # green_bottom mapped to preview row
    midx = int((900 + 30) * 640 / 1920)
    px = prev[gy, midx]
    assert px[1] > 150 and px[0] < 80 and px[2] < 80   # BGR green drawn

def test_draw_overlay_skips_low_confidence():
    prev = np.zeros((360, 640, 3), dtype=np.uint8)
    gz = FakeGZ(bar_x=900, bar_w=60, fill_y=600, green_top_y=520,
                green_bottom_y=560, confidence=0.2)
    out = L.draw_overlay(prev, gz, 1080, 1920)
    assert int(out.sum()) == 0      # nothing drawn
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_logic.py -v`
Expected: FAIL (`No module named 'glory_rp_logic'` / attribute errors).

- [ ] **Step 3: Write minimal implementation**

```python
# glory_rp_logic.py
"""Pure, GUI-free logic for the Remote Play HUD: result classification,
release-lead auto-tune, scoreboard math, and the meter overlay drawing.
Unit-tested in tests/test_rp_logic.py."""
import cv2

MAGENTA = (255, 0, 255)   # BGR - bar outline
GREEN   = (0, 255, 0)     # BGR - green target / release line
CYAN    = (255, 255, 0)   # BGR - fill top
AMBER   = (0, 170, 255)   # BGR - predicted landing


def classify_landing(landing_px, tol=6):
    if abs(landing_px) <= tol:
        return 'green'
    return 'early' if landing_px > 0 else 'late'


def autotune_lead(lead_ms, result, step=6.0, lo=-150.0, hi=150.0):
    if result == 'late':
        lead = lead_ms + step
    elif result == 'early':
        lead = lead_ms - step
    else:
        return lead_ms
    return max(lo, min(hi, lead))


def scoreboard_summary(session_shots, miss_px):
    shots = sum(v['shots'] for v in session_shots.values())
    greens = sum(v['g'] for v in session_shots.values())
    pct = (100.0 * greens / shots) if shots else 0.0
    early = [p for p in miss_px if p > 0]
    late = [p for p in miss_px if p < 0]
    return {
        'shots': shots, 'greens': greens, 'pct': pct,
        'avg_early_px': (sum(early) / len(early)) if early else 0.0,
        'avg_late_px': (sum(late) / len(late)) if late else 0.0,
    }


def draw_overlay(preview_bgr, gz, full_h, full_w, landing_y=None):
    if gz is None or getattr(gz, 'confidence', 0.0) < 0.5 or not full_w or not full_h:
        return preview_bgr
    ph, pw = preview_bgr.shape[:2]
    sx, sy = pw / full_w, ph / full_h
    x1, x2 = int(gz.bar_x * sx), int((gz.bar_x + gz.bar_w) * sx)
    fy = int(gz.fill_y * sy)
    gtop = int(gz.green_top_y * sy)
    gbot = int(gz.green_bottom_y * sy)
    cv2.rectangle(preview_bgr, (x1, gtop), (x2, fy), MAGENTA, 1)
    cv2.line(preview_bgr, (x1, gbot), (x2, gbot), GREEN, 2)
    cv2.line(preview_bgr, (x1, fy), (x2, fy), CYAN, 1)
    if landing_y is not None:
        ly = int(landing_y * sy)
        cv2.line(preview_bgr, (x1, ly), (x2, ly), AMBER, 1)
    return preview_bgr
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_logic.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add glory_rp_logic.py tests/test_rp_logic.py
git commit -m "feat(rp-hud): pure logic - classify/autotune/scoreboard/overlay"
```

---

### Task 2: Config key + lead persistence (`remoteplay_window`, `save_lead`)

**Files:**
- Modify: `C:\Users\dalei\GloryV1\glory_v1_config.json` (add `"remoteplay_window": "Xbox"`)
- Create: `C:\Users\dalei\GloryV1\glory_rp_config.py`
- Test: `C:\Users\dalei\GloryV1\tests\test_rp_config.py`

**Interfaces:**
- Produces: `save_lead(config: dict, lead_ms: float, path: str) -> None` — writes the whole `config` dict back to `path` with `release_lead_ms` updated and rounded to 1 dp. Used by the lead slider callback so a tuned lead survives restart.

- [ ] **Step 1: Add the config key**

Edit `glory_v1_config.json`: add a top-level key (after `"release_lead_ms": 58.0`):
```json
  "release_lead_ms": 58.0,
  "remoteplay_window": "Xbox"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_rp_config.py
import os, json, importlib.util, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

C = _load('glory_rp_config', 'glory_rp_config.py')

def test_save_lead_roundtrip():
    cfg = {'release_lead_ms': 10.0, 'remoteplay_window': 'Xbox', 'boxes': {}}
    fd, path = tempfile.mkstemp(suffix='.json'); os.close(fd)
    try:
        C.save_lead(cfg, 72.345, path)
        back = json.load(open(path))
        assert back['release_lead_ms'] == 72.3
        assert back['remoteplay_window'] == 'Xbox'   # other keys preserved
    finally:
        os.remove(path)

def test_live_config_has_window_key():
    cfg = json.load(open(os.path.join(HERE, 'glory_v1_config.json')))
    assert cfg.get('remoteplay_window') == 'Xbox'
```

- [ ] **Step 3: Run test to verify it fails**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_config.py -v`
Expected: FAIL (`No module named 'glory_rp_config'`).

- [ ] **Step 4: Write minimal implementation**

```python
# glory_rp_config.py
"""Config persistence for the Remote Play app (keeps a tuned release lead
across restarts without touching 2k26_autogreen._save_config)."""
import json


def save_lead(config, lead_ms, path):
    config = dict(config)
    config['release_lead_ms'] = round(float(lead_ms), 1)
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_config.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add glory_v1_config.json glory_rp_config.py tests/test_rp_config.py
git commit -m "feat(rp-hud): remoteplay_window config key + lead persistence"
```

---

### Task 3: Remote Play engine (`glory_rp_engine.py`)

**Files:**
- Create: `C:\Users\dalei\GloryV1\glory_rp_engine.py`
- Test: `C:\Users\dalei\GloryV1\tests\test_rp_engine.py`

**Interfaces:**
- Consumes: `glory_rp_logic` (Task 1), `meter/detector.py::MeterDetector`, `find_window_rect`/`_xinput_reader` from `glory_remoteplay.py`, a `SharedState` instance, its `config` dict.
- Produces:
  - `class RPEngine(state, config)` with:
    - `process(frame, lb_held: bool, now: float) -> None` — runs detection + FSM + (fake/real) pad, writes `state.gz_state, state.fill, state.meter_pos, state.fsm_state, state.preview_frame`, and on release updates `state.last_landing_px, state.last_result`, calls `state.record_result('standstill', result)`, appends to `self.miss_px`, and auto-tunes `state.release_lead_ms` when `self.autotune` is True.
    - `self.pad` with `.x_down()`/`.x_up()` (a small wrapper; tests inject a fake).
    - `self.miss_px: deque`, `self.autotune: bool`.
    - `MAX_HOLD_MS = 1600`.
  - `class _Pad` real wrapper around `vgamepad.VX360Gamepad` exposing `x_down()`, `x_up()`, `connected: bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rp_engine.py
import os, sys, importlib.util, time
import numpy as np, cv2
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ENG = _load('glory_rp_engine', 'glory_rp_engine.py')
AG = _load('gapp', '2k26_autogreen.py')

class FakePad:
    def __init__(self): self.events = []; self.connected = True
    def x_down(self): self.events.append('down')
    def x_up(self):   self.events.append('up')

def _frame_with_bar(fill_top):
    """1080x1920 BGR: magenta bar (x 900-960), green cap rows 520-560,
    magenta fill from fill_top down to 700. Mirrors test_meter_detector."""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[520:560, 900:960] = (0, 255, 0)           # green cap (BGR)
    img[fill_top:700, 900:960] = (200, 0, 200)    # magenta fill (BGR)
    return img

def test_engine_holds_then_releases_on_green():
    state = AG.SharedState()
    eng = ENG.RPEngine(state, dict(state.config))
    eng.pad = FakePad()
    # Fill rising toward the green cap over frames; arm (LB held) throughout.
    t = 1000.0
    for fill_top in range(660, 540, -10):     # rises ~10px/frame toward 560
        eng.process(_frame_with_bar(fill_top), lb_held=True, now=t)
        t += 0.016
    assert 'down' in eng.pad.events, "X should have been pressed when armed"
    assert 'up' in eng.pad.events, "X should release as fill reaches green"
    assert state.fsm_state in ('RELEASE', 'COOLDOWN')

def test_engine_idle_when_not_armed():
    state = AG.SharedState()
    eng = ENG.RPEngine(state, dict(state.config))
    eng.pad = FakePad()
    eng.process(_frame_with_bar(600), lb_held=False, now=1.0)
    assert eng.pad.events == []
    assert state.fsm_state == 'IDLE'

def test_engine_autotune_moves_lead_on_late():
    state = AG.SharedState()
    state.release_lead_ms = 0.0
    eng = ENG.RPEngine(state, dict(state.config))
    eng.pad = FakePad(); eng.autotune = True
    eng._finish_shot(landing_px=-20, now=1.0)   # overshoot -> late
    assert state.last_result == 'late'
    assert state.release_lead_ms == 6.0          # late -> +step
    assert list(eng.miss_px)[-1] == -20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_engine.py -v`
Expected: FAIL (`No module named 'glory_rp_engine'`).

- [ ] **Step 3: Write minimal implementation**

```python
# glory_rp_engine.py
"""Remote Play engine: one thread that grabs the Remote Play window, runs the
meter detector, drives a virtual Xbox pad (hold X on LB, release on green), and
writes everything into the shared SharedState the original HUD already renders."""
import os, time, threading
from collections import deque
import importlib.util

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


L = _load('glory_rp_logic', 'glory_rp_logic.py')
_rp = _load('glory_remoteplay', 'glory_remoteplay.py')   # reuse window + xinput
_det = _load('gdet', os.path.join('meter', 'detector.py'))

PREVIEW_W, PREVIEW_H = 640, 360
MAX_HOLD_MS = 1600


def _roi(box, fw, fh):
    return (int(box[0] * fw), int(box[1] * fh), int(box[2] * fw), int(box[3] * fh))


class _Pad:
    """Real virtual-pad wrapper. connected=False if ViGEmBus/vgamepad missing."""
    def __init__(self):
        self.connected = False
        self._gp = None
        try:
            import vgamepad as vg
            self._gp = vg.VX360Gamepad()
            self._btn = vg.XUSB_BUTTON.XUSB_GAMEPAD_X
            self.connected = True
        except Exception:
            self.connected = False

    def x_down(self):
        if self._gp:
            self._gp.press_button(button=self._btn); self._gp.update()

    def x_up(self):
        if self._gp:
            self._gp.release_button(button=self._btn); self._gp.update()


class RPEngine:
    def __init__(self, state, config):
        self.state = state
        self.cfg = config
        self.det = _det.MeterDetector()
        self.pad = None                 # set in init_io() or injected by tests
        self.lb_read = None
        self.grab = None
        self.sct = None
        self.miss_px = deque(maxlen=50)
        self.autotune = False
        self.fsm = 'IDLE'
        self.hold_start = 0.0
        self.arm_prev = False
        self.stop_evt = threading.Event()
        # dynamic status flags the HUD reads via getattr
        state.rp_lb_held = False
        state.rp_pad_connected = False
        state.rp_window_locked = False

    # ---- IO setup (real run only; tests inject pad + call process directly) ----
    def init_io(self):
        import mss
        title_sub = self.cfg.get('remoteplay_window', 'Xbox')
        rect, title = _rp.find_window_rect(title_sub)
        self.sct = mss.mss()
        if rect is None:
            mon = self.sct.monitors[1]
            rect = (mon['left'], mon['top'], mon['width'], mon['height'])
            self.state.rp_window_locked = False
            self.state.log(f"Remote Play window '{title_sub}' not found; "
                           f"grabbing full monitor {rect[2]}x{rect[3]}.")
        else:
            self.state.rp_window_locked = True
            self.state.log(f"Locked Remote Play window '{title}' {rect[2]}x{rect[3]}.")
        self.grab = {'left': rect[0], 'top': rect[1], 'width': rect[2], 'height': rect[3]}
        self.state.capture_width, self.state.capture_height = rect[2], rect[3]
        self.state.capture_backend_actual = 'RemotePlay'
        self.state.capture_index_actual = -1
        if self.pad is None:
            self.pad = _Pad()
        self.state.rp_pad_connected = self.pad.connected
        self.lb_read = _rp._xinput_reader()
        self.state.capture_connected = self.state.rp_window_locked and self.pad.connected

    # ---- per-frame step (unit-tested) -----------------------------------------
    def process(self, frame, lb_held, now):
        fh, fw = frame.shape[:2]
        gz = self.det.update(frame, _roi(self.cfg['boxes']['meter'], fw, fh), self.cfg)
        self.state.gz_state = gz
        self.state.fill = float(getattr(gz, 'fill_velocity', 0.0))
        self.state.rp_lb_held = bool(lb_held)
        base = float(self.cfg.get('system_latency_ms', 17.0))
        eff_lat = base + float(getattr(self.state, 'release_lead_ms', 0.0))

        landing_y = None
        if gz is not None and getattr(gz, 'confidence', 0.0) >= 0.5:
            resid = self.det.predict_landing(gz, eff_lat)
            landing_y = gz.fill_y - int(resid)      # where it will stop, full-frame Y

        if self.fsm == 'IDLE':
            if lb_held and not self.arm_prev:
                self.pad.x_down(); self.hold_start = now; self.fsm = 'HOLDING'
        elif self.fsm == 'HOLDING':
            held_ms = (now - self.hold_start) * 1000.0
            rd = self.det.release_decision(gz, eff_lat) if gz is not None else None
            if not lb_held:
                self.pad.x_up(); self.fsm = 'COOLDOWN'
            elif (rd is not None and rd.should_fire) or held_ms >= MAX_HOLD_MS:
                self.pad.x_up()
                lp = (gz.fill_y - gz.green_bottom_y) if gz is not None else 0
                self._finish_shot(landing_px=int(lp), now=now)
                self.fsm = 'COOLDOWN'
        elif self.fsm == 'COOLDOWN':
            if not lb_held:
                self.fsm = 'IDLE'

        self.state.fsm_state = self.fsm
        self.arm_prev = lb_held

        # preview + overlay (engine-side; HUD renders state.preview_frame as-is)
        prev = cv2.resize(frame, (PREVIEW_W, PREVIEW_H), interpolation=cv2.INTER_AREA)
        L.draw_overlay(prev, gz, fh, fw, landing_y)
        self.state.preview_frame = prev

    def _finish_shot(self, landing_px, now):
        result = L.classify_landing(landing_px)
        self.state.last_landing_px = landing_px
        self.state.last_result = result
        self.state.record_result('standstill', result)
        self.miss_px.append(landing_px)
        if self.autotune:
            self.state.release_lead_ms = L.autotune_lead(
                float(getattr(self.state, 'release_lead_ms', 0.0)), result)

    # ---- background loop (real run) -------------------------------------------
    def run(self):
        self.init_io()
        while not self.stop_evt.is_set():
            frame = np.asarray(self.sct.grab(self.grab))[:, :, :3]
            lb = self.lb_read() if self.lb_read else False
            self.process(frame, lb, time.time())
            time.sleep(0.001)

    def start(self):
        t = threading.Thread(target=self.run, daemon=True); t.start(); return t

    def stop(self):
        self.stop_evt.set()
        if self.pad:
            self.pad.x_up()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_engine.py -v`
Expected: PASS (3 tests). If the rising-bar test does not reach RELEASE, widen the fill range or lower `MIN_FIRE_VELOCITY` expectations by adding one more frame at `fill_top=550`; the detector needs ≥2 frames of motion to compute velocity.

- [ ] **Step 5: Commit**

```bash
git add glory_rp_engine.py tests/test_rp_engine.py
git commit -m "feat(rp-hud): Remote Play engine - grab/detect/FSM/virtual-pad"
```

---

### Task 4: HUD augmentation (`glory_rp_hud.py`)

**Files:**
- Create: `C:\Users\dalei\GloryV1\glory_rp_hud.py`
- Test: `C:\Users\dalei\GloryV1\tests\test_rp_hud.py`

**Interfaces:**
- Consumes: `glory_rp_logic` (Task 1), DearPyGui, the existing parent tag `cap_quick_sidebar` (created by `glory_ui._build_capture`), `SharedState` instance, `glory_rp_config.save_lead`.
- Produces:
  - `augment_capture_tab(state, config_path: str)` — adds status lights, scoreboard text, and a lead slider into `cap_quick_sidebar`. Must be called AFTER `build_hud`.
  - `update_rp_hud(state, engine)` — refreshes the added widgets each frame from `state` + `engine.miss_px`.
  - `rp_hud_values(state, engine) -> dict` — pure value computation (tested without DPG): keys `pct_txt, count_txt, strip, lights, last_dist_txt`.

- [ ] **Step 1: Write the failing test** (pure values only — no DPG context needed)

```python
# tests/test_rp_hud.py
import os, importlib.util
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

H = _load('glory_rp_hud', 'glory_rp_hud.py')
AG = _load('gapp', '2k26_autogreen.py')

class FakeEng:
    def __init__(self): self.miss_px = [20, -10]

def test_rp_hud_values():
    state = AG.SharedState()
    state.record_result('standstill', 'green')
    state.record_result('standstill', 'late')
    state.rp_lb_held = True
    state.rp_pad_connected = True
    state.rp_window_locked = False
    state.last_landing_px = -10
    state.fsm_state = 'HOLDING'
    v = H.rp_hud_values(state, FakeEng())
    assert '50' in v['pct_txt']                 # 1 green / 2 shots
    assert v['lights']['lb'] is True
    assert v['lights']['pad'] is True
    assert v['lights']['window'] is False
    assert v['lights']['fsm'] == 'HOLDING'
    assert v['strip'].count('●') == 1 and v['strip'].count('○') == 1
    assert '-10' in v['last_dist_txt']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_hud.py -v`
Expected: FAIL (`No module named 'glory_rp_hud'`).

- [ ] **Step 3: Write minimal implementation**

```python
# glory_rp_hud.py
"""Injects the four Remote Play improvements into the original Glory HUD's
existing Capture-tab sidebar (parent tag 'cap_quick_sidebar'), so glory_ui.py
stays untouched. rp_hud_values() is the pure, testable value computation."""
import os, importlib.util
import dearpygui.dearpygui as dpg

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


L = _load('glory_rp_logic', 'glory_rp_logic.py')
_cfg = _load('glory_rp_config', 'glory_rp_config.py')

GOLD = (245, 166, 35, 255)
MUTED = (136, 136, 136, 255)
GREEN = (0, 200, 83, 255)
RED = (213, 0, 0, 255)
WHITE = (255, 255, 255, 255)
CONFIG_PATH = os.path.join(HERE, 'glory_v1_config.json')


def rp_hud_values(state, engine):
    with state.lock:
        ss = {t: dict(v) for t, v in state.session_shots.items()}
        history = list(state.shot_history)
        last_px = int(getattr(state, 'last_landing_px', 0))
    summ = L.scoreboard_summary(ss, list(engine.miss_px))
    strip = ''.join('●' if r == 'green' else '○' for r in history[:10])
    return {
        'pct_txt': f"{summ['pct']:.0f}%  ({summ['greens']}/{summ['shots']})",
        'count_txt': (f"early {summ['avg_early_px']:.0f}px / "
                      f"late {summ['avg_late_px']:.0f}px"),
        'strip': strip or '—',
        'last_dist_txt': f"{last_px:+d}px",
        'lights': {
            'lb': bool(getattr(state, 'rp_lb_held', False)),
            'pad': bool(getattr(state, 'rp_pad_connected', False)),
            'window': bool(getattr(state, 'rp_window_locked', False)),
            'fsm': getattr(state, 'fsm_state', 'IDLE'),
        },
    }


def _light(on):
    return GREEN if on else RED


def augment_capture_tab(state, config_path=CONFIG_PATH):
    """Add status lights + scoreboard + lead slider into the existing sidebar."""
    if not dpg.does_item_exist('cap_quick_sidebar'):
        return
    p = 'cap_quick_sidebar'
    dpg.add_separator(parent=p)
    dpg.add_text('AUTO-GREEN', color=GOLD, parent=p)

    # status lights
    for key, label in (('window', 'Window'), ('pad', 'Virtual pad'),
                       ('lb', 'LB held'), ('fsm', 'FSM')):
        with dpg.group(horizontal=True, parent=p):
            dpg.add_text('●', tag=f'rp_dot_{key}', color=RED)
            dpg.add_text(label, color=MUTED)
            if key == 'fsm':
                dpg.add_text('IDLE', tag='rp_fsm_txt', color=WHITE)

    dpg.add_separator(parent=p)
    dpg.add_text('Make %', color=MUTED, parent=p)
    dpg.add_text('0%  (0/0)', tag='rp_pct', color=GREEN, parent=p)
    dpg.add_text('—', tag='rp_strip', color=WHITE, parent=p)
    dpg.add_text('', tag='rp_misspx', color=MUTED, parent=p)
    dpg.add_text('last —', tag='rp_lastdist', color=MUTED, parent=p)

    dpg.add_separator(parent=p)
    dpg.add_text('Release lead (ms)', color=MUTED, parent=p)

    def _on_lead(s, a, u):
        with state.lock:
            state.release_lead_ms = float(a)
        _cfg.save_lead(state.config, float(a), config_path)

    dpg.add_slider_float(tag='rp_lead', parent=p, width=170,
                         default_value=float(getattr(state, 'release_lead_ms', 0.0)),
                         min_value=-150.0, max_value=150.0, callback=_on_lead)

    def _on_auto(s, a, u):
        # engine reference is attached on the state by the app entry
        eng = getattr(state, 'rp_engine', None)
        if eng is not None:
            eng.autotune = bool(a)

    dpg.add_checkbox(label='Auto-tune lead', tag='rp_autotune',
                     parent=p, callback=_on_auto)


def update_rp_hud(state, engine):
    if not dpg.does_item_exist('rp_pct'):
        return
    v = rp_hud_values(state, engine)
    for key in ('window', 'pad', 'lb'):
        dpg.configure_item(f'rp_dot_{key}', color=_light(v['lights'][key]))
    dpg.configure_item('rp_dot_fsm',
                       color=GREEN if v['lights']['fsm'] != 'IDLE' else RED)
    dpg.set_value('rp_fsm_txt', v['lights']['fsm'])
    dpg.set_value('rp_pct', v['pct_txt'])
    dpg.set_value('rp_strip', v['strip'])
    dpg.set_value('rp_misspx', v['count_txt'])
    dpg.set_value('rp_lastdist', 'last ' + v['last_dist_txt'])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_hud.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add glory_rp_hud.py tests/test_rp_hud.py
git commit -m "feat(rp-hud): inject status/scoreboard/lead into Capture sidebar"
```

---

### Task 5: App entry + live verification (`glory_remoteplay_app.py`)

**Files:**
- Create: `C:\Users\dalei\GloryV1\glory_remoteplay_app.py`
- Test: manual launch (GUI) + the full pytest suite.

**Interfaces:**
- Consumes: `build_hud`, `update_hud` from `glory_ui.py`; `SharedState`, `PIDTuner`, `SHOT_TYPES`, `CONFIG` from `2k26_autogreen.py`; `RPEngine` (Task 3); `augment_capture_tab`, `update_rp_hud` (Task 4).
- Produces: a runnable GUI app; no exported API.

- [ ] **Step 1: Write the entry module**

```python
# glory_remoteplay_app.py
"""Standalone Remote Play auto-green app: the ORIGINAL Glory HUD (glory_ui.py)
driven by the Remote Play engine, with the live meter overlay, auto-green
scoreboard, latency/lead tuner, and arm/pad status panel injected into the
Capture tab. No capture card, no Zen, no Arduino.

  python glory_remoteplay_app.py                 # run
  python glory_remoteplay_app.py --window Xbox    # match a different window title
"""
import os, sys, time, argparse, importlib.util, threading
import dearpygui.dearpygui as dpg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser(description='Glory Remote Play HUD app')
    ap.add_argument('--window', default=None, help='Remote Play window title substr')
    args = ap.parse_args()

    AG = _load('gapp', '2k26_autogreen.py')
    UI = _load('gui', 'glory_ui.py')
    ENG = _load('glory_rp_engine', 'glory_rp_engine.py')
    HUD = _load('glory_rp_hud', 'glory_rp_hud.py')

    state = AG.SharedState()
    if args.window:
        state.config['remoteplay_window'] = args.window
    tuner = AG.PIDTuner(state.config.get('timing', {}))
    stop_evt = threading.Event()

    engine = ENG.RPEngine(state, state.config)
    state.rp_engine = engine                       # for the auto-tune checkbox
    state.release_lead_ms = float(state.config.get('release_lead_ms', 0.0))

    def _save():
        AG._save_config(state, tuner)

    def _stop():
        engine.stop(); stop_evt.set()

    # Build the original HUD, then inject the Remote Play panels.
    UI.build_hud(state, tuner=tuner, stop_evt=stop_evt, save_fn=_save,
                 start_fn=None, stop_fn=_stop)
    HUD.augment_capture_tab(state)

    engine.start()
    try:
        while dpg.is_dearpygui_running():
            UI.update_hud(state, tuner, stop_evt)
            HUD.update_rp_hud(state, engine)
            dpg.render_dearpygui_frame()
    finally:
        engine.stop()
        dpg.destroy_context()


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run the full test suite**

Run: `C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests/test_rp_logic.py tests/test_rp_config.py tests/test_rp_engine.py tests/test_rp_hud.py tests/test_meter_detector.py -v`
Expected: PASS (all). Fix any import path issues before proceeding.

- [ ] **Step 3: Launch smoke test (no game needed)**

Ensure no other process holds the capture/window. Run:
`C:/Users/dalei/AppData/Local/Programs/Python/Python312/python.exe glory_remoteplay_app.py`
Expected: the Glory V1 window opens with the original sidebar/theme/splash; the **Capture** tab shows the live preview (full monitor if Remote Play isn't running) and the new AUTO-GREEN panel (status lights, Make %, last-10 strip, lead slider). `Virtual pad` light = green (ViGEmBus present); `Window` light = red until the Xbox app is open. Close the window; process exits cleanly. If it crashes on a missing tag, confirm `augment_capture_tab` runs AFTER `build_hud`.

- [ ] **Step 4: Live verification (user, with Remote Play)**

1. Start the Xbox app → Remote Play → boot 2K to a shot.
2. Relaunch `glory_remoteplay_app.py`; confirm `Window` light turns green and the preview shows the game.
3. On a shot, **hold LB**: the overlay should box the magenta bar, mark the green line, and the FSM light should go HOLDING→RELEASE; `last ±px` updates and the scoreboard increments.
4. Toggle **Auto-tune lead** and take ~10 shots; the lead slider should converge and Make % should climb.
5. Verify the one open unknown: the game actually reacts to the virtual X (pad forwarding). If not, note it for the pre-launch-pad-init follow-up.

- [ ] **Step 5: Commit**

```bash
git add glory_remoteplay_app.py
git commit -m "feat(rp-hud): standalone Remote Play app wiring original HUD + engine"
```

---

## Self-Review

**Spec coverage:**
- Same HUD (glory_ui verbatim) → Task 5 reuses `build_hud`/`update_hud`. ✓
- Standalone app, capture-card app untouched → Tasks 3–5, Global Constraints (no edits to `glory_ui.py`/`2k26_autogreen.py`). ✓
- Improvement 1 meter overlay → Task 1 `draw_overlay`, applied in Task 3 `process`. ✓
- Improvement 2 scoreboard → Task 1 `scoreboard_summary`, Task 4 `rp_hud_values`/panel. ✓
- Improvement 3 lead tuner + auto-tune → Task 1 `autotune_lead`, Task 2 `save_lead`, Task 4 slider/checkbox, Task 3 `_finish_shot`. ✓
- Improvement 4 arm/pad status → Task 3 sets `rp_*` flags, Task 4 lights. ✓
- Error handling (no window/pad/controller, MAX_HOLD) → Task 3 `init_io`/`_Pad`/`process`. ✓
- Config key `remoteplay_window` → Task 2. ✓
- Success criteria 1–7 → Tasks 3–5 tests + Task 5 live steps. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `RPEngine.process(frame, lb_held, now)`, `_finish_shot(landing_px, now)`, `rp_hud_values(state, engine)`, `scoreboard_summary(session_shots, miss_px)`, `autotune_lead(lead_ms, result, ...)`, `classify_landing(landing_px, tol)`, `draw_overlay(preview, gz, full_h, full_w, landing_y)` — names/params identical across tasks. Result strings `'green'|'early'|'late'` consistent. `state.rp_lb_held/rp_pad_connected/rp_window_locked/rp_engine` set in Task 3/5, read in Task 4. ✓

**Refinements over spec (both reduce risk):** single engine thread instead of three (one clock, no races); additive HUD injection instead of swapping sidebar inputs (zero edits to `glory_ui.py`). Noted in the architecture line.
