# CONFIGURATION.md — config.toml Reference

## `[midi]`

MIDI device and channel routing.

| Key            | Type   | Default                           | Description |
|----------------|--------|-----------------------------------|-------------|
| `port`         | string | `"Launchkey Mini LK Mini MIDI"`   | Exact MIDI input port name. Run `python3 -c "import mido; print(mido.get_input_names())"` to list available ports. |
| `port_out`     | string | `"Launchkey Mini LK Mini InControl"` | MIDI output port for pad LED control. Run `python3 -c "import mido; print(mido.get_output_names())"` to list available ports. |
| `channel_keys` | int    | `0`                               | MIDI channel (0-indexed) used by keyboard keys. `0` = ch1 (InControl mode). `8` = ch9 (normal mode). |
| `channel_pads` | int    | `9`                               | MIDI channel (0-indexed) used by pads. Always `9` (ch10) on the LaunchKey Mini MK2. |

## `[track]`

Selects which sound preset each input plays. Values must match a key defined under `[sounds]`.

| Key    | Type   | Default   | Description |
|--------|--------|-----------|-------------|
| `keys` | string | `"piano"` | Sound preset for keyboard keys. |
| `pads` | string | `"drums"` | Sound preset for pads. |

**Example — switch keys to guitar:**
```toml
[track]
keys = "guitar"
pads = "drums"
```

---

## `[sounds.<name>]`

Each named block under `[sounds]` defines a sound preset.
The `type` field selects the synthesis engine. All other fields are engine-specific.

### Common field

| Key      | Type  | Default | Description |
|----------|-------|---------|-------------|
| `type`   | string | (required) | Synthesis engine: `"piano"`, `"guitar"`, `"organ"`, `"drums"`, `"bells"`. |
| `volume` | float | engine default | Output volume scale (0.0–1.0). Applied after velocity curve. |

---

### type = `"piano"`

Additive synthesis — fundamental plus harmonics, two-stage exponential decay.

| Key          | Type          | Default                              | Description |
|--------------|---------------|--------------------------------------|-------------|
| `volume`     | float         | `0.4`                                | Output volume scale. |
| `harmonics`  | array[float]  | `[1.0, 0.50, 0.25, 0.12, 0.06, 0.03]` | Amplitude of each harmonic partial (index 0 = fundamental). |
| `decay_fast` | float         | `6.0`                                | Exponent for the fast initial decay. Higher = shorter initial drop. |
| `decay_slow` | float         | `1.2`                                | Exponent for the slow sustain tail. Higher = faster fade-out. |
| `attack_ms`  | float         | `5`                                  | Attack time in milliseconds. |

Higher notes automatically decay faster regardless of `decay_fast`/`decay_slow`.
Velocity controls brightness — harder hits emphasise upper harmonics.

---

### type = `"guitar"`

Karplus-Strong plucked string synthesis. Initialises a ring buffer with noise and smooths it each cycle to simulate a vibrating string.

| Key        | Type  | Default | Description |
|------------|-------|---------|-------------|
| `volume`   | float | `0.5`   | Output volume scale. |
| `decay`    | float | `0.996` | Per-sample damping factor (0–1). Closer to 1 = longer sustain. Lower = more muted/percussive. |
| `duration` | float | `2.5`   | Maximum note length in seconds. |

---

### type = `"organ"`

Sustained additive synthesis — all harmonics held at constant level with a slow attack, like a Hammond organ drawbar.

| Key          | Type         | Default                        | Description |
|--------------|--------------|--------------------------------|-------------|
| `volume`     | float        | `0.3`                          | Output volume scale. |
| `harmonics`  | array[float] | `[1.0, 0.50, 0.33, 0.25, 0.20]` | Amplitude of each harmonic partial. |
| `attack_ms`  | float        | `15`                           | Attack time in milliseconds. |
| `release_ms` | float        | `50`                           | Release time in milliseconds. |
| `duration`   | float        | `1.5`                          | Note length in seconds. |

---

### type = `"drums"`

Noise burst mixed with a sine tone at the MIDI note frequency, with exponential decay.

| Key          | Type  | Default | Description |
|--------------|-------|---------|-------------|
| `volume`     | float | `0.6`   | Output volume scale. |
| `tone_mix`   | float | `0.4`   | Balance between sine tone and noise. `0.0` = pure noise (snare-like), `1.0` = pure tone (tom-like). |
| `decay_rate` | float | `18.0`  | Decay exponent. Higher = shorter, snappier hit. |
| `duration`   | float | `0.25`  | Maximum hit length in seconds. |

---

### type = `"bells"`

Inharmonic additive synthesis. Uses fixed partial ratios (1×, 2.76×, 5.40×) that give a metallic bell character regardless of the `harmonics` amplitudes.

| Key          | Type         | Default            | Description |
|--------------|--------------|--------------------|-------------|
| `volume`     | float        | `0.4`              | Output volume scale. |
| `harmonics`  | array[float] | `[1.0, 0.25, 0.06]` | Amplitude of each of the three inharmonic partials. |
| `decay_rate` | float        | `0.8`              | Decay exponent. Lower = longer ring (church bell). Higher = shorter (cowbell). |
| `attack_ms`  | float        | `2`                | Attack time in milliseconds. |
| `duration`   | float        | `2.5`              | Note length in seconds. |

---

## Preset recipes

**Bright piano:**
```toml
[sounds.bright_piano]
type       = "piano"
volume     = 0.4
harmonics  = [1.0, 0.70, 0.40, 0.20, 0.10, 0.05]
decay_fast = 8.0
decay_slow = 1.5
attack_ms  = 3
```

**Muted guitar:**
```toml
[sounds.muted_guitar]
type     = "guitar"
volume   = 0.5
decay    = 0.980
duration = 1.0
```

**Church bells:**
```toml
[sounds.church_bells]
type       = "bells"
volume     = 0.35
harmonics  = [1.0, 0.30, 0.08]
decay_rate = 0.3
attack_ms  = 5
duration   = 4.0
```

**Kick drum (pads):**
```toml
[sounds.kick]
type       = "drums"
volume     = 0.7
tone_mix   = 0.8
decay_rate = 25.0
duration   = 0.3
```

**Snare drum (pads):**
```toml
[sounds.snare]
type       = "drums"
volume     = 0.6
tone_mix   = 0.1
decay_rate = 20.0
duration   = 0.2
```

---

## `[loop]`

Step sequencer configuration. Active when loop play mode is enabled (press the top play button).

| Key           | Type         | Default | Description |
|---------------|--------------|---------|-------------|
| `bpm`         | int          | `120`   | Tempo in beats per minute. Determines 1/16-note interval. |
| `pad_notes`   | array[int]   | `[]` | MIDI note numbers the 16 pads send, ordered left-to-right, top row first. |
| `led_playhead`| int          | `12`    | LED velocity for the current playhead step (green on MK2). |
| `led_active`  | int          | `15`    | LED velocity for active (on) steps that are not the playhead (orange on MK2). |
| `led_off`     | int          | `0`     | LED velocity for inactive steps (off). |

**Recommended `pad_notes` for LaunchKey Mini MK2:**
```toml
pad_notes = [40, 41, 42, 43, 44, 45, 46, 47,
             48, 49, 50, 51, 52, 53, 54, 55]
```
Top row left→right: 40–47. Bottom row left→right: 48–55. Adjust if your device sends different note numbers (press pads while running `python3 -c "import mido; port=mido.open_input('Launchkey Mini LK Mini MIDI'); [print(m) for m in port]"` to verify).

**LED colour encoding (LaunchKey Mini MK2 bi-color):**
Velocity bits `[3:2]` = green level, bits `[1:0]` = red level (each 0–3). `12` = full green, `15` = orange, `3` = full red, `0` = off.

---
