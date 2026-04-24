"""
modes/note_challenge.py — Note Challenge ear-training game.

The player is given a random sequence of N notes to memorise.
Use pads 1-3 to control the game:
  Pad 1  play the target sequence again
  Pad 2  generate a new target sequence
  Pad 3  say the note names aloud as a hint
Play the sequence on the keys in order; once the last N notes played
match the target sequence the game announces "Bingo" and advances to
a new sequence.

Entry: hold KeySelect, press Pad 16 then Pad 1, release KeySelect.
Exit:  same sequence again (toggle).
"""
import random
import threading
import time

# MIDI note → chromatic name (display)
_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# TTS-friendly names (no '#' symbol; A-G letters are spoken via pre-recorded WAVs
# so they don't need the trailing-dot hack used by the macOS `say` fallback).
_NOTE_NAMES_TTS = [
    'C', 'C sharp', 'D', 'D sharp', 'E',
    'F', 'F sharp', 'G', 'G sharp', 'A', 'A sharp', 'B',
]


def midi_note_name(note: int) -> str:
    """Return display name, e.g. 'C4', 'F#3'."""
    octave = (note // 12) - 1
    return f"{_NOTE_NAMES[note % 12]}{octave}"


def midi_note_name_tts(note: int) -> str:
    """Return TTS-friendly name, e.g. 'C 4', 'F sharp 3'."""
    octave = (note // 12) - 1
    return f"{_NOTE_NAMES_TTS[note % 12]} {octave}"


def generate_target(n: int, note_min: int = 48, note_max: int = 72) -> list:
    """Return n random MIDI notes in [note_min, note_max] (inclusive)."""
    return [random.randint(note_min, note_max) for _ in range(n)]


def note_names_display(notes: list) -> str:
    return ', '.join(midi_note_name(n) for n in notes)


def note_names_tts(notes: list) -> str:
    return ', '.join(midi_note_name_tts(n) for n in notes)


def play_notes_async(notes: list, channel: int, fs,
                     velocity: int = 100,
                     note_duration: float = 0.4,
                     gap: float = 0.1) -> None:
    """Play notes sequentially in a background daemon thread."""
    def _play():
        for note in notes:
            fs.noteon(channel, note, velocity)
            time.sleep(note_duration)
            fs.noteoff(channel, note)
            time.sleep(gap)

    threading.Thread(target=_play, daemon=True).start()


def check_match(history: list, target: list) -> bool:
    """Return True if the last len(target) entries in history equal target."""
    n = len(target)
    if len(history) < n:
        return False
    return history[-n:] == target
