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
   parse_events(msg, state)   — MIDI → app events (pure transform + state mutation)
        │
        ├─ NoteOnEvent / NoteOffEvent
        ├─ PitchBendEvent / CCEvent
        ├─ ProgramChangeEvent / PercussionChangeEvent
        └─ NoteChallengePlayEvent / NoteChallengeNewEvent /
           NoteChallengeHintEvent / NoteChallengeBingoEvent
                │
                ▼
   handle_event(event, ...)   — drives FluidSynth and side effects (TTS, audio)
                │
                ▼
         FluidSynth            — renders SoundFont samples
                │              runs its own internal audio thread
                ▼
        System Audio Out
```

## File Map

| File                        | Role |
|-----------------------------|------|
| `main.py`                   | Entry point — config load, FluidSynth init, MIDI event loop |
| `config.toml`               | Runtime configuration — MIDI ports, SoundFont path, GM bank/program, Note Challenge settings |
| `modes/note_challenge.py`   | Note Challenge ear-training game logic (pure helpers, no I/O) |
| `modes/__init__.py`         | Package marker |
| `Brewfile`                  | Homebrew dependencies (`brew bundle` installs `fluid-synth`) |
| `CONFIGURATION.md`          | Reference for every config.toml option |
| `README.md`                 | Setup and usage guide |
| `references/mk2.md`         | LaunchKey Mini MK2 MIDI protocol reference |
| `test_main.py`              | Unit tests for `parse_events` and helpers |
| `AGENT.md`                  | This file |

## Concurrency Model

FluidSynth manages its own internal audio thread. `main.py` is single-threaded: it reads MIDI messages from mido in a blocking loop and makes synchronous calls into the FluidSynth C library. No Python threading primitives are needed in the main loop.

Exception: `note_challenge.play_notes_async` spawns a short-lived daemon thread to play a note sequence without blocking the MIDI loop.

## Input State Machine

`parse_events` converts raw MIDI messages into typed app events while mutating a dict (`state`) that tracks mode state. Key fields:

| Field | Purpose |
|---|---|
| `current_keys_channel` | Active output channel for key notes (modified by ChannelSelect) |
| `last_keys_channel` | Most recent channel key notes were actually sent on (used to latch KeySelect target) |
| `key_select_active` | True while Scene Down (CC 105) is held |
| `key_select_channel` | Channel latched at KeySelect press — patch change target |
| `key_select_digits` / `key_select_bank_digits` | Digit accumulator for KeySelect patch/bank entry |
| `pad_select_active` | True while Scene Up (CC 104) is held |
| `note_challenge_active` | True when Note Challenge mode is running |
| `note_challenge_target` | Random note sequence the player must reproduce |
| `note_challenge_history` | Recent key notes played (bounded ring buffer) |

## Scene Button Controls

| Button | CC | Function |
|--------|----|----------|
| Scene Up (upper round pad) | 104 | **PadSelect** — hold + press pad 1-9 to set percussion kit (bank 128, program 0-8) |
| Scene Down (lower round pad) | 105 | **KeySelect** — hold + press digit pads to enter patch number; pad 16 separates patch from bank |

### KeySelect Encoding

Pads 1-9 enter digits 1-9; pad 10 enters 0; pad 16 is the bank separator.

Examples:
- `1, 2, 8` → patch 128, bank 0
- `1, 2, 8, [pad16], 3` → patch 128, bank 3

On release, `ProgramChangeEvent` fires and FluidSynth switches the instrument.

## Note Challenge Mode

An ear-training mini-game. Enter/exit by holding KeySelect and pressing the pad sequence configured in `note_challenge.entry_pads` (default `16,1`).

While active:
- Pad 1 — replay the target sequence
- Pad 2 — generate a new target sequence
- Pad 3 — speak note names aloud via TTS
- Key presses are tracked; when the last N notes match the target sequence, a bingo sound plays and a new sequence is generated

Configuration in `config.toml` under `[note_challenge]`: `n_notes`, `note_min`, `note_max`, `entry_pads`, `bingo_sound`.

Logic is in `modes/note_challenge.py` (pure functions, no I/O). Orchestration is in `handle_event` in `main.py`.

## SoundFont and GM Programs

FluidSynth renders audio by looking up samples from a loaded SoundFont (`.sf2`) file. Each channel must be assigned to a bank and program number before note events are sent:

- **Keys channel** (default: ch1): bank 0, program 0–127 (GM melodic instruments)
- **Pads channel** (default: ch10): bank 128, program 0–N (GM percussion kits)

These are set at startup via `program_select_with_fallback`, which falls back to bank 0 program 0 if the requested program isn't in the SoundFont.

## MIDI Channel Notes

The LaunchKey Mini MK2 changes which MIDI channel keys use depending on mode:

| Mode          | Keys channel (0-indexed) | Pads channel (0-indexed) |
|---------------|--------------------------|--------------------------|
| Normal        | 8  (ch9)                 | 9  (ch10)                |
| InControl ON  | 0  (ch1)                 | 9  (ch10)                |

Enable InControl by pressing the InControl button on the device.
`config.toml` defaults to InControl mode (`channel_keys = 0`).

## Key Velocity

Set `enable_key_velocity = true` in `[midi]` to pass through the hardware velocity. When `false` (default), all key note-on events fire at velocity 100.

## Environment Variables

| Variable | Effect |
|---|---|
| `DEBUG=1` | Print detailed parse and Note Challenge debug output |
| `SAY_INSTRUMENT=1` | Speak instrument name aloud via TTS after each KeySelect/PadSelect change |
