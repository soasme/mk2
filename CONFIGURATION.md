# CONFIGURATION.md — config.toml Reference

## `[midi]`

MIDI device and channel routing.

| Key            | Type   | Default                           | Description |
|----------------|--------|-----------------------------------|-------------|
| `port`         | string | `"Launchkey Mini LK Mini MIDI"`   | Exact MIDI input port name. Run `python3 -c "import mido; print(mido.get_input_names())"` to list available ports. |
| `channel_keys`        | int  | `0`     | MIDI channel (0-indexed) used by keyboard keys. `0` = ch1 (InControl mode). `8` = ch9 (normal mode). |
| `channel_pads`        | int  | `9`     | MIDI channel (0-indexed) used by pads. Always `9` (ch10) on the LaunchKey Mini MK2. |
| `enable_key_velocity` | bool | `false` | When `false`, all key note-on events use a fixed velocity of 100, ignoring how hard you press. Set to `true` to use the actual strike velocity from the hardware. Loop Mode records the rendered note velocity, so loop playback follows this setting too. |

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

Use the **Scene Up** and **Scene Down** buttons to change sounds:

### KeySelect (Scene Down button)

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

### PadSelect (Scene Up button)

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

## `[note_challenge]`

Settings for Note Challenge ear-training mode.

| Key          | Type   | Default  | Description |
|--------------|--------|----------|-------------|
| `n_notes`    | int    | `4`      | Number of notes in each challenge sequence. |
| `note_min`   | int    | `48`     | Lowest MIDI note the game will pick (48 = C3). |
| `note_max`   | int    | `72`     | Highest MIDI note the game will pick (72 = C5). |
| `entry_pads`  | string | `"16,1"` | Comma-separated pad numbers to press while holding KeySelect to toggle the mode. Pad 16 acts as the bank separator; pads 1–10 contribute digits. Example: `"16,2"` requires Pad 16 then Pad 2. |
| `bingo_sound` | string | *(none)* | Path to an audio file (MP3, WAV, etc.) played on a correct match. Relative paths resolve from the directory containing `config.toml`. When omitted, falls back to TTS "Bingo" via `SAY_INSTRUMENT`. |

---

## `[chord_learning]`

Settings for Chord Learning mode.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `entry_pads` | string | `"16,2"` | Comma-separated pad numbers to press while holding KeySelect to enter or reset the mode. Pad 16 acts as the bank separator; pads 1–10 contribute digits. Example: `"16,3"` requires Pad 16 then Pad 3. |
| `chord_set` | string | `"extended"` | Recognition set to use. Supported values: `"minimal"`, `"core_set"`, `"extended"`. |
| `announce_delay` | float | `0.2` | Seconds to wait after the last held-note change before announcing the detected chord. Increase this if you want the app to wait for your full voicing before speaking. |

---

## `[loop_mode]`

Settings for Loop Mode.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `entry_pads` | string | `"16,3"` | Comma-separated pad numbers to press while holding KeySelect to enter or exit Loop Mode. Pad 16 acts as the bank separator; pads 1–10 contribute digits. Example: `"16,1"` would require Pad 16 then Pad 1. |
| `n_tracks` | int | `4` | Number of independent loop tracks kept in memory for each Loop Mode session. |

Loop Mode behavior notes:
- The first non-empty track saved in a session becomes the reference loop length.
- Later tracks are auto-fit to the nearest whole-number multiple of that reference when they are close enough, so small timing drift is corrected automatically.
- Exiting Loop Mode or clearing all tracks resets the reference length.

Control notes:
- Record/playback use **Play Button 1 / Play Button 2** on the tested MK2 units (`108/109`).
- The app accepts both common track-button mappings: `103/102` and `106/107` (`106 = left`, `107 = right` on the tested unit).

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

**Loop Mode with 6 tracks:**
```toml
[loop_mode]
entry_pads = "16,3"
n_tracks = 6
```
