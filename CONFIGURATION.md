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

## `[track]`

Selects which GM instrument each input plays.

| Key            | Type | Default | Description |
|----------------|------|---------|-------------|
| `keys_bank`    | int  | `0`     | SoundFont bank for keys. `0` = GM melodic bank. |
| `keys_program` | int  | `0`     | GM program number (0–127) for keys. `0` = Acoustic Grand Piano. |
| `pads_bank`    | int  | `128`   | SoundFont bank for pads. `128` = GM percussion bank. |
| `pads_program` | int  | `0`     | Drum kit number within the percussion bank. `0` = Standard Kit. |

### Changing the keys instrument

Set `keys_program` to any [GM program number](https://en.wikipedia.org/wiki/General_MIDI#Program_change_events):

```toml
[track]
keys_bank    = 0
keys_program = 40   # 40 = Violin
```

### Changing the drum kit

Set `pads_program` to a GM percussion kit number (bank 128):

```toml
[track]
pads_bank    = 128
pads_program = 25   # 25 = TR-808
```

---

## Examples

**Electric bass + TR-808:**
```toml
[track]
keys_bank    = 0
keys_program = 33   # Electric Bass (finger)
pads_bank    = 128
pads_program = 25   # TR-808
```

**Strings + Jazz kit:**
```toml
[track]
keys_bank    = 0
keys_program = 48   # String Ensemble 1
pads_bank    = 128
pads_program = 32   # Jazz Kit
```

**Alternative SoundFont:**
```toml
[synth]
soundfont = "~/soundfonts/FluidR3_GM.sf2"
gain      = 0.6
driver    = "coreaudio"
```
