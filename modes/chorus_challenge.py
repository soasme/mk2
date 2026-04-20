"""
modes/chorus_challenge.py — Chorus Challenge Mode.

The player is shown a chord (e.g. "C Major Chord is C E G") and must press
all the required notes simultaneously.  When the correct pitch-classes are all
held at once, the game plays a success sound and moves on to a random new chord.

Entry: hold KeySelect, press Pad 16 then Pad 2, release KeySelect (default).
Exit:  same sequence again (toggle).
"""
import random
import threading
import time

# Each entry: (display_name, tts_announcement, frozenset_of_pitch_classes)
# Pitch classes: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11
CHORDS = [
    ('C Major',  'C Major Chord is C, E, G',   frozenset([0, 4, 7])),
    ('F Major',  'F Major Chord is F, A, C',   frozenset([5, 9, 0])),
    ('G Major',  'G Major Chord is G, B, D',   frozenset([7, 11, 2])),
    ('D Major',  'D Major Chord is D, F sharp, A', frozenset([2, 6, 9])),
    ('A Major',  'A Major Chord is A, C sharp, E', frozenset([9, 1, 4])),
    ('E Major',  'E Major Chord is E, G sharp, B', frozenset([4, 8, 11])),
    ('A Minor',  'A Minor Chord is A, C, E',   frozenset([9, 0, 4])),
    ('E Minor',  'E Minor Chord is E, G, B',   frozenset([4, 7, 11])),
    ('D Minor',  'D Minor Chord is D, F, A',   frozenset([2, 5, 9])),
    ('B Minor',  'B Minor Chord is B, D, F sharp', frozenset([11, 2, 6])),
]


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
    # Map pitch classes to MIDI notes in the given octave
    base = (root_octave + 1) * 12
    notes = sorted((base + pc) for pc in pitch_classes)

    def _play():
        for note in notes:
            fs.noteon(channel, note, velocity)
        time.sleep(duration)
        for note in notes:
            fs.noteoff(channel, note)

    threading.Thread(target=_play, daemon=True).start()
