# Loop Play Mode — Design Spec
_Date: 2026-04-05_

## Overview

Add a 16-step sequencer (loop play mode) to the LaunchKey Mini MK2 synthesizer. Pressing the top play button toggles the mode. In loop mode the 16 pads act as step toggles for a one-bar pattern; a moving green LED marks the playhead and orange LEDs mark active steps. Pressing a piano key sets the pitch played on every active step.

---

## 1. Trigger

| Event | MIDI message | Action |
|-------|-------------|--------|
| Play button press | `control_change channel=0 control=108 value=127` | Toggle loop mode on/off |
| Play button release | `control_change channel=0 control=108 value=0` | Ignored |

---

## 2. State

A `SequencerState` dataclass holds all sequencer state, shared between the MIDI input thread and the sequencer thread via the existing `_lock`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `loop_mode` | `bool` | `False` | Whether the sequencer is running |
| `steps` | `list[bool]` (16) | all `False` | Which steps are active |
| `current_step` | `int` | `0` | Current playhead position (0–15) |
| `loop_note` | `int` | `60` | MIDI note played on active steps (middle C default) |

---

## 3. Pad Behaviour by Mode

### Not in loop mode (existing behaviour)
- `note_on` on `ch_pads` → play `pads_sound` at the pressed note

### In loop mode
- `note_on` on `ch_pads` → look up step index from `pad_notes` config list → toggle `steps[i]` → update that pad's LED (orange if on, off if off); no audio
- `note_on` on `ch_keys` → set `seq.loop_note` to the pressed note; no audio

---

## 4. Sequencer Thread

Runs in a dedicated thread, created on loop mode entry and stopped on exit.

**Step interval:** `60 / (bpm * 4)` seconds = 0.125 s at 120 BPM

**Stop signal:** `threading.Event` (`_stop_seq`). Uses `_stop_seq.wait(timeout=interval)` so the thread wakes immediately on exit — no sleep delay.

**Per-tick logic:**
1. Snapshot `current_step`, `steps[current_step]`, `loop_note` under `_lock`
2. If the step is active: trigger `make_sound(loop_note, velocity=100, pads_sound, sounds_cfg)` and append to `_active`
3. Call `set_pad_leds(...)` to update all 16 pad LEDs
4. Advance `current_step = (current_step + 1) % 16` under `_lock`

**Thread lifecycle:**
```
enter loop mode → _stop_seq.clear() → Thread(target=sequencer_loop).start()
exit loop mode  → _stop_seq.set()  → thread exits → clear all pad LEDs
```

---

## 5. LED Control

### Output port
Send `note_on` messages to `'Launchkey Mini LK Mini InControl'`, opened at startup via `mido.open_output(port_out)`.

### Color encoding (LaunchKey Mini MK2 bi-color LEDs)
Velocity bits: `bits[3:2]` = green level, `bits[1:0]` = red level (each 0–3).

| Colour | Velocity | Use |
|--------|----------|-----|
| Green  | `12` (`0b1100`) | Playhead (current step) |
| Orange | `15` (`0b1111`) | Active step (not current) |
| Off    | `0`  | Inactive step |

### `set_pad_leds(outport, steps, current_step, pad_notes, loop_cfg)`
Sends one `note_on` per pad (all 16) on channel 0. Called every tick and once on mode exit (all velocity 0 to clear).

---

## 6. Configuration Changes

### `config.toml` additions

```toml
[midi]
port_out = "Launchkey Mini LK Mini InControl"

[loop]
bpm          = 120
pad_notes    = [40, 41, 42, 43, 44, 45, 46, 47,
                48, 49, 50, 51, 52, 53, 54, 55]
led_playhead = 12
led_active   = 15
led_off      = 0
```

`pad_notes` lists the MIDI note number each pad sends, ordered left-to-right, top row first then bottom row. Adjust if the device layout differs.

---

## 7. Concurrency

| Thread | Reads | Writes |
|--------|-------|--------|
| Main (MIDI input) | `seq.loop_mode` | `seq.loop_mode`, `seq.steps[i]`, `seq.loop_note` |
| Sequencer | `seq.steps`, `seq.current_step`, `seq.loop_note` | `seq.current_step` |
| Audio callback | `_active` | `_active` |

All access to `seq` fields and `_active` is guarded by `_lock`.

---

## 8. File Changes

| File | Change |
|------|--------|
| `main.py` | Add `SequencerState`, `sequencer_loop`, `set_pad_leds`; extend `dispatch` for CC and loop-mode pad/key handling; open output port in `main()` |
| `config.toml` | Add `[midi] port_out`, `[loop]` section |
| `CONFIGURATION.md` | Document new config keys |
| `AGENT.md` | Update data flow and concurrency tables |
