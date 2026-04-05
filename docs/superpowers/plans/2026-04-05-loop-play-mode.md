# Loop Play Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 16-step drum-machine sequencer mode to the LaunchKey Mini MK2 synthesizer, toggled by the top play button (CC 108), with LED feedback via the InControl MIDI output port.

**Architecture:** A `SequencerState` dataclass holds loop mode state (on/off, 16-step pattern, playhead position, active note). A dedicated `sequencer_loop` thread advances the playhead every 1/16 note, plays active steps, and updates pad LEDs. The existing `dispatch` function is extended to handle CC 108 (mode toggle), pad presses (step toggle in loop mode), and key presses (set note in loop mode).

**Tech Stack:** Python 3.14, mido, numpy, sounddevice, pytest (new dev dependency)

---

## File Map

| File | Change |
|------|--------|
| `main.py` | Add `SequencerState`, `set_pad_leds`, `clear_pad_leds`, `sequencer_loop`; extend `dispatch`; update `main()` |
| `config.toml` | Add `midi.port_out` and `[loop]` section |
| `CONFIGURATION.md` | Document new config keys |
| `AGENT.md` | Update data-flow and concurrency tables |
| `pyproject.toml` | Add pytest dev dependency |
| `tests/test_loop.py` | Unit tests for all new logic |

---

## Task 1: Add pytest and create test skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/test_loop.py`

- [ ] **Step 1: Add pytest to pyproject.toml**

Replace the `[project]` block so it reads:

```toml
[project]
name = "testnovation"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "mido>=1.3.3",
    "numpy>=2.4.4",
    "python-rtmidi>=1.5.8",
    "sounddevice>=0.5.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 2: Install pytest**

```bash
uv sync --group dev
```

Expected: resolves and installs pytest, no errors.

- [ ] **Step 3: Create empty test package**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 4: Create test file with shared helpers**

Create `tests/test_loop.py`:

```python
"""Unit tests for loop play mode — SequencerState, LED helpers, dispatch."""
import threading
from unittest.mock import MagicMock, patch, call

import mido
import pytest

import main as m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockPort:
    """Records note_on messages sent to it."""
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def fresh_seq():
    """Return a new default SequencerState."""
    return m.SequencerState()


LOOP_CFG = {
    'bpm': 120,
    'pad_notes': [40, 41, 42, 43, 44, 45, 46, 47,
                  48, 49, 50, 51, 52, 53, 54, 55],
    'led_playhead': 12,
    'led_active':   15,
    'led_off':       0,
}
```

- [ ] **Step 5: Verify pytest discovers the file**

```bash
uv run pytest tests/test_loop.py --collect-only
```

Expected output (no errors, 0 tests collected yet):
```
collected 0 items
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock tests/__init__.py tests/test_loop.py
git commit -m "chore: add pytest and test skeleton for loop play mode"
```

---

## Task 2: SequencerState dataclass

**Files:**
- Modify: `main.py` (after imports, before helpers)
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loop.py`:

```python
# ---------------------------------------------------------------------------
# SequencerState
# ---------------------------------------------------------------------------

def test_sequencer_state_defaults():
    seq = m.SequencerState()
    assert seq.loop_mode is False
    assert seq.steps == [False] * 16
    assert seq.current_step == 0
    assert seq.loop_note == 60
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_loop.py::test_sequencer_state_defaults -v
```

Expected: FAIL — `AttributeError: module 'main' has no attribute 'SequencerState'`

- [ ] **Step 3: Add SequencerState and module-level globals to main.py**

After the imports block (after `import sounddevice as sd`) in `main.py`, add:

```python
import dataclasses

@dataclasses.dataclass
class SequencerState:
    loop_mode:    bool      = False
    steps:        list      = dataclasses.field(default_factory=lambda: [False] * 16)
    current_step: int       = 0
    loop_note:    int       = 60


# Sequencer globals — shared between main thread and sequencer thread
seq       = SequencerState()
_stop_seq = threading.Event()
_stop_seq.set()   # set = sequencer not running
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/test_loop.py::test_sequencer_state_defaults -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_loop.py
git commit -m "feat: add SequencerState dataclass and module globals"
```

---

## Task 3: set_pad_leds and clear_pad_leds

**Files:**
- Modify: `main.py` (add after `SequencerState` block)
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loop.py`:

```python
# ---------------------------------------------------------------------------
# set_pad_leds
# ---------------------------------------------------------------------------

def test_set_pad_leds_playhead_color():
    """Current step gets led_playhead velocity."""
    outport = MockPort()
    steps = [False] * 16
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    # note=40 is pad 0 (current_step), must get playhead velocity
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 12   # led_playhead


def test_set_pad_leds_active_color():
    """Active non-current step gets led_active velocity."""
    outport = MockPort()
    steps = [False] * 16
    steps[3] = True   # pad 3 is on, but current_step is 0
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    msg = next(msg for msg in outport.sent if msg.note == 43)  # pad 3
    assert msg.velocity == 15   # led_active


def test_set_pad_leds_inactive_color():
    """Inactive non-current step gets led_off velocity."""
    outport = MockPort()
    steps = [False] * 16
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    msg = next(msg for msg in outport.sent if msg.note == 47)  # pad 7, off
    assert msg.velocity == 0    # led_off


def test_set_pad_leds_sends_all_16():
    """Exactly 16 note_on messages are sent."""
    outport = MockPort()
    m.set_pad_leds(outport, [False] * 16, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    assert len(outport.sent) == 16


def test_clear_pad_leds_sends_velocity_zero():
    """clear_pad_leds sends velocity=0 for every pad."""
    outport = MockPort()
    m.clear_pad_leds(outport, LOOP_CFG['pad_notes'])
    assert len(outport.sent) == 16
    assert all(msg.velocity == 0 for msg in outport.sent)
```

- [ ] **Step 2: Run to verify failures**

```bash
uv run pytest tests/test_loop.py -k "pad_leds" -v
```

Expected: 5 FAILs — `AttributeError: module 'main' has no attribute 'set_pad_leds'`

- [ ] **Step 3: Implement set_pad_leds and clear_pad_leds in main.py**

Add after the `_stop_seq` line (before the helpers section):

```python
# ---------------------------------------------------------------------------
# LED helpers
# ---------------------------------------------------------------------------

def set_pad_leds(outport, steps, current_step, pad_notes, loop_cfg):
    """Send a note_on to the InControl port for every pad to update colours."""
    playhead_vel = loop_cfg.get('led_playhead', 12)
    active_vel   = loop_cfg.get('led_active',   15)
    off_vel      = loop_cfg.get('led_off',        0)
    for i, note in enumerate(pad_notes):
        if i == current_step:
            vel = playhead_vel
        elif steps[i]:
            vel = active_vel
        else:
            vel = off_vel
        outport.send(mido.Message('note_on', channel=0, note=note, velocity=vel))


def clear_pad_leds(outport, pad_notes):
    """Turn off all pad LEDs."""
    for note in pad_notes:
        outport.send(mido.Message('note_on', channel=0, note=note, velocity=0))
```

- [ ] **Step 4: Run to verify all pass**

```bash
uv run pytest tests/test_loop.py -k "pad_leds" -v
```

Expected: 5 PASSes

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_loop.py
git commit -m "feat: add set_pad_leds and clear_pad_leds helpers"
```

---

## Task 4: Extend dispatch — CC 108 toggles loop mode

**Files:**
- Modify: `main.py` — `dispatch` function signature and body
- Modify: `tests/test_loop.py`

The `dispatch` signature gains three new trailing parameters: `seq`, `outport`, `loop_cfg`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loop.py`:

```python
# ---------------------------------------------------------------------------
# dispatch — CC 108 (play button)
# ---------------------------------------------------------------------------

def _dispatch_cc(value, seq=None, outport=None):
    """Helper: send CC 108 through dispatch."""
    if seq is None:
        seq = fresh_seq()
    if outport is None:
        outport = MockPort()
    msg = mido.Message('control_change', channel=0, control=108, value=value)
    with patch('main.threading.Thread') as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        m.dispatch(msg, ch_keys=0, ch_pads=9,
                   keys_sound='piano', pads_sound='drums', sounds_cfg={},
                   seq=seq, outport=outport, loop_cfg=LOOP_CFG)
        return seq, outport, mock_thread_cls


def test_cc108_press_enters_loop_mode():
    seq, outport, mock_thread_cls = _dispatch_cc(value=127)
    assert seq.loop_mode is True
    assert seq.current_step == 0
    mock_thread_cls.return_value.start.assert_called_once()


def test_cc108_press_exits_loop_mode():
    seq = fresh_seq()
    seq.loop_mode = True
    _dispatch_cc(value=127, seq=seq)
    assert seq.loop_mode is False


def test_cc108_release_ignored():
    """Value=0 (button release) must not change loop_mode."""
    seq, _, _ = _dispatch_cc(value=0)
    assert seq.loop_mode is False


def test_cc108_exit_clears_leds():
    """Exiting loop mode sends velocity=0 for all 16 pads."""
    seq = fresh_seq()
    seq.loop_mode = True
    _, outport, _ = _dispatch_cc(value=127, seq=seq)
    assert len(outport.sent) == 16
    assert all(msg.velocity == 0 for msg in outport.sent)
```

- [ ] **Step 2: Run to verify failures**

```bash
uv run pytest tests/test_loop.py -k "cc108" -v
```

Expected: 4 FAILs — `TypeError: dispatch() got unexpected keyword argument 'seq'`

- [ ] **Step 3: Update dispatch signature and add CC 108 handling in main.py**

Replace the entire `dispatch` function with:

```python
def dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg,
             seq, outport, loop_cfg):
    # -----------------------------------------------------------------------
    # Play button: CC 108 ch0 value=127 → toggle loop mode
    # -----------------------------------------------------------------------
    if msg.type == 'control_change' and msg.channel == 0 and msg.control == 108:
        if msg.value == 127:
            with _lock:
                seq.loop_mode = not seq.loop_mode
                entering = seq.loop_mode
                if entering:
                    seq.current_step = 0
            if entering:
                _stop_seq.clear()
                t = threading.Thread(
                    target=sequencer_loop,
                    args=(seq, outport, loop_cfg, pads_sound, sounds_cfg),
                    daemon=True,
                )
                t.start()
            else:
                _stop_seq.set()
                clear_pad_leds(outport, loop_cfg.get('pad_notes', []))
        return

    if msg.type != 'note_on' or msg.velocity == 0:
        return

    # -----------------------------------------------------------------------
    # Normal mode — play sound immediately
    # -----------------------------------------------------------------------
    if msg.channel == ch_keys:
        samples = make_sound(msg.note, msg.velocity, keys_sound, sounds_cfg)
    elif msg.channel == ch_pads:
        samples = make_sound(msg.note, msg.velocity, pads_sound, sounds_cfg)
    else:
        return
    if samples is not None:
        with _lock:
            _active.append([samples, 0])
```

Note: `sequencer_loop` is referenced here but defined in Task 6. Add a stub for now so the tests can import without error — add this right after `clear_pad_leds`:

```python
def sequencer_loop(seq, outport, loop_cfg, pads_sound, sounds_cfg):
    """Step sequencer thread — implemented in full in Task 6."""
    pass
```

- [ ] **Step 4: Update the call-site in main() to pass the new args**

In `main()`, find:

```python
                    dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg)
```

Replace with:

```python
                    dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg,
                             seq, outport, loop_cfg)
```

(The `outport` variable will exist after Task 8 wires the output port. Keep this edit now so the signature is consistent.)

- [ ] **Step 5: Run to verify CC tests pass**

```bash
uv run pytest tests/test_loop.py -k "cc108" -v
```

Expected: 4 PASSes

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_loop.py
git commit -m "feat: extend dispatch to toggle loop mode on CC 108"
```

---

## Task 5: dispatch — pad press toggles step in loop mode

**Files:**
- Modify: `main.py` — `dispatch` body (loop-mode pad branch)
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Add _lock import to test file top**

In `tests/test_loop.py`, after `import main as m`, add:

```python
from main import _lock
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_loop.py`:

```python
# ---------------------------------------------------------------------------
# dispatch — pad press in loop mode
# ---------------------------------------------------------------------------

def _pad_press(note, seq=None, outport=None):
    """Helper: send a pad note_on while in loop mode."""
    if seq is None:
        seq = fresh_seq()
        seq.loop_mode = True
    if outport is None:
        outport = MockPort()
    msg = mido.Message('note_on', channel=9, note=note, velocity=100)
    m.dispatch(msg, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    return seq, outport


def test_pad_press_toggles_step_on():
    seq, _ = _pad_press(note=40)   # pad 0 (first in pad_notes)
    assert seq.steps[0] is True


def test_pad_press_toggles_step_off():
    seq, _ = _pad_press(note=40)   # on
    _pad_press(note=40, seq=seq)   # off
    assert seq.steps[0] is False


def test_pad_press_sends_orange_led_when_on():
    _, outport = _pad_press(note=40)
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 15      # led_active (orange)


def test_pad_press_sends_off_led_when_toggled_off():
    seq, outport = _pad_press(note=40)   # on
    outport.sent.clear()
    _pad_press(note=40, seq=seq, outport=outport)   # off
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 0       # led_off


def test_pad_press_in_loop_mode_does_not_play_audio():
    """No audio buffers should be added when toggling a step."""
    with _lock:
        m._active.clear()
    _pad_press(note=40)
    with _lock:
        assert m._active == []


def test_pad_press_unknown_note_ignored():
    """A pad note not in pad_notes list must not crash or change any step."""
    seq, _ = _pad_press(note=99)   # not in LOOP_CFG['pad_notes']
    assert seq.steps == [False] * 16
```

- [ ] **Step 3: Run to verify failures**

```bash
uv run pytest tests/test_loop.py -k "pad_press" -v
```

Expected: 6 FAILs — steps are never toggled (loop-mode branch not yet implemented).

- [ ] **Step 4: Add loop-mode pad branch in dispatch**

In `dispatch`, insert the following **before** the existing normal-mode block (i.e., between the `return` after CC handling and the normal-mode `if msg.channel == ch_keys` line):

```python
    # -----------------------------------------------------------------------
    # Loop mode — pad toggles step; key sets note
    # -----------------------------------------------------------------------
    with _lock:
        in_loop = seq.loop_mode

    if in_loop:
        if msg.channel == ch_pads:
            pad_notes = loop_cfg.get('pad_notes', [])
            if msg.note in pad_notes:
                i = pad_notes.index(msg.note)
                with _lock:
                    seq.steps[i] = not seq.steps[i]
                    vel = (loop_cfg.get('led_active', 15)
                           if seq.steps[i]
                           else loop_cfg.get('led_off', 0))
                outport.send(mido.Message('note_on', channel=0,
                                          note=msg.note, velocity=vel))
        elif msg.channel == ch_keys:
            with _lock:
                seq.loop_note = msg.note
        return
```

- [ ] **Step 5: Run to verify all pad_press tests pass**

```bash
uv run pytest tests/test_loop.py -k "pad_press" -v
```

Expected: 6 PASSes

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_loop.py
git commit -m "feat: pad presses toggle sequencer steps in loop mode"
```

---

## Task 6: dispatch — key press sets loop note in loop mode

**Files:**
- Modify: `tests/test_loop.py`
- (dispatch already handles this — just missing tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loop.py`:

```python
# ---------------------------------------------------------------------------
# dispatch — key press in loop mode
# ---------------------------------------------------------------------------

def test_key_press_sets_loop_note():
    seq = fresh_seq()
    seq.loop_mode = True
    outport = MockPort()
    msg = mido.Message('note_on', channel=0, note=65, velocity=80)
    m.dispatch(msg, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    assert seq.loop_note == 65


def test_key_press_in_loop_mode_does_not_play_audio():
    with _lock:
        m._active.clear()
    seq = fresh_seq()
    seq.loop_mode = True
    outport = MockPort()
    msg = mido.Message('note_on', channel=0, note=65, velocity=80)
    m.dispatch(msg, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    with _lock:
        assert m._active == []
```

- [ ] **Step 2: Run to verify failures**

```bash
uv run pytest tests/test_loop.py -k "key_press" -v
```

Expected: 2 FAILs (loop_note stays at 60 default, not 65).

- [ ] **Step 3: Verify the key branch exists in dispatch**

The key branch (`elif msg.channel == ch_keys: seq.loop_note = msg.note`) was already added in Task 5 Step 4. If the tests still fail, confirm the branch is present in `main.py` inside the `if in_loop:` block.

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/test_loop.py -k "key_press" -v
```

Expected: 2 PASSes

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_loop.py
git commit -m "test: key press sets loop_note in loop mode"
```

---

## Task 7: sequencer_loop thread

**Files:**
- Modify: `main.py` — replace the stub `sequencer_loop` with full implementation

No additional unit tests for the timing loop (hardware-dependent). Instead this task verifies manually.

- [ ] **Step 1: Replace the sequencer_loop stub in main.py**

Find the stub:

```python
def sequencer_loop(seq, outport, loop_cfg, pads_sound, sounds_cfg):
    """Step sequencer thread — implemented in full in Task 6."""
    pass
```

Replace with:

```python
def sequencer_loop(seq, outport, loop_cfg, pads_sound, sounds_cfg):
    """Advance the step sequencer at 1/16-note intervals.

    Runs in a daemon thread. Exits when _stop_seq is set.
    """
    bpm      = loop_cfg.get('bpm', 120)
    interval = 60.0 / (bpm * 4)      # seconds per 1/16 note
    pad_notes = loop_cfg.get('pad_notes', [])

    while not _stop_seq.wait(timeout=interval):
        with _lock:
            step   = seq.current_step
            active = seq.steps[step]
            note   = seq.loop_note
            steps_snapshot = list(seq.steps)

        if active:
            samples = make_sound(note, 100, pads_sound, sounds_cfg)
            if samples is not None:
                with _lock:
                    _active.append([samples, 0])

        set_pad_leds(outport, steps_snapshot, step, pad_notes, loop_cfg)

        with _lock:
            seq.current_step = (step + 1) % 16
```

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: implement sequencer_loop thread (1/16 note step advance)"
```

---

## Task 8: Wire output port and loop config in main()

**Files:**
- Modify: `main.py` — `main()` function
- Modify: `config.toml`

- [ ] **Step 1: Add loop section and port_out to config.toml**

Add after the `[midi]` block:

```toml
[midi]
port         = "Launchkey Mini LK Mini MIDI"
port_out     = "Launchkey Mini LK Mini InControl"
channel_keys = 0
channel_pads = 9
```

And add a new `[loop]` section at the end of the file:

```toml
# -----------------------------------------------------------------------------
# Loop play mode — step sequencer
# -----------------------------------------------------------------------------
[loop]
bpm          = 120
# MIDI note numbers the 16 pads send, ordered left-to-right, top row first.
pad_notes    = [40, 41, 42, 43, 44, 45, 46, 47,
                48, 49, 50, 51, 52, 53, 54, 55]
# LED velocity values for the InControl port.
# LaunchKey Mini MK2 bi-color encoding: bits[3:2]=green, bits[1:0]=red
led_playhead = 12   # full green — current step
led_active   = 15   # orange (red+green) — step is on
led_off      = 0    # off
```

- [ ] **Step 2: Update main() to open the output port and pass loop_cfg**

Replace the existing `main()` function with:

```python
def main():
    cfg        = load_config()
    midi_cfg   = cfg.get('midi', {})
    track_cfg  = cfg.get('track', {})
    sounds_cfg = cfg.get('sounds', {})
    loop_cfg   = cfg.get('loop', {})

    port        = midi_cfg.get('port',     'Launchkey Mini LK Mini MIDI')
    port_out    = midi_cfg.get('port_out', 'Launchkey Mini LK Mini InControl')
    ch_keys     = midi_cfg.get('channel_keys', 0)
    ch_pads     = midi_cfg.get('channel_pads', 9)
    keys_sound  = track_cfg.get('keys', 'piano')
    pads_sound  = track_cfg.get('pads', 'drums')

    print(f"Listening on : {port}")
    print(f"LED output   : {port_out}")
    print(f"Keys sound   : {keys_sound}")
    print(f"Pads sound   : {pads_sound}")
    print(f"Loop BPM     : {loop_cfg.get('bpm', 120)}")
    print("Ctrl-C to quit\n")

    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1,
                             dtype='float32', blocksize=512,
                             callback=audio_callback):
            with mido.open_output(port_out) as outport:
                with mido.open_input(port) as inport:
                    for msg in inport:
                        dispatch(msg, ch_keys, ch_pads,
                                 keys_sound, pads_sound, sounds_cfg,
                                 seq, outport, loop_cfg)
    except KeyboardInterrupt:
        _stop_seq.set()
        print("Goodbye!")
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add main.py config.toml
git commit -m "feat: wire loop mode — open InControl output port, pass loop_cfg to dispatch"
```

---

## Task 9: Update documentation

**Files:**
- Modify: `CONFIGURATION.md`
- Modify: `AGENT.md`

- [ ] **Step 1: Add loop config docs to CONFIGURATION.md**

Append to `CONFIGURATION.md` after the `[sounds]` section:

````markdown
---

## `[midi] port_out`

| Key        | Type   | Default                                  | Description |
|------------|--------|------------------------------------------|-------------|
| `port_out` | string | `"Launchkey Mini LK Mini InControl"`     | MIDI output port for pad LED control. Run `python3 -c "import mido; print(mido.get_output_names())"` to list available ports. |

---

## `[loop]`

Step sequencer configuration. Active when loop play mode is enabled (press the top play button).

| Key           | Type         | Default | Description |
|---------------|--------------|---------|-------------|
| `bpm`         | int          | `120`   | Tempo in beats per minute. Determines 1/16-note interval. |
| `pad_notes`   | array[int]   | see below | MIDI note numbers the 16 pads send, ordered left-to-right, top row first. |
| `led_playhead`| int          | `12`    | LED velocity for the current playhead step (green on MK2). |
| `led_active`  | int          | `15`    | LED velocity for active (on) steps that are not the playhead (orange on MK2). |
| `led_off`     | int          | `0`     | LED velocity for inactive steps (off). |

**Default `pad_notes`:**
```toml
pad_notes = [40, 41, 42, 43, 44, 45, 46, 47,
             48, 49, 50, 51, 52, 53, 54, 55]
```
Top row left→right: 40–47. Bottom row left→right: 48–55. Adjust if your device sends different note numbers (press pads while running `python3 -c "import mido; port=mido.open_input('Launchkey Mini LK Mini MIDI'); [print(m) for m in port]"` to verify).

**LED colour encoding (LaunchKey Mini MK2 bi-color):**
Velocity bits `[3:2]` = green level, bits `[1:0]` = red level (each 0–3). `12` = full green, `15` = orange, `3` = full red, `0` = off.
````

- [ ] **Step 2: Update the data flow diagram in AGENT.md**

In `AGENT.md`, replace the `## Data Flow` section with:

````markdown
## Data Flow

```
LaunchKey Mini MK2 (USB)
        │
        │  MIDI Note On / CC
        ▼
   mido.open_input()          — blocking iterator on main thread
        │
        ▼
     dispatch()               — routes message by mode and MIDI channel
        │
        ├─ CC 108 ch0 value=127  → toggle loop_mode (start/stop SequencerThread)
        │
        ├─ [loop mode] ch_pads  → toggle step on/off, update pad LED via InControl port
        ├─ [loop mode] ch_keys  → set seq.loop_note (no audio)
        │
        ├─ [normal] channel_keys → make_sound(keys_sound, …)
        └─ [normal] channel_pads → make_sound(pads_sound, …)
                │
                ▼
        sound generator        — numpy synthesis, returns float32 buffer
                │
                ▼
          _active list          — thread-safe mixer queue
                │
                ▼
       audio_callback()        — sounddevice real-time thread
                │              sums all active buffers, clips to [-1, 1]
                ▼
        System Audio Out


LaunchKey Mini MK2 InControl port  ←── set_pad_leds() / clear_pad_leds()
        ↑                                        ↑
        └────────────── SequencerThread ─────────┘
                        (sequencer_loop, daemon thread)
                        advances step every 1/16 note @ BPM
```
````

- [ ] **Step 3: Update the concurrency table in AGENT.md**

Replace the `## Concurrency Model` table with:

```markdown
## Concurrency Model

| Thread | Responsibility |
|--------|---------------|
| Main thread | Reads MIDI messages, generates sound buffers on normal note-on, toggles loop mode on CC 108, updates `_active` |
| Sequencer thread | Advances playhead every 1/16 note, triggers sounds for active steps, updates pad LEDs via InControl port |
| sounddevice thread | Runs `audio_callback` per audio block, consumes `_active` |

`_active` and all `SequencerState` fields are protected by `threading.Lock`. `_stop_seq` (`threading.Event`) signals the sequencer thread to exit cleanly.
```

- [ ] **Step 4: Commit docs**

```bash
git add CONFIGURATION.md AGENT.md
git commit -m "docs: document loop play mode config and updated architecture"
```

---

## Manual Smoke Test (after all tasks complete)

1. Connect the LaunchKey Mini MK2 via USB and enable InControl mode.
2. Run: `uv run python main.py`
3. Verify startup prints `LED output: Launchkey Mini LK Mini InControl`.
4. **Enter loop mode:** press the top play button. Pad 0 (top-left) should glow green and advance left-to-right every 125 ms.
5. **Toggle steps:** tap pads while the sequencer runs. Lit pads turn orange; the green playhead keeps moving.
6. **Set note:** press a piano key. Active steps should now play at that pitch.
7. **Exit loop mode:** press the play button again. All LEDs go dark. Pressing pads plays drum sounds as before.
8. If pad LEDs show wrong colours, adjust `led_playhead` / `led_active` in `config.toml` to match your device's response.
