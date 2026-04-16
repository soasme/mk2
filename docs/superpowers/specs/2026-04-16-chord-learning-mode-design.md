# Chord Learning Mode — Design Spec

**Date:** 2026-04-16  
**Status:** Approved

---

## Overview

Chord Learning Mode is a new interactive mode for the LaunchKey Mini MK2 synthesizer. When active, pressing multiple keys simultaneously causes the system to announce the chord name aloud via TTS (e.g., "C Major", "B flat minor seventh, first inversion", "G perfect fifth"). It is intended as a real-time ear-training and theory reference tool.

---

## Entry and Exit

- **Entry/exit gesture:** Hold KeySelect (CC 105) and press the configured pad sequence, then release KeySelect. Default: pad 16, then pad 2 (`entry_pads = "16,2"`).
- This reuses the same `parse_entry_pads` / KeySelect mechanism already used by Note Challenge Mode.
- Mode exits automatically if the drum kit or tone is changed (same behavior as Note Challenge).
- Toggle semantics: same gesture exits if already active.

---

## Key Tracking

While `chord_learning_active` is true:

- `note_on` events on the keys channel add the note to `chord_learning_held` (a set).
- `note_off` events on the keys channel remove the note from `chord_learning_held`.
- Pad notes are not tracked.
- Every change to `chord_learning_held` emits a `ChordLearningNoteChangedEvent(held=frozenset(...))`.

---

## Chord Detection

Triggered immediately on every `ChordLearningNoteChangedEvent`. If fewer than 2 notes are held, nothing is announced.

Algorithm (in `modes/chord_learning.py`, `identify_chord`):

1. Extract pitch classes: `pcs = sorted(set(n % 12 for n in held_notes))`
2. Identify bass note: lowest MIDI note in `held_notes` → its pitch class is the bass PC.
3. Try all rotations of `pcs` (i.e., cyclic permutations):
   - Compute interval tuple for that rotation.
   - Look up in the active chord set's table.
   - First match → root PC = first element of that rotation.
4. Determine inversion: if bass PC ≠ root PC, find its position in the chord tones → "first inversion", "second inversion", etc.
5. Build TTS string: `"{root_name} {chord_suffix}"` or `"{root_name} {chord_suffix}, {inversion}"`.
6. If no rotation matches → return `None`, say nothing.

Root names use flat spelling for TTS: C, D flat, D, E flat, E, F, G flat, G, A flat, A, B flat, B.

---

## Chord Sets

Configured via `chord_set` in `[chord_learning]`. Three levels:

**Note: interval tuples are computed from sorted pitch classes (consecutive differences), not stacked thirds.**

### minimal
All 2-note intervals + 6 triads:

| Interval tuple | Name |
|---|---|
| `(1,)` | minor second |
| `(2,)` | major second |
| `(3,)` | minor third |
| `(4,)` | major third |
| `(5,)` | perfect fourth |
| `(6,)` | tritone |
| `(7,)` | perfect fifth |
| `(8,)` | minor sixth |
| `(9,)` | major sixth |
| `(10,)` | minor seventh |
| `(11,)` | major seventh |
| `(4, 3)` | Major |
| `(3, 4)` | minor |
| `(3, 3)` | diminished |
| `(4, 4)` | augmented |
| `(2, 5)` | suspended second |
| `(5, 2)` | suspended fourth |

### core_set (default)
Everything in minimal, plus:

| Interval tuple | Name |
|---|---|
| `(4, 3, 3)` | dominant seventh |
| `(4, 3, 4)` | major seventh |
| `(3, 4, 3)` | minor seventh |
| `(3, 3, 3)` | diminished seventh |
| `(3, 3, 4)` | half-diminished seventh |
| `(2, 5)` | suspended second |
| `(5, 2)` | suspended fourth |

### extended
Everything in core_set, plus:

| Interval tuple | Name |
|---|---|
| `(4, 3, 2)` | major sixth |
| `(3, 4, 2)` | minor sixth |
| `(2, 2, 3)` | add nine |
| `(2, 2, 3, 3)` | dominant ninth |
| `(2, 2, 3, 4)` | major ninth |
| `(2, 1, 4, 3)` | minor ninth |

---

## Configuration

New section in `config.toml`:

```toml
[chord_learning]
entry_pads = "16,2"        # KeySelect pad sequence to enter/exit the mode
chord_set  = "core_set"    # "minimal", "core_set", or "extended"
```

New fields loaded in `main()` and stored in `state`.

---

## New Code

### `modes/chord_learning.py` (new file)
Pure functions, no I/O:

- `CHORD_SETS: dict[str, dict[tuple, str]]` — maps chord set name → interval tuple → chord name
- `identify_chord(held_notes: frozenset, chord_set: str) -> str | None` — returns TTS string or None
- `_interval_tuple(pcs: list[int]) -> tuple[int, ...]` — intervals between adjacent sorted pitch classes (wrapping last to first across the octave)

### Events added to `main.py`

```python
@dataclass
class EnterChordLearningEvent: pass

@dataclass
class ExitChordLearningEvent: pass

@dataclass
class ChordLearningNoteChangedEvent:
    held: frozenset  # current set of held MIDI notes
```

### State fields added to `make_input_state`

```python
'chord_learning_active': False,
'chord_learning_held': set(),
'chord_learning_entry': parse_entry_pads('16,2'),
'chord_learning_chord_set': 'core_set',
```

### `parse_events` changes

- KeySelect release: check `chord_learning_entry` alongside `note_challenge_entry`; emit Enter/Exit events.
- `note_on` on keys channel while `chord_learning_active`: add to `chord_learning_held`, emit `ChordLearningNoteChangedEvent`.
- `note_off` on keys channel while `chord_learning_active`: remove from `chord_learning_held`, emit `ChordLearningNoteChangedEvent` always (identify_chord returns None for <2 notes, so nothing is said).
- `PercussionChangeEvent` / `ProgramChangeEvent` handlers: also exit Chord Learning Mode.

### `handle_event` changes

```python
elif isinstance(event, EnterChordLearningEvent):
    state['chord_learning_active'] = True
    state['chord_learning_held'] = set()
    speak("Chord Learning Mode")

elif isinstance(event, ExitChordLearningEvent):
    state['chord_learning_active'] = False
    state['chord_learning_held'] = set()
    speak("Goodbye")

elif isinstance(event, ChordLearningNoteChangedEvent):
    name = chord_learning.identify_chord(event.held, state['chord_learning_chord_set'])
    if name:
        speak(name)
```

---

## What Is Not Included

- No LED feedback (out of scope for this feature).
- No chord history tracking.
- No "quiz" mode (that would be a separate feature).
- No debouncing (continuous announcement chosen by user).
