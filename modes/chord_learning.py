"""
modes/chord_learning.py — Chord Learning Mode.

While active, pressing 2+ keys simultaneously announces the chord name aloud.
Uses interval-set rotation matching to identify root, chord quality, and inversion.

Entry: hold KeySelect, press Pad 16 then Pad 2, release KeySelect (default).
Exit:  same sequence again (toggle).
"""

_NOTE_NAMES_TTS = [
    'C', 'D flat', 'D', 'E flat', 'E', 'F',
    'G flat', 'G', 'A flat', 'A', 'B flat', 'B',
]

_INVERSION_NAMES = ['', 'first inversion', 'second inversion', 'third inversion', 'fourth inversion']

# Interval tuples computed from sorted pitch classes (consecutive differences, no wrap).
# Key: tuple of semitone differences. Value: chord name for TTS.

_INTERVALS_2 = {
    (1,): 'minor second',
    (2,): 'major second',
    (3,): 'minor third',
    (4,): 'major third',
    (5,): 'perfect fourth',
    (6,): 'tritone',
    (7,): 'perfect fifth',
    (8,): 'minor sixth',
    (9,): 'major sixth',
    (10,): 'minor seventh',
    (11,): 'major seventh',
}

_TRIADS = {
    (4, 3): 'Major',
    (3, 4): 'minor',
    (3, 3): 'diminished',
    (4, 4): 'augmented',
    (2, 5): 'suspended second',
    (5, 2): 'suspended fourth',
}

_SEVENTHS = {
    (4, 3, 3): 'dominant seventh',
    (4, 3, 4): 'major seventh',
    (3, 4, 3): 'minor seventh',
    (3, 3, 3): 'diminished seventh',
    (3, 3, 4): 'half-diminished seventh',
}

_EXTENDED = {
    (4, 3, 2): 'major sixth',       # C E G A  → [0,4,7,9]
    (3, 4, 2): 'minor sixth',       # C Eb G A → [0,3,7,9]
    (2, 2, 3): 'add nine',          # C E G D  → [0,2,4,7]
    (2, 2, 3, 3): 'dominant ninth', # C E G Bb D → [0,2,4,7,10]
    (2, 2, 3, 4): 'major ninth',    # C E G B D  → [0,2,4,7,11]
    (2, 1, 4, 3): 'minor ninth',    # C Eb G Bb D → [0,2,3,7,10]
}

CHORD_SETS = {
    'minimal': {**_INTERVALS_2, **_TRIADS},
    'core_set': {**_INTERVALS_2, **_TRIADS, **_SEVENTHS},
    'extended': {**_INTERVALS_2, **_TRIADS, **_SEVENTHS, **_EXTENDED},
}


def _interval_tuple(notes: list[int]) -> tuple[int, ...]:
    """Consecutive differences between sorted integers (no wrap)."""
    return tuple(notes[i + 1] - notes[i] for i in range(len(notes) - 1))


def identify_chord(held_notes: frozenset, chord_set: str, bass_override: int | None = None) -> str | None:
    """Return a TTS chord name for the held notes, or None if unrecognized.

    Args:
        held_notes: Set of held MIDI note numbers.
        chord_set: One of 'minimal', 'core_set', 'extended'.
        bass_override: If given, use this MIDI note as the bass instead of min(held_notes).
                       Used only for testing; in production the bass is always min(held_notes).
    """
    if len(held_notes) < 2:
        return None

    table = CHORD_SETS.get(chord_set, CHORD_SETS['core_set'])
    pcs = sorted(set(n % 12 for n in held_notes))
    n = len(pcs)

    bass_note = bass_override if bass_override is not None else min(held_notes)
    bass_pc = bass_note % 12

    for i in range(n):
        rotated = pcs[i:] + [p + 12 for p in pcs[:i]]
        t = _interval_tuple(rotated)
        if t in table:
            root_pc = pcs[i]
            chord_name = table[t]
            # Find inversion: position of bass_pc in the rotated chord tones
            chord_pcs = [p % 12 for p in rotated]
            if bass_pc in chord_pcs:
                inv_idx = chord_pcs.index(bass_pc)
            else:
                inv_idx = 0
            root_name = _NOTE_NAMES_TTS[root_pc]
            if inv_idx == 0:
                return f'{root_name} {chord_name}'
            inv_label = _INVERSION_NAMES[inv_idx] if inv_idx < len(_INVERSION_NAMES) else f'inversion {inv_idx}'
            return f'{root_name} {chord_name}, {inv_label}'

    return None
