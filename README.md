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

Download a SoundFont into `soundfonts/`:

| SoundFont | Size | GM level | Download |
|-----------|------|----------|----------|
| **Fluid R3 GM** | ~140 MB | GM2 | `curl -L "https://github.com/musescore/MuseScore/raw/master/share/sound/FluidR3Mono_GM.sf3" -o soundfonts/FluidR3_GM.sf3` |
| **GeneralUser GS** | ~30 MB | GM1 | `curl -L "https://github.com/ROCKNIX/generaluser-gs/raw/main/GeneralUser%20GS%20v1.471.sf2" -o soundfonts/GeneralUser_GS.sf2` |
| **MuseScore General** | ~200 MB | GM1 | `curl -L "https://musical-artifacts.com/artifacts/3001/MS_Basic.sf2" -o soundfonts/MS_Basic.sf2` |
| **OmegaGMGS2 GM** | ~119MB | GM2 | Check <https://musescore.org/en/node/109371> |

GM1 fonts work fine — pad sequences must end with **Pad 10** (bank 0). GM2 fonts additionally support alternate banks (end with Pad 1–9).

If you use a different file, update `config.toml` to point at it:

```toml
[synth]
soundfont = "soundfonts/FluidR3_GM.sf3"
```

## Usage

Connect your LaunchKey Mini MK2 via USB, then:

```bash
uv run python main.py
```

Press the **InControl** button on the device to activate InControl mode (required for the default MIDI channel mapping). Keys start on Acoustic Grand Piano; pads start on Standard Kit.

Quit with `Ctrl-C`.

### Debug mode

Set `DEBUG=1` to print every note event as it arrives:

```bash
DEBUG=1 uv run python main.py
```

### Finding your MIDI port name

If the device name differs on your system, list available ports:

```bash
uv run python -c "import mido; print(mido.get_input_names())"
```

Copy the exact port name into `config.toml → midi.port`.

## Changing sounds live

Instruments are selected on the device using the two round play buttons, without editing any files.

### KeySelect — change the keys instrument

Hold the **second play button** (KeySelect), press pads to enter the patch number, then release:

- Pads 1–10 enter digits **1 2 3 4 5 6 7 8 9 0**. The digits directly spell the patch number (1-indexed). Bank defaults to 0.
- To select a non-zero bank, press **Pad 16** as a separator, then enter the bank number.
- Example: `1, 2, 8` → patch 128, bank 0 → **Gunshot**
- Example: `1, 2, 8, 16, 3` → patch 128, bank 3 → **Explosion**
- Example: `7, 4` → patch 74, bank 0 → **Flute**

| Pad | Digit / Role |
|-----|-------------|
| Pad 1 | 1 |
| Pad 2 | 2 |
| … | … |
| Pad 9 | 9 |
| Pad 10 | 0 |
| Pad 16 | bank separator |

GM1 SoundFonts only have bank 0 — just omit Pad 16 and you're done.

The terminal prints the selected instrument on release:
```
Program: ch1 bank=0 program=128 name=Gunshot
```

<details>
<summary>Full GM2 instrument table (Pad Sequence → Patch, Bank, Name)</summary>

Pad sequence uses pad numbers 1–9, **10** (digit 0), and **16** (bank separator). Each press is separated by →.

**Piano**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 1 | 1 | 0 | Acoustic Grand Piano |
| 1 → 16 → 1 | 1 | 1 | Wide Acoustic Grand Piano |
| 1 → 16 → 2 | 1 | 2 | Dark Acoustic Grand Piano |
| 2 | 2 | 0 | Bright Acoustic Piano |
| 2 → 16 → 1 | 2 | 1 | Wide Bright Acoustic Piano |
| 3 | 3 | 0 | Electric Grand Piano |
| 3 → 16 → 1 | 3 | 1 | Wide Electric Grand Piano |
| 4 | 4 | 0 | Honky-Tonk Piano |
| 4 → 16 → 1 | 4 | 1 | Wide Honky-Tonk Piano |
| 5 | 5 | 0 | Rhodes Electric Piano |
| 5 → 16 → 1 | 5 | 1 | Detuned Electric Piano 1 |
| 5 → 16 → 2 | 5 | 2 | Variation Electric Piano 1 |
| 5 → 16 → 3 | 5 | 3 | 60's Electric Piano |
| 6 | 6 | 0 | Chorused Electric Piano |
| 6 → 16 → 1 | 6 | 1 | Detuned Electric Piano 2 |
| 6 → 16 → 2 | 6 | 2 | Variation Electric Piano 2 |
| 6 → 16 → 3 | 6 | 3 | Electric Piano Legend |
| 6 → 16 → 4 | 6 | 4 | Phaser Electric Piano |
| 7 | 7 | 0 | Harpsichord |
| 7 → 16 → 1 | 7 | 1 | Coupled Harpsichord |
| 7 → 16 → 2 | 7 | 2 | Wide Harpsichord |
| 7 → 16 → 3 | 7 | 3 | Open Harpsichord |
| 8 | 8 | 0 | Clavinet |
| 8 → 16 → 1 | 8 | 1 | Pulsed Clavinet |

**Chromatic Percussion**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 9 | 9 | 0 | Celesta |
| 1 → 10 | 10 | 0 | Glockenspiel |
| 1 → 1 | 11 | 0 | Music Box |
| 1 → 2 | 12 | 0 | Vibraphone |
| 1 → 2 → 16 → 1 | 12 | 1 | Wet Vibraphone |
| 1 → 3 | 13 | 0 | Marimba |
| 1 → 3 → 16 → 1 | 13 | 1 | Wide Marimba |
| 1 → 4 | 14 | 0 | Xylophone |
| 1 → 5 | 15 | 0 | Tubular Bells |
| 1 → 5 → 16 → 1 | 15 | 1 | Church Bells |
| 1 → 5 → 16 → 2 | 15 | 2 | Carillon Bells |
| 1 → 6 | 16 | 0 | Dulcimer/Santur |

**Organ**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 1 → 7 | 17 | 0 | Drawbar Organ 1 |
| 1 → 7 → 16 → 1 | 17 | 1 | Detuned Drawbar Organ |
| 1 → 7 → 16 → 2 | 17 | 2 | 60's Drawbar Organ |
| 1 → 7 → 16 → 3 | 17 | 3 | Drawbar Organ 2 |
| 1 → 8 | 18 | 0 | Percussive B3 Organ 1 |
| 1 → 8 → 16 → 1 | 18 | 1 | Detuned Percussive B3 Organ |
| 1 → 8 → 16 → 2 | 18 | 2 | Percussive B3 Organ 2 |
| 1 → 9 | 19 | 0 | Rock Organ |
| 2 → 10 | 20 | 0 | Church Organ 1 |
| 2 → 10 → 16 → 1 | 20 | 1 | Church Organ 2 |
| 2 → 10 → 16 → 2 | 20 | 2 | Church Organ 3 |
| 2 → 1 | 21 | 0 | Reeds Organ |
| 2 → 1 → 16 → 1 | 21 | 1 | Puffs Organ |
| 2 → 2 | 22 | 0 | French Accordion |
| 2 → 2 → 16 → 1 | 22 | 1 | Italian Accordion |
| 2 → 3 | 23 | 0 | Harmonica |
| 2 → 4 | 24 | 0 | Tango Accordion |

**Guitar**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 2 → 5 | 25 | 0 | Nylon-Strings Guitar 1 |
| 2 → 5 → 16 → 1 | 25 | 1 | Ukulele |
| 2 → 5 → 16 → 2 | 25 | 2 | Opened Nylon-Strings Guitar |
| 2 → 5 → 16 → 3 | 25 | 3 | Nylon-Strings Guitar 2 |
| 2 → 6 | 26 | 0 | Steel-Strings Guitar |
| 2 → 6 → 16 → 1 | 26 | 1 | 12-Strings Steel Guitar |
| 2 → 6 → 16 → 2 | 26 | 2 | Mandolin |
| 2 → 6 → 16 → 3 | 26 | 3 | Steel-Strings Guitar + Body Tapped Sounds |
| 2 → 7 | 27 | 0 | Jazz Guitar |
| 2 → 7 → 16 → 1 | 27 | 1 | Hawaiian Guitar |
| 2 → 8 | 28 | 0 | Clean Electric Guitar |
| 2 → 8 → 16 → 1 | 28 | 1 | Chorus Guitar |
| 2 → 8 → 16 → 2 | 28 | 2 | Mid Tone Guitar |
| 2 → 9 | 29 | 0 | Muted Electric Guitar |
| 2 → 9 → 16 → 1 | 29 | 1 | Funky Guitar 1 |
| 2 → 9 → 16 → 2 | 29 | 2 | Funky Guitar 2 |
| 2 → 9 → 16 → 3 | 29 | 3 | Jazz Man |
| 3 → 10 | 30 | 0 | Overdriven Guitar |
| 3 → 10 → 16 → 1 | 30 | 1 | Guitar Pinch |
| 3 → 1 | 31 | 0 | Distortion Guitar |
| 3 → 1 → 16 → 1 | 31 | 1 | Feedback Guitar |
| 3 → 1 → 16 → 2 | 31 | 2 | Distortion Rhythm Guitar |
| 3 → 2 | 32 | 0 | Guitar Harmonics |
| 3 → 2 → 16 → 1 | 32 | 1 | Guitar Feedback |

**Bass**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 3 → 3 | 33 | 0 | Acoustic Bass |
| 3 → 4 | 34 | 0 | Fingered Bass |
| 3 → 4 → 16 → 1 | 34 | 1 | Fingered Slap Bass |
| 3 → 5 | 35 | 0 | Picked Bass |
| 3 → 6 | 36 | 0 | Fretless Bass |
| 3 → 7 | 37 | 0 | Slap Bass 1 |
| 3 → 8 | 38 | 0 | Slap Bass 2 |
| 3 → 9 | 39 | 0 | Synth Bass 1 |
| 3 → 9 → 16 → 1 | 39 | 1 | Synth Bass 101 |
| 3 → 9 → 16 → 2 | 39 | 2 | Synth Bass 3 |
| 3 → 9 → 16 → 3 | 39 | 3 | Clavi Bass |
| 3 → 9 → 16 → 4 | 39 | 4 | Hammered Bass |
| 4 → 10 | 40 | 0 | Synth Bass 2 |
| 4 → 10 → 16 → 1 | 40 | 1 | Synth Bass 4 |
| 4 → 10 → 16 → 2 | 40 | 2 | Rubber Bass |
| 4 → 10 → 16 → 3 | 40 | 3 | Attack Pulsed |

**Orchestra Solo**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 4 → 1 | 41 | 0 | Violin |
| 4 → 1 → 16 → 1 | 41 | 1 | Slow Violin |
| 4 → 2 | 42 | 0 | Viola |
| 4 → 3 | 43 | 0 | Cello |
| 4 → 4 | 44 | 0 | Contrabass |
| 4 → 5 | 45 | 0 | Tremolo Strings |
| 4 → 6 | 46 | 0 | Pizzicato Strings |
| 4 → 7 | 47 | 0 | Harp |
| 4 → 7 → 16 → 1 | 47 | 1 | Yangqin |
| 4 → 8 | 48 | 0 | Timpani |

**Orchestra Ensemble**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 4 → 9 | 49 | 0 | Strings Ensemble |
| 4 → 9 → 16 → 1 | 49 | 1 | Orchestral Strings |
| 4 → 9 → 16 → 2 | 49 | 2 | 60's Strings |
| 5 → 10 | 50 | 0 | Slow Strings Ensemble |
| 5 → 1 | 51 | 0 | Synth Strings 1 |
| 5 → 1 → 16 → 1 | 51 | 1 | Synth Strings 3 |
| 5 → 2 | 52 | 0 | Synth Strings 2 |
| 5 → 3 | 53 | 0 | Choir Aahs 1 |
| 5 → 3 → 16 → 1 | 53 | 1 | Choir Aahs 2 |
| 5 → 4 | 54 | 0 | Voice Oohs |
| 5 → 4 → 16 → 1 | 54 | 1 | Humming |
| 5 → 5 | 55 | 0 | Synth Voice |
| 5 → 5 → 16 → 1 | 55 | 1 | Analog Voice |
| 5 → 6 | 56 | 0 | Orchestra Hit |
| 5 → 6 → 16 → 1 | 56 | 1 | Bass Hit |
| 5 → 6 → 16 → 2 | 56 | 2 | 6th Hit |
| 5 → 6 → 16 → 3 | 56 | 3 | Euro Hit |

**Brass**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 5 → 7 | 57 | 0 | Trumpet |
| 5 → 7 → 16 → 1 | 57 | 1 | Dark Trumpet Soft |
| 5 → 8 | 58 | 0 | Trombone 1 |
| 5 → 8 → 16 → 1 | 58 | 1 | Trombone 2 |
| 5 → 8 → 16 → 2 | 58 | 2 | Bright Trombone |
| 5 → 9 | 59 | 0 | Tuba |
| 6 → 10 | 60 | 0 | Muted Trumpet 1 |
| 6 → 10 → 16 → 1 | 60 | 1 | Muted Trumpet 2 |
| 6 → 1 | 61 | 0 | French Horns 1 |
| 6 → 1 → 16 → 1 | 61 | 1 | French Horns 2 |
| 6 → 2 | 62 | 0 | Brass Section 1 |
| 6 → 2 → 16 → 1 | 62 | 1 | Brass Section 2 |
| 6 → 3 | 63 | 0 | Synth Brass 1 |
| 6 → 3 → 16 → 1 | 63 | 1 | Synth Brass 3 |
| 6 → 3 → 16 → 2 | 63 | 2 | Analog Brass 1 |
| 6 → 3 → 16 → 3 | 63 | 3 | Jump Brass |
| 6 → 4 | 64 | 0 | Synth Brass 2 |
| 6 → 4 → 16 → 1 | 64 | 1 | Synth Brass 4 |
| 6 → 4 → 16 → 2 | 64 | 2 | Analog Brass 2 |

**Reed**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 6 → 5 | 65 | 0 | Soprano Sax |
| 6 → 6 | 66 | 0 | Alto Sax |
| 6 → 7 | 67 | 0 | Tenor Sax |
| 6 → 8 | 68 | 0 | Baritone Sax |
| 6 → 9 | 69 | 0 | Oboe |
| 7 → 10 | 70 | 0 | English Horn |
| 7 → 1 | 71 | 0 | Bassoon |
| 7 → 2 | 72 | 0 | Clarinet |

**Wind**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 7 → 3 | 73 | 0 | Piccolo |
| 7 → 4 | 74 | 0 | Flute |
| 7 → 5 | 75 | 0 | Recorder |
| 7 → 6 | 76 | 0 | Pan Flute |
| 7 → 7 | 77 | 0 | Bottle Blow |
| 7 → 8 | 78 | 0 | Shakuhachi |
| 7 → 9 | 79 | 0 | Whistle |
| 8 → 10 | 80 | 0 | Ocarina |

**Synth Lead**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 8 → 1 | 81 | 0 | Square Lead |
| 8 → 1 → 16 → 1 | 81 | 1 | Square Wave |
| 8 → 1 → 16 → 2 | 81 | 2 | Sine Wave |
| 8 → 2 | 82 | 0 | Saw Lead |
| 8 → 2 → 16 → 1 | 82 | 1 | Saw Wave |
| 8 → 2 → 16 → 2 | 82 | 2 | Doctor Solo |
| 8 → 2 → 16 → 3 | 82 | 3 | Natural Lead |
| 8 → 2 → 16 → 4 | 82 | 4 | Sequenced Saw |
| 8 → 3 | 83 | 0 | Synth Calliope |
| 8 → 4 | 84 | 0 | Chiffer Lead |
| 8 → 5 | 85 | 0 | Charang |
| 8 → 5 → 16 → 1 | 85 | 1 | Wire Lead |
| 8 → 6 | 86 | 0 | Solo Synth Vox |
| 8 → 7 | 87 | 0 | 5th Saw Wave |
| 8 → 8 | 88 | 0 | Bass & Lead |
| 8 → 8 → 16 → 1 | 88 | 1 | Delayed Lead |

**Synth Pad**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 8 → 9 | 89 | 0 | Fantasia Pad |
| 9 → 10 | 90 | 0 | Warm Pad |
| 9 → 10 → 16 → 1 | 90 | 1 | Sine Pad |
| 9 → 1 | 91 | 0 | Polysynth Pad |
| 9 → 2 | 92 | 0 | Space Voice Pad |
| 9 → 2 → 16 → 1 | 92 | 1 | Itopia |
| 9 → 3 | 93 | 0 | Bowed Glass Pad |
| 9 → 4 | 94 | 0 | Metal Pad |
| 9 → 5 | 95 | 0 | Halo Pad |
| 9 → 6 | 96 | 0 | Sweep Pad |

**Synth Sound FX**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 9 → 7 | 97 | 0 | Ice Rain |
| 9 → 8 | 98 | 0 | Soundtrack |
| 9 → 9 | 99 | 0 | Crystal |
| 9 → 9 → 16 → 1 | 99 | 1 | Synth Mallet |
| 1 → 10 → 10 | 100 | 0 | Atmosphere |
| 1 → 10 → 1 | 101 | 0 | Brightness |
| 1 → 10 → 2 | 102 | 0 | Goblin |
| 1 → 10 → 3 | 103 | 0 | Echo Drops |
| 1 → 10 → 3 → 16 → 1 | 103 | 1 | Echo Bell |
| 1 → 10 → 3 → 16 → 2 | 103 | 2 | Echo Pan |
| 1 → 10 → 4 | 104 | 0 | Star Theme |

**Ethnic**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 1 → 10 → 5 | 105 | 0 | Sitar 1 |
| 1 → 10 → 5 → 16 → 1 | 105 | 1 | Sitar 2 |
| 1 → 10 → 6 | 106 | 0 | Banjo |
| 1 → 10 → 7 | 107 | 0 | Shamisen |
| 1 → 10 → 8 | 108 | 0 | Koto |
| 1 → 10 → 8 → 16 → 1 | 108 | 1 | Taisho Koto |
| 1 → 10 → 9 | 109 | 0 | Kalimba |
| 1 → 1 → 10 | 110 | 0 | Bagpipe |
| 1 → 1 → 1 | 111 | 0 | Fiddle |
| 1 → 1 → 2 | 112 | 0 | Shanai |

**Percussive**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 1 → 1 → 3 | 113 | 0 | Tinkle Bells |
| 1 → 1 → 4 | 114 | 0 | Agogô |
| 1 → 1 → 5 | 115 | 0 | Steel Drums |
| 1 → 1 → 6 | 116 | 0 | Woodblock |
| 1 → 1 → 6 → 16 → 1 | 116 | 1 | Castanets |
| 1 → 1 → 7 | 117 | 0 | Taiko Drums |
| 1 → 1 → 7 → 16 → 1 | 117 | 1 | Concert Bass Drums |
| 1 → 1 → 8 | 118 | 0 | Melodic Tom 1 |
| 1 → 1 → 8 → 16 → 1 | 118 | 1 | Melodic Tom 2 |
| 1 → 1 → 9 | 119 | 0 | Synth Drums |
| 1 → 1 → 9 → 16 → 1 | 119 | 1 | 808 Toms |
| 1 → 1 → 9 → 16 → 2 | 119 | 2 | Electric Percussion |
| 1 → 2 → 10 | 120 | 0 | Reversed Cymbals |

**Sound Effect**

| Pad Sequence | Patch | Bank | Instrument |
|---|---|---|---|
| 1 → 2 → 1 | 121 | 0 | Guitar Fret Noise |
| 1 → 2 → 1 → 16 → 1 | 121 | 1 | Guitar Cut Noise |
| 1 → 2 → 1 → 16 → 2 | 121 | 2 | String Slap |
| 1 → 2 → 2 | 122 | 0 | Breath Noise |
| 1 → 2 → 2 → 16 → 1 | 122 | 1 | Flute Key Click |
| 1 → 2 → 3 | 123 | 0 | Seashore |
| 1 → 2 → 3 → 16 → 1 | 123 | 1 | Rain |
| 1 → 2 → 3 → 16 → 2 | 123 | 2 | Thunder |
| 1 → 2 → 3 → 16 → 3 | 123 | 3 | Wind |
| 1 → 2 → 3 → 16 → 4 | 123 | 4 | Stream |
| 1 → 2 → 3 → 16 → 5 | 123 | 5 | Bubble |
| 1 → 2 → 4 | 124 | 0 | Bird |
| 1 → 2 → 4 → 16 → 1 | 124 | 1 | Dog |
| 1 → 2 → 4 → 16 → 2 | 124 | 2 | Horse Gallop |
| 1 → 2 → 4 → 16 → 3 | 124 | 3 | Bird 2 |
| 1 → 2 → 5 | 125 | 0 | Telephone 1 |
| 1 → 2 → 5 → 16 → 1 | 125 | 1 | Telephone 2 |
| 1 → 2 → 5 → 16 → 2 | 125 | 2 | Door Creaking |
| 1 → 2 → 5 → 16 → 3 | 125 | 3 | Door Closing |
| 1 → 2 → 5 → 16 → 4 | 125 | 4 | Scratch |
| 1 → 2 → 5 → 16 → 5 | 125 | 5 | Wind Chimes |
| 1 → 2 → 6 | 126 | 0 | Helicopter |
| 1 → 2 → 6 → 16 → 1 | 126 | 1 | Car Engine |
| 1 → 2 → 6 → 16 → 2 | 126 | 2 | Car Stop |
| 1 → 2 → 6 → 16 → 3 | 126 | 3 | Car Pass |
| 1 → 2 → 6 → 16 → 4 | 126 | 4 | Car Crash |
| 1 → 2 → 6 → 16 → 5 | 126 | 5 | Siren |
| 1 → 2 → 6 → 16 → 6 | 126 | 6 | Train |
| 1 → 2 → 6 → 16 → 7 | 126 | 7 | Jet Plane |
| 1 → 2 → 6 → 16 → 8 | 126 | 8 | Starship |
| 1 → 2 → 6 → 16 → 9 | 126 | 9 | Burst Noise |
| 1 → 2 → 7 | 127 | 0 | Applause |
| 1 → 2 → 7 → 16 → 1 | 127 | 1 | Laughter |
| 1 → 2 → 7 → 16 → 2 | 127 | 2 | Screaming |
| 1 → 2 → 7 → 16 → 3 | 127 | 3 | Punch |
| 1 → 2 → 7 → 16 → 4 | 127 | 4 | Heartbeat |
| 1 → 2 → 7 → 16 → 5 | 127 | 5 | Footsteps |
| 1 → 2 → 8 | 128 | 0 | Gunshot |
| 1 → 2 → 8 → 16 → 1 | 128 | 1 | Machine Gun |
| 1 → 2 → 8 → 16 → 2 | 128 | 2 | Laser Gun |
| 1 → 2 → 8 → 16 → 3 | 128 | 3 | Explosion |

</details>

### PadSelect — change the drum kit

Hold the **first play button** (PadSelect), press one pad (1–9) to select a GM percussion kit, then release:

| Pad | Kit |
|-----|-----|
| 1 | Standard Kit |
| 2 | Room Kit |
| 3 | Power Kit |
| 4 | Electronic Kit |
| 5 | TR-808 Kit |
| 6 | Jazz Kit |
| 7 | Brush Kit |
| 8 | Orchestra Kit |
| 9 | Sound FX Kit |

The terminal prints the selected kit on release:
```
Percussion: program=1 name=Standard Kit
```

## Configuration reference

See [CONFIGURATION.md](CONFIGURATION.md) for all `config.toml` options.
