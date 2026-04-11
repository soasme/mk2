# mk2 — LaunchKey Mini MK2 Synthesizer

A real-time synthesizer for the Novation LaunchKey Mini MK2. Plays GM instruments through the keyboard keys and GM percussion through the pads, powered by FluidSynth and a SoundFont file.

## Prerequisites

- macOS (or Linux — see [Audio driver](#audio-driver) below)
- [Homebrew](https://brew.sh)
- Python 3.14+, managed with [uv](https://docs.astral.sh/uv/)

## Setup

**1. Install the native FluidSynth library:**

```bash
brew bundle
```

**2. Install Python dependencies:**

```bash
uv sync
```

**3. Download a SoundFont:**

```bash
mkdir -p soundfonts
```

Pick one of the free GM-compatible SoundFonts below and download it into `soundfonts/`:

| SoundFont | Size | Character | Download |
|-----------|------|-----------|----------|
| **GeneralUser GS** *(default)* | ~30 MB | Balanced, clean GM coverage | `curl -L "https://github.com/ROCKNIX/generaluser-gs/raw/main/GeneralUser%20GS%20v1.471.sf2" -o soundfonts/GeneralUser_GS.sf2` |
| **Fluid R3 GM** | ~140 MB | Richer, more expressive | `curl -L "https://github.com/musescore/MuseScore/raw/master/share/sound/FluidR3Mono_GM.sf3" -o soundfonts/FluidR3_GM.sf3` |
| **MuseScore General** | ~200 MB | High quality, orchestral | Download from [musescore.org/download/MuseScore_General.sf3](https://musescore.org/download/MuseScore_General.sf3) |

**Example — GeneralUser GS (recommended for getting started):**

```bash
curl -L "https://github.com/ROCKNIX/generaluser-gs/raw/main/GeneralUser%20GS%20v1.471.sf2" \
     -o soundfonts/GeneralUser_GS.sf2
```

If you download a different file, update `config.toml` to point at it:

```toml
[synth]
soundfont = "soundfonts/FluidR3_GM.sf3"
```

## Usage

Connect your LaunchKey Mini MK2 via USB, then:

```bash
uv run python main.py
```

Press the **InControl** button on the device to activate InControl mode (required for the default MIDI channel mapping). Keys play the configured GM instrument; pads play GM percussion.

Quit with `Ctrl-C`.

### Finding your MIDI port name

If the device name differs on your system, list available ports:

```bash
uv run python -c "import mido; print(mido.get_input_names())"
```

Copy the exact port name into `config.toml → midi.port`.

## Swapping sounds

### Keys instrument

Edit `config.toml` and change `keys_program` to any [GM program number](https://en.wikipedia.org/wiki/General_MIDI#Program_change_events) (0–127):

```toml
[track]
keys_bank    = 0
keys_program = 25   # 25 = Acoustic Guitar (Steel)
```

Common programs:

| Program | Instrument |
|---------|------------|
| 0 | Acoustic Grand Piano |
| 24 | Nylon Guitar |
| 25 | Steel Guitar |
| 33 | Electric Bass (finger) |
| 40 | Violin |
| 48 | String Ensemble 1 |
| 73 | Flute |

### Pads drum kit

Change `pads_program` to select a different GM drum kit (bank 128):

```toml
[track]
pads_bank    = 128
pads_program = 0    # 0 = Standard Kit
```

Common drum kits (bank 128):

| Program | Kit |
|---------|-----|
| 0 | Standard |
| 8 | Room |
| 16 | Power |
| 24 | Electronic |
| 25 | TR-808 |
| 32 | Jazz |
| 40 | Brush |

## Configuration reference

See [CONFIGURATION.md](CONFIGURATION.md) for all `config.toml` options.
