# AGENT.md — Architecture Overview

## Purpose

A real-time software synthesizer for the Novation LaunchKey Mini MK2.
Reads MIDI input from the keyboard and forwards it to FluidSynth, which renders audio from a GM SoundFont file and plays it through the system audio output.
All routing and sound configuration is controlled by `config.toml`.

## Data Flow

```
LaunchKey Mini MK2 (USB)
        │
        │  MIDI messages (Note On/Off, CC, Pitchwheel)
        ▼
   mido.open_input()          — blocking iterator on main thread
        │
        ▼
   message dispatch           — routes by message type
        │
        ├─ note_on  → fs.noteon(channel, note, velocity)
        ├─ note_off → fs.noteoff(channel, note)
        ├─ control_change → fs.cc(channel, control, value)
        └─ pitchwheel → fs.pitch_bend(channel, pitch)
                │
                ▼
         FluidSynth            — renders SoundFont samples
                │              runs its own internal audio thread
                ▼
        System Audio Out
```

## File Map

| File               | Role |
|--------------------|------|
| `main.py`          | Entry point — loads config, initialises FluidSynth, MIDI event loop |
| `config.toml`      | Runtime configuration — MIDI ports, SoundFont path, GM bank/program |
| `Brewfile`         | Homebrew dependencies (`brew bundle` installs `fluid-synth`) |
| `CONFIGURATION.md` | Reference for every config.toml option |
| `README.md`        | Setup and usage guide |
| `AGENT.md`         | This file |

## Concurrency Model

FluidSynth manages its own internal audio thread. `main.py` is single-threaded: it reads MIDI messages from mido in a blocking loop and makes synchronous calls into the FluidSynth C library. No Python threading primitives are needed.

## SoundFont and GM Programs

FluidSynth renders audio by looking up samples from a loaded SoundFont (`.sf2`) file. Each channel must be assigned to a bank and program number before note events are sent:

- **Keys channel** (default: ch1): bank 0, program 0–127 (GM melodic instruments)
- **Pads channel** (default: ch10): bank 128, program 0–N (GM percussion kits)

These are set at startup via `fs.program_select(channel, sfid, bank, program)`.

## Swapping Instruments

Change `keys_program` or `pads_program` in `config.toml`. No code changes required. See `CONFIGURATION.md` for the full option reference and `README.md` for a GM program number table.

## MIDI Channel Notes

The LaunchKey Mini MK2 changes which MIDI channel keys use depending on mode:

| Mode          | Keys channel (0-indexed) | Pads channel (0-indexed) |
|---------------|--------------------------|--------------------------|
| Normal        | 8  (ch9)                 | 9  (ch10)                |
| InControl ON  | 0  (ch1)                 | 9  (ch10)                |

Enable InControl by pressing the InControl button on the device.
`config.toml` defaults to InControl mode (`channel_keys = 0`).
