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
    # Major triads (root, major 3rd, perfect 5th)
    ('C Major',  'C Major Chord is C, E, G',           frozenset([0, 4, 7])),
    ('F Major',  'F Major Chord is F, A, C',           frozenset([5, 9, 0])),
    ('G Major',  'G Major Chord is G, B, D',           frozenset([7, 11, 2])),
    ('D Major',  'D Major Chord is D, F sharp, A',     frozenset([2, 6, 9])),
    ('A Major',  'A Major Chord is A, C sharp, E',     frozenset([9, 1, 4])),
    ('E Major',  'E Major Chord is E, G sharp, B',     frozenset([4, 8, 11])),
    # Minor triads (root, minor 3rd, perfect 5th)
    ('C Minor',  'C Minor Chord is C, E flat, G',      frozenset([0, 3, 7])),
    ('A Minor',  'A Minor Chord is A, C, E',           frozenset([9, 0, 4])),
    ('E Minor',  'E Minor Chord is E, G, B',           frozenset([4, 7, 11])),
    ('D Minor',  'D Minor Chord is D, F, A',           frozenset([2, 5, 9])),
    ('G Minor',  'G Minor Chord is G, B flat, D',      frozenset([7, 10, 2])),
    ('B Minor',  'B Minor Chord is B, D, F sharp',     frozenset([11, 2, 6])),
    # Augmented triads (root, major 3rd, augmented 5th)
    ('C Augmented',  'C Augmented Chord is C, E, G sharp',      frozenset([0, 4, 8])),
    ('F Augmented',  'F Augmented Chord is F, A, C sharp',      frozenset([5, 9, 1])),
    ('G Augmented',  'G Augmented Chord is G, B, D sharp',      frozenset([7, 11, 3])),
    ('D Augmented',  'D Augmented Chord is D, F sharp, A sharp', frozenset([2, 6, 10])),
    # Diminished triads (root, minor 3rd, diminished 5th)
    ('C Diminished',  'C Diminished Chord is C, E flat, G flat',      frozenset([0, 3, 6])),
    ('D Diminished',  'D Diminished Chord is D, F, A flat',           frozenset([2, 5, 8])),
    ('B Diminished',  'B Diminished Chord is B, D, F',                frozenset([11, 2, 5])),
    ('F sharp Diminished', 'F sharp Diminished Chord is F sharp, A, C', frozenset([6, 9, 0])),
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
