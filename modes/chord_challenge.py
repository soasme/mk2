"""
modes/chord_challenge.py — Chord Challenge Mode.

The player is shown a chord (e.g. "C Major Chord is C E G") and must press
all the required notes simultaneously.  When the correct pitch-classes are all
held at once, the game plays a success sound and moves on to a random new chord.

Entry: hold KeySelect, press Pad 16 then Pad 2, release KeySelect (default).
Exit:  same sequence again (toggle).
"""
import random
import threading
import time

# Chromatic note names (display and TTS-friendly)
# A-G letters are spoken via pre-recorded WAVs by speak(), so no trailing-dot hack needed.
_NOTE_NAMES = ['C', 'C sharp', 'D', 'D sharp', 'E', 'F', 'F sharp', 'G', 'G sharp', 'A', 'A sharp', 'B']
_NOTE_DISPLAY = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Chord type definitions: (quality_name, intervals_from_root)
# intervals_from_root: semitones above root for each chord tone
_CHORD_TYPES = [
    ('Major',      [0, 4, 7]),   # root, major 3rd, perfect 5th
    ('Minor',      [0, 3, 7]),   # root, minor 3rd, perfect 5th
    ('Augmented',  [0, 4, 8]),   # root, major 3rd, augmented 5th
    ('Diminished', [0, 3, 6]),   # root, minor 3rd, diminished 5th
]


def _build_chords():
    chords = []
    for root in range(12):
        root_name = _NOTE_NAMES[root]
        root_display = _NOTE_DISPLAY[root]
        for quality, intervals in _CHORD_TYPES:
            pcs = frozenset((root + i) % 12 for i in intervals)
            note_names = [_NOTE_NAMES[(root + i) % 12] for i in intervals]
            display = f'{root_display} {quality}'
            chord_tts = f'{root_name} {quality}'
            chords.append((display, chord_tts, note_names, pcs))
    return chords


CHORDS = _build_chords()


def random_chord(exclude=None):
    """Return a random (display_name, tts_text, pitch_classes) tuple, optionally excluding one."""
    choices = [c for c in CHORDS if c[0] != exclude] if exclude and len(CHORDS) > 1 else CHORDS
    return random.choice(choices)


def check_chord(held_notes: frozenset, target_pcs: frozenset) -> bool:
    """Return True if the pitch classes of held_notes exactly match target_pcs."""
    held_pcs = frozenset(n % 12 for n in held_notes)
    return held_pcs == target_pcs


def play_chord_async(pitch_classes: frozenset, channel: int, fs,
                     root_octave: int = 4,
                     velocity: int = 100,
                     duration: float = 0.8) -> None:
    """Play all notes of the chord simultaneously in a background thread."""
    base = (root_octave + 1) * 12
    notes = sorted((base + pc) for pc in pitch_classes)

    def _play():
        for note in notes:
            fs.noteon(channel, note, velocity)
        time.sleep(duration)
        for note in notes:
            fs.noteoff(channel, note)

    threading.Thread(target=_play, daemon=True).start()
