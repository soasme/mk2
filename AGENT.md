# AGENT.md — Architecture Overview

## Purpose

A real-time software synthesizer for the Novation LaunchKey Mini MK2.
Reads MIDI input from the keyboard, synthesizes audio on the fly, and plays it through the system audio output.
All sound and routing behaviour is controlled by `config.toml`.

## Data Flow

```
LaunchKey Mini MK2 (USB)
        │
        │  MIDI Note On / CC
        ▼
   mido.open_input()          — blocking iterator on main thread
        │
        ▼
     dispatch()               — routes message by mode and MIDI channel
        │
        ├─ CC 108 ch0 value=127  → toggle loop_mode (start/stop SequencerThread)
        │
        ├─ [loop mode] ch_pads  → toggle step on/off, update pad LED via InControl port
        ├─ [loop mode] ch_keys  → set seq.loop_note (no audio)
        │
        ├─ [normal] channel_keys → make_sound(keys_sound, …)
        └─ [normal] channel_pads → make_sound(pads_sound, …)
                │
                ▼
        sound generator        — numpy synthesis, returns float32 buffer
                │
                ▼
          _active list          — thread-safe mixer queue
                │
                ▼
       audio_callback()        — sounddevice real-time thread
                │              sums all active buffers, clips to [-1, 1]
                ▼
        System Audio Out


LaunchKey Mini MK2 InControl port  ←── set_pad_leds() / clear_pad_leds()
        ↑                                        ↑
        └────────────── SequencerThread ─────────┘
                        (sequencer_loop, daemon thread)
                        advances step every 1/16 note @ BPM
```

## File Map

| File               | Role |
|--------------------|------|
| `main.py`          | Entry point — MIDI loop, sound generators, audio mixer |
| `config.toml`      | Runtime configuration — MIDI ports, active track, sound presets |
| `CONFIGURATION.md` | Reference for every config.toml option |
| `AGENT.md`         | This file |

## Concurrency Model

| Thread | Responsibility |
|--------|---------------|
| Main thread | Reads MIDI messages, generates sound buffers on normal note-on, toggles loop mode on CC 108, updates `_active` |
| Sequencer thread | Advances playhead every 1/16 note, triggers sounds for active steps, updates pad LEDs via InControl port |
| sounddevice thread | Runs `audio_callback` per audio block, consumes `_active` |

`_active` and all `SequencerState` fields are protected by `threading.Lock`. `_stop_seq` (`threading.Event`) signals the sequencer thread to exit cleanly.

## Sound Engines

Each engine is a pure function `(note, velocity, cfg) → np.ndarray[float32]`:

| Engine  | Algorithm | Good for |
|---------|-----------|----------|
| `piano` | Additive synthesis — fundamental + 5 harmonics, two-stage exponential decay, velocity-sensitive brightness | Keys, melodic leads |
| `guitar` | Karplus-Strong — random noise in a ring buffer, averaged and damped each cycle | Plucked strings |
| `organ`  | Additive synthesis — sustained harmonics, slow attack | Chords, pads |
| `drums`  | Noise + sine burst, exponential decay | Pad percussion |
| `bells`  | Inharmonic additive synthesis (partials at 1×, 2.76×, 5.40×) | Pad accents |

## Adding a New Sound Engine

1. Write a function `make_myengine(note, velocity, cfg) -> np.ndarray`.
2. Register it in `SOUND_MAKERS` in `main.py`.
3. Add a `[sounds.mypreset]` block in `config.toml` with `type = "myengine"`.
4. Set `track.keys` or `track.pads` to `"mypreset"`.

## MIDI Channel Notes

The LaunchKey Mini MK2 changes which MIDI channel keys use depending on mode:

| Mode          | Keys channel (0-indexed) | Pads channel (0-indexed) |
|---------------|--------------------------|--------------------------|
| Normal        | 8  (ch9)                 | 9  (ch10)                |
| InControl ON  | 0  (ch1)                 | 9  (ch10)                |

Enable InControl by pressing the InControl button on the device.
`config.toml` defaults to InControl mode (`channel_keys = 0`).
