"""
modes/chord_progression.py — Chord Progression Mode.

The player presses a key (C3–C5) to trigger a named chord progression in
C Major.  The progression loops continuously until a different key is pressed
or the mode is exited.

Entry: hold KeySelect, press Pad 16 then Pad 5, release KeySelect.
Exit:  same sequence again (toggle).
"""
import threading
import time

# ---------------------------------------------------------------------------
# Chord building
# ---------------------------------------------------------------------------

_INTERVALS = {
    'major':      [0, 4, 7],
    'minor':      [0, 3, 7],
    'diminished': [0, 3, 6],
}


def build_chord_notes(root_midi: int, quality: str) -> list[int]:
    """Return MIDI note numbers for a chord rooted at root_midi."""
    intervals = _INTERVALS[quality]
    return [root_midi + i for i in intervals]


# ---------------------------------------------------------------------------
# Progressions: MIDI note 48 (C3) … 72 (C5)
# Each entry: (display_name, [(root_midi, quality), ...])
# Voicing uses octave 4 as base: C4=60, D4=62, …
# ---------------------------------------------------------------------------

# Helper: chord root as MIDI note in octave 4
_C4 = 60
_D4 = 62
_E4 = 64
_F4 = 65
_G4 = 67
_A4 = 69  # Actually A3=57 is more common for Am voicing; use 57 for Am
_B4 = 71

# Am voicing in "octave 4 context" — keep A below C for natural voice leading
_Am_root = 57   # A3
_Em_root = 64   # E4
_Dm_root = 62   # D4
_Bdim_root = 59  # B3

PROGRESSIONS: dict[int, tuple[str, list[tuple[int, str]]]] = {
    48: ("I IV V VI",    [(_C4, 'major'), (_F4, 'major'), (_G4, 'major'), (_Am_root, 'minor')]),
    49: ("VI IV I V",    [(_Am_root, 'minor'), (_F4, 'major'), (_C4, 'major'), (_G4, 'major')]),
    50: ("I V VI IV",    [(_C4, 'major'), (_G4, 'major'), (_Am_root, 'minor'), (_F4, 'major')]),
    51: ("I VI IV V",    [(_C4, 'major'), (_Am_root, 'minor'), (_F4, 'major'), (_G4, 'major')]),
    52: ("II V I",       [(_Dm_root, 'minor'), (_G4, 'major'), (_C4, 'major')]),
    53: ("I IV VII IV",  [(_C4, 'major'), (_F4, 'major'), (_Bdim_root, 'diminished'), (_F4, 'major')]),
    54: ("I III IV V",   [(_C4, 'major'), (_Em_root, 'minor'), (_F4, 'major'), (_G4, 'major')]),
    55: ("VI VII I",     [(_Am_root, 'minor'), (_Bdim_root, 'diminished'), (_C4, 'major')]),
    56: ("I V IV",       [(_C4, 'major'), (_G4, 'major'), (_F4, 'major')]),
    57: ("I II IV I",    [(_C4, 'major'), (_Dm_root, 'minor'), (_F4, 'major'), (_C4, 'major')]),
    58: ("IV I V VI",    [(_F4, 'major'), (_C4, 'major'), (_G4, 'major'), (_Am_root, 'minor')]),
    59: ("I VI III VII", [(_C4, 'major'), (_Am_root, 'minor'), (_Em_root, 'minor'), (_Bdim_root, 'diminished')]),
    60: ("I IV I V",     [(_C4, 'major'), (_F4, 'major'), (_C4, 'major'), (_G4, 'major')]),
    61: ("II IV V I",    [(_Dm_root, 'minor'), (_F4, 'major'), (_G4, 'major'), (_C4, 'major')]),
    62: ("I VII VI V",   [(_C4, 'major'), (_Bdim_root, 'diminished'), (_Am_root, 'minor'), (_G4, 'major')]),
    63: ("I III VI IV",  [(_C4, 'major'), (_Em_root, 'minor'), (_Am_root, 'minor'), (_F4, 'major')]),
    64: ("IV V III VI",  [(_F4, 'major'), (_G4, 'major'), (_Em_root, 'minor'), (_Am_root, 'minor')]),
    65: ("I II V",       [(_C4, 'major'), (_Dm_root, 'minor'), (_G4, 'major')]),
    66: ("VI IV VII I",  [(_Am_root, 'minor'), (_F4, 'major'), (_Bdim_root, 'diminished'), (_C4, 'major')]),
    67: ("I V VI III IV",[(_C4, 'major'), (_G4, 'major'), (_Am_root, 'minor'), (_Em_root, 'minor'), (_F4, 'major')]),
    68: ("IV VI I V",    [(_F4, 'major'), (_Am_root, 'minor'), (_C4, 'major'), (_G4, 'major')]),
    69: ("II V I IV",    [(_Dm_root, 'minor'), (_G4, 'major'), (_C4, 'major'), (_F4, 'major')]),
    70: ("VI II V I",    [(_Am_root, 'minor'), (_Dm_root, 'minor'), (_G4, 'major'), (_C4, 'major')]),
    71: ("I IV VI V",    [(_C4, 'major'), (_F4, 'major'), (_Am_root, 'minor'), (_G4, 'major')]),
    72: ("I II III IV",  [(_C4, 'major'), (_Dm_root, 'minor'), (_Em_root, 'minor'), (_F4, 'major')]),
}

PROGRESSION_MIN = 48  # C3
PROGRESSION_MAX = 72  # C5


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

CHORD_DURATION = 0.7   # seconds notes are held
CHORD_GAP = 0.1        # silence between chords


def play_progression_loop(
    chords: list[tuple[int, str]],
    channel: int,
    fs,
    stop_event: threading.Event,
) -> None:
    """Loop the chord progression until stop_event is set.

    Args:
        chords:     list of (root_midi, quality) tuples.
        channel:    MIDI channel for note output.
        fs:         FluidSynth instance.
        stop_event: set to stop playback.
    """
    while not stop_event.is_set():
        for root, quality in chords:
            if stop_event.is_set():
                return
            notes = build_chord_notes(root, quality)
            for n in notes:
                fs.noteon(channel, n, 90)
            if stop_event.wait(CHORD_DURATION):
                for n in notes:
                    fs.noteoff(channel, n)
                return
            for n in notes:
                fs.noteoff(channel, n)
            if stop_event.wait(CHORD_GAP):
                return
