# CONFIGURATION.md — config.toml Reference

## `[midi]`

MIDI device and channel routing.

| Key            | Type   | Default                           | Description |
|----------------|--------|-----------------------------------|-------------|
| `port`         | string | `"Launchkey Mini LK Mini MIDI"`   | Exact MIDI input port name. Run `python3 -c "import mido; print(mido.get_input_names())"` to list available ports. |
| `channel_keys` | int    | `0`                               | MIDI channel (0-indexed) used by keyboard keys. `0` = ch1 (InControl mode). `8` = ch9 (normal mode). |
| `channel_pads` | int    | `9`                               | MIDI channel (0-indexed) used by pads. Always `9` (ch10) on the LaunchKey Mini MK2. |

---

## `[synth]`

FluidSynth engine settings.

| Key         | Type   | Default                          | Description |
|-------------|--------|----------------------------------|-------------|
| `soundfont` | string | `"soundfonts/GeneralUser_GS.sf2"` | Path to the SoundFont file. Relative paths are resolved from the directory containing `config.toml`. Supports `~` for home directory. |
| `gain`      | float  | `0.5`                            | Master output gain (0.0–1.0). |
| `driver`    | string | `"coreaudio"`                    | Audio backend. `"coreaudio"` on macOS, `"alsa"` or `"pulseaudio"` on Linux, `"dsound"` on Windows. |

---

## Instrument selection

Instruments are selected live on the device — there is no `[track]` section in `config.toml`. On startup the keys default to **Acoustic Grand Piano** (bank 0, program 1) and the pads default to **Standard Kit** (bank 128, program 1).

Use the two round play buttons to change sounds:

### KeySelect (second play button)

Hold KeySelect, press pads 1–10 to type a code, release. The last digit is the GM2 bank; the preceding digits are the patch number (1-indexed).

```
Pads: 1, 0  →  patch 1, bank 0  →  Acoustic Grand Piano
Pads: 4, 0  →  patch 4, bank 0  →  Honky-tonk Piano
Pads: 7, 4  →  patch 7, bank 4  →  GM2 bank 4, patch 7
```

| Pad | Digit |
|-----|-------|
| Pad 1 | 1 |
| Pad 2 | 2 |
| Pad 3 | 3 |
| Pad 4 | 4 |
| Pad 5 | 5 |
| Pad 6 | 6 |
| Pad 7 | 7 |
| Pad 8 | 8 |
| Pad 9 | 9 |
| Pad 10 | 0 |

Only the keys channel is affected. The pads channel is unchanged.

### PadSelect (first play button)

Hold PadSelect, press one pad (1–9) to select a GM percussion kit, release.

| Pad | Program | Kit |
|-----|---------|-----|
| 1 | 1 | Standard Kit |
| 2 | 2 | Room Kit |
| 3 | 3 | Power Kit |
| 4 | 4 | Electronic Kit |
| 5 | 5 | TR-808 Kit |
| 6 | 6 | Jazz Kit |
| 7 | 7 | Brush Kit |
| 8 | 8 | Orchestra Kit |
| 9 | 9 | Sound FX Kit |

Only the pads channel (bank 128) is affected. The keys channel is unchanged.

---

## Environment variables

| Variable | Values | Description |
|----------|--------|-------------|
| `DEBUG`  | `1`    | Print every note_on / note_off event to stdout. |

---

## Example config.toml

**Alternative SoundFont:**
```toml
[synth]
soundfont = "~/soundfonts/FluidR3_GM.sf2"
gain      = 0.6
driver    = "coreaudio"
```
