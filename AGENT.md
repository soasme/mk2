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
        ├─ EnterChordLearningEvent / ExitChordLearningEvent /
        │  ChordLearningNoteChangedEvent
        ├─ EnterLoopModeEvent / ExitLoopModeEvent /
        │  LoopModeTrackLeftEvent / LoopModeTrackRightEvent /
        │  LoopModeRecordToggleEvent / LoopModePlaybackToggleEvent
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
| `modes/chord_learning.py`   | Chord Learning Mode — interval-set chord detection (pure functions, no I/O) |
| `modes/loop_mode.py`        | Loop Mode track storage and per-track playback loop (pure helpers, no I/O) |
| `modes/__init__.py`         | Package marker |
| `Brewfile`                  | Homebrew dependencies (`brew bundle` installs `fluid-synth`) |
| `CONFIGURATION.md`          | Reference for every config.toml option |
| `README.md`                 | Setup and usage guide |
| `references/mk2.md`         | LaunchKey Mini MK2 MIDI protocol reference |
| `test_main.py`              | Unit tests for `parse_events` and helpers |
| `AGENT.md`                  | This file |

## Concurrency Model

FluidSynth manages its own internal audio thread. `main.py` is single-threaded: it reads MIDI messages from mido in a blocking loop and makes synchronous calls into the FluidSynth C library.

Exceptions:
- `note_challenge.play_notes_async` spawns a short-lived daemon thread to play a note sequence without blocking the MIDI loop
- Chord Learning mode uses a short-lived `threading.Timer` to debounce chord announcements after held-note changes
- Loop Mode uses one daemon thread per playing track so multi-track loops can run without blocking MIDI input

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
| `chord_learning_active` | True when Chord Learning Mode is running |
| `chord_learning_held` | Set of currently held MIDI note numbers |
| `chord_learning_chord_set` | Active chord recognition set name |
| `chord_learning_announce_delay` | Debounce delay before speaking a detected chord |
| `chord_learning_announce_timer` | Pending timer for the next debounced chord announcement |
| `loop_mode_active` | True when Loop Mode is running |
| `loop_mode_current_track` | Selected loop track index (0-based) |
| `loop_mode_recording` | True while the current track is being recorded |
| `loop_mode_record_buffer` | Timestamped note events captured for the current recording pass |
| `loop_mode_playing` | True when loop playback is enabled globally |
| `loop_mode_play_stop_events` | Per-track `threading.Event` objects used to stop playback threads |

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

## Chord Learning Mode

A real-time chord identification tool. While active, holding 2 or more keys simultaneously announces the chord name aloud via TTS (e.g., "C Major", "B flat minor seventh, first inversion", "G perfect fifth").

Entry/reset: hold KeySelect and press the pad sequence configured in `chord_learning.entry_pads` (default `16,2`). Repeating the gesture while already active clears held notes and restarts the mode instead of exiting it.

While active:
- Key notes still play normally through FluidSynth
- Every change to the set of held keys resets a short debounce timer
- If the held notes form a recognized chord, its name is spoken via TTS
- Unrecognized combinations produce no output

Configuration in `config.toml` under `[chord_learning]`: `entry_pads`, `chord_set` (`"minimal"`, `"core_set"`, `"extended"`), `announce_delay` (seconds).

Logic is in `modes/chord_learning.py` (pure functions, no I/O). Orchestration is in `handle_event` in `main.py`.

## Loop Mode

A multi-track loop recorder. While active, the user can record note sequences per track and loop them back.

Entry/exit: hold KeySelect and press the pad sequence configured in `loop_mode.entry_pads` (default `16,3`). Pressing while active exits, stops playback, and leaves the mode. The next entry starts with a clean slate.

### Controls (while in Loop Mode)

| Control | Action |
|---------|--------|
| Track Left (CC 103) | Switch to previous track (wraps) |
| Track Right (CC 102) | Switch to next track (wraps) |
| Scene Up (CC 104) bare tap (no pad pressed) | Toggle recording for the current track |
| Scene Down (CC 105) bare tap (no pad pressed) | Toggle playback of all tracks |
| Play Button 1 (CC 108) | Toggle recording for the current track |
| Play Button 2 (CC 109) | Toggle playback of all tracks |
| KeySelect + digit pads | Change instrument on the keys channel (works normally) |
| PadSelect + digit pad 1-9 | Change percussion kit on the pads channel (works normally) |

### Recording lifecycle

- Press Scene Up (bare tap) to start recording the current track. Notes still play through FluidSynth normally.
- Only `note_on` / `note_off` events on the configured keys and pads channels are recorded.
- Press Scene Up again to stop. If notes were captured, they replace the current track's loop. If nothing was captured, the current track is cleared.
- If global playback is on when recording stops, the saved track auto-restarts playing.
- When recording starts, only the current track's playback pauses. Other playing tracks continue looping.

### Playback

- Press Scene Down (bare tap) to start looping all tracks that have content.
- Press Scene Down again to stop all tracks.
- Each track loops independently at the duration captured during its recording pass.

Configuration in `config.toml` under `[loop_mode]`: `entry_pads`, `n_tracks`.

Logic is in `modes/loop_mode.py` (pure track data + playback loop). Orchestration is in `handle_event` in `main.py`.

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
