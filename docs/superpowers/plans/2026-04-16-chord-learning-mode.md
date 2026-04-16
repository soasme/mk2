# Chord Learning Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chord Learning Mode that announces chord names aloud when multiple keys are held simultaneously.

**Architecture:** A new `modes/chord_learning.py` module provides pure chord-detection functions using interval-set rotation matching. `main.py` gains three new events and new state fields; `parse_events` tracks held notes and emits `ChordLearningNoteChangedEvent` on every change; `handle_event` calls `identify_chord` and speaks the result.

**Tech Stack:** Python 3.12+, `mido`, `fluidsynth` (pyfluidsynth), `uv` for env management. Tests run with `uv run python -m unittest test_main -v`.

---

> **Note:** One pre-existing test failure exists before this work begins:
> `test_key_select_press_prints_latched_target_channel` — do not fix it as part of this feature.

---

## File Map

| File | Change |
|------|--------|
| `modes/chord_learning.py` | **Create** — pure chord detection functions |
| `main.py` | **Modify** — new events, state fields, parse_events, handle_event, main() |
| `config.toml` | **Modify** — add `[chord_learning]` section |
| `test_main.py` | **Modify** — add `ChordLearningTests` and `ChordLearningParseEventsTests` classes |
| `AGENT.md` | **Modify** — document new mode |

---

## Task 1: Chord detection pure functions (TDD)

**Files:**
- Create: `modes/chord_learning.py`
- Modify: `test_main.py`

### How the algorithm works

Given a set of held MIDI notes (e.g., `{60, 64, 67}` = C4, E4, G4):

1. Extract unique pitch classes: `pcs = sorted(set(n % 12 for n in held))` → `[0, 4, 7]`
2. Find bass pitch class: `bass_pc = min(held) % 12` → `0` (C)
3. Try each rotation `i` of `pcs`:
   - Rotated list: `pcs[i:] + [p + 12 for p in pcs[:i]]`
   - Compute interval tuple: consecutive differences
   - Look up in chord set table
   - First match → `root_pc = pcs[i]`, `chord_name = table[interval_tuple]`
4. Determine inversion: position of `bass_pc` in the rotated (root-position) chord tones
   - Position 0 = root position (no suffix)
   - Position 1 = "first inversion", position 2 = "second inversion", etc.
5. Build TTS string: `"{root_name} {chord_name}"` or `"{root_name} {chord_name}, {inversion}"`

Root names use flat spelling: `['C', 'D flat', 'D', 'E flat', 'E', 'F', 'G flat', 'G', 'A flat', 'A', 'B flat', 'B']`

### Interval tuples reference

All tuples are computed from **sorted pitch classes** (consecutive differences, no octave wrap):

**2-note intervals** (tuple has 1 element = distance between the two PCs):

| Tuple | Name |
|-------|------|
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

**Triads** (3 notes, tuple has 2 elements):

| Tuple | Name |
|-------|------|
| `(4, 3)` | Major |
| `(3, 4)` | minor |
| `(3, 3)` | diminished |
| `(4, 4)` | augmented |
| `(2, 5)` | suspended second |
| `(5, 2)` | suspended fourth |

Note: sus2 and sus4 share the same pitch classes when rotated — the first matching rotation wins.

**7th chords** (4 notes, tuple has 3 elements):

| Tuple | Name |
|-------|------|
| `(4, 3, 3)` | dominant seventh |
| `(4, 3, 4)` | major seventh |
| `(3, 4, 3)` | minor seventh |
| `(3, 3, 3)` | diminished seventh |
| `(3, 3, 4)` | half-diminished seventh |

**Extended** (additions to core_set):

Computed from sorted pitch classes in one octave:

| Chord | Notes | Sorted PCs | Tuple | Name |
|-------|-------|-----------|-------|------|
| Major 6th | C E G A | [0,4,7,9] | `(4, 3, 2)` | major sixth |
| Minor 6th | C Eb G A | [0,3,7,9] | `(3, 4, 2)` | minor sixth |
| Add9 | C E G D | [0,2,4,7] | `(2, 2, 3)` | add nine |
| Dominant 9th | C E G Bb D | [0,2,4,7,10] | `(2, 2, 3, 3)` | dominant ninth |
| Major 9th | C E G B D | [0,2,4,7,11] | `(2, 2, 3, 4)` | major ninth |
| Minor 9th | C Eb G Bb D | [0,2,3,7,10] | `(2, 1, 4, 3)` | minor ninth |

### Steps

- [ ] **Step 1: Write failing tests for `identify_chord`**

Add a new class `ChordLearningTests` to `test_main.py`:

```python
from modes import chord_learning

class ChordLearningTests(unittest.TestCase):
    # --- 2-note intervals ---
    def test_perfect_fifth(self):
        # C4=60, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 67}), 'core_set'), 'C perfect fifth')

    def test_minor_third(self):
        # C4=60, Eb4=63
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63}), 'core_set'), 'C minor third')

    def test_tritone(self):
        # C4=60, F#4=66
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 66}), 'core_set'), 'C tritone')

    # --- Triads ---
    def test_c_major_root_position(self):
        # C4=60, E4=64, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67}), 'core_set'), 'C Major')

    def test_c_major_first_inversion(self):
        # E4=64 is bass, C4=60, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67}), 'core_set', bass_override=64), 'C Major, first inversion')

    def test_c_minor_root_position(self):
        # C4=60, Eb4=63, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63, 67}), 'core_set'), 'C minor')

    def test_b_flat_major(self):
        # Bb4=70, D5=74, F5=77
        self.assertEqual(chord_learning.identify_chord(frozenset({70, 74, 77}), 'core_set'), 'B flat Major')

    def test_diminished_triad(self):
        # C4=60, Eb4=63, Gb4=66
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63, 66}), 'core_set'), 'C diminished')

    def test_augmented_triad(self):
        # C4=60, E4=64, Ab4=68
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 68}), 'core_set'), 'C augmented')

    def test_sus2(self):
        # C4=60, D4=62, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 62, 67}), 'core_set'), 'C suspended second')

    def test_sus4(self):
        # C4=60, F4=65, G4=67
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 65, 67}), 'core_set'), 'C suspended fourth')

    # --- 7th chords ---
    def test_dominant_seventh(self):
        # C4=60, E4=64, G4=67, Bb4=70
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67, 70}), 'core_set'), 'C dominant seventh')

    def test_major_seventh(self):
        # C4=60, E4=64, G4=67, B4=71
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67, 71}), 'core_set'), 'C major seventh')

    def test_minor_seventh(self):
        # C4=60, Eb4=63, G4=67, Bb4=70
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63, 67, 70}), 'core_set'), 'C minor seventh')

    def test_minor_seventh_second_inversion(self):
        # G is bass (67), C4=60, Eb4=63, Bb4=70; bass_override=67
        self.assertEqual(
            chord_learning.identify_chord(frozenset({60, 63, 67, 70}), 'core_set', bass_override=67),
            'C minor seventh, second inversion'
        )

    def test_diminished_seventh(self):
        # C4=60, Eb4=63, Gb4=66, Bbb4=69 (A=69)
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63, 66, 69}), 'core_set'), 'C diminished seventh')

    def test_half_diminished_seventh(self):
        # C4=60, Eb4=63, Gb4=66, Bb4=70
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 63, 66, 70}), 'core_set'), 'C half-diminished seventh')

    # --- Returns None for fewer than 2 notes ---
    def test_single_note_returns_none(self):
        self.assertIsNone(chord_learning.identify_chord(frozenset({60}), 'core_set'))

    def test_empty_returns_none(self):
        self.assertIsNone(chord_learning.identify_chord(frozenset(), 'core_set'))

    # --- Returns None for unrecognized combination ---
    def test_unrecognized_returns_none(self):
        # C, D, E — whole-tone fragment, not in core_set
        self.assertIsNone(chord_learning.identify_chord(frozenset({60, 62, 64}), 'core_set'))

    # --- Extended set ---
    def test_major_sixth_extended(self):
        # C4=60, E4=64, G4=67, A4=69
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67, 69}), 'extended'), 'C major sixth')

    def test_dominant_ninth_extended(self):
        # C4=60, E4=64, G4=67, Bb4=70, D5=74
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67, 70, 74}), 'extended'), 'C dominant ninth')

    # --- Minimal set ---
    def test_minimal_has_triads(self):
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67}), 'minimal'), 'C Major')

    def test_minimal_no_seventh(self):
        # Dominant 7th not in minimal set
        self.assertIsNone(chord_learning.identify_chord(frozenset({60, 64, 67, 70}), 'minimal'))
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run python -m unittest test_main.ChordLearningTests -v 2>&1 | head -30
```

Expected: errors like `ModuleNotFoundError: No module named 'modes.chord_learning'` or `AttributeError`.

- [ ] **Step 3: Create `modes/chord_learning.py`**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run python -m unittest test_main.ChordLearningTests -v 2>&1
```

Expected: all `ChordLearningTests` pass. The pre-existing `test_key_select_press_prints_latched_target_channel` failure is unrelated — ignore it.

- [ ] **Step 5: Commit**

```bash
git add modes/chord_learning.py test_main.py
git commit -m "feat: add chord_learning module with interval-set rotation matching"
```

---

## Task 2: New events and state in main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Write failing tests for new state fields**

Add to `test_main.py`, inside `ParseEventsTests` class (or as a separate class `ChordLearningParseEventsTests`):

```python
class ChordLearningParseEventsTests(unittest.TestCase):
    def test_chord_learning_state_defaults(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        self.assertFalse(state['chord_learning_active'])
        self.assertEqual(state['chord_learning_held'], set())
        self.assertEqual(state['chord_learning_chord_set'], 'core_set')
        # entry = parse_entry_pads('16,2') = ([], True, [2])
        self.assertEqual(state['chord_learning_entry'], ([], True, [2]))

    def test_enter_chord_learning_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        # Hold KeySelect
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            # Press Pad 16 (note 47) then Pad 2 (note 41)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=41, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.EnterChordLearningEvent)

    def test_exit_chord_learning_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=41, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.ExitChordLearningEvent)

    def test_note_on_adds_to_held_and_emits_changed_event(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True

        events = main.parse_events(
            msg('note_on', note=60, velocity=100, channel=state['ch_keys']), state
        )

        # NoteOnEvent is still emitted (note still plays)
        note_on_events = [e for e in events if isinstance(e, main.NoteOnEvent)]
        self.assertEqual(len(note_on_events), 1)
        self.assertEqual(note_on_events[0].note, 60)

        # ChordLearningNoteChangedEvent is also emitted
        changed_events = [e for e in events if isinstance(e, main.ChordLearningNoteChangedEvent)]
        self.assertEqual(len(changed_events), 1)
        self.assertEqual(changed_events[0].held, frozenset({60}))

        # State updated
        self.assertIn(60, state['chord_learning_held'])

    def test_note_off_removes_from_held_and_emits_changed_event(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        state['chord_learning_held'] = {60, 64}

        events = main.parse_events(
            msg('note_off', note=60, channel=state['ch_keys']), state
        )

        changed_events = [e for e in events if isinstance(e, main.ChordLearningNoteChangedEvent)]
        self.assertEqual(len(changed_events), 1)
        self.assertEqual(changed_events[0].held, frozenset({64}))
        self.assertNotIn(60, state['chord_learning_held'])

    def test_chord_learning_does_not_intercept_pad_notes(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True

        events = main.parse_events(
            msg('note_on', note=40, velocity=100, channel=state['ch_pads']), state
        )

        changed_events = [e for e in events if isinstance(e, main.ChordLearningNoteChangedEvent)]
        self.assertEqual(len(changed_events), 0)
        self.assertEqual(state['chord_learning_held'], set())
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run python -m unittest test_main.ChordLearningParseEventsTests -v 2>&1
```

Expected: `AttributeError: module 'main' has no attribute 'EnterChordLearningEvent'` or similar.

- [ ] **Step 3: Add new event dataclasses to `main.py`**

Add after the `NoteChallengeBingoEvent` dataclass (around line 153):

```python
@dataclass
class EnterChordLearningEvent:
    pass

@dataclass
class ExitChordLearningEvent:
    pass

@dataclass
class ChordLearningNoteChangedEvent:
    held: frozenset  # current set of held MIDI notes
```

- [ ] **Step 4: Add new state fields to `make_input_state` in `main.py`**

Add at the end of the returned dict in `make_input_state` (after the `note_challenge_captured` entry):

```python
        # Chord Learning Mode
        'chord_learning_active': False,
        'chord_learning_held': set(),
        'chord_learning_entry': parse_entry_pads('16,2'),
        'chord_learning_chord_set': 'core_set',
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run python -m unittest test_main.ChordLearningParseEventsTests -v 2>&1
```

Expected: `test_chord_learning_state_defaults` and `test_enter_chord_learning_mode` etc. may still fail — that's fine, we fix parse_events in the next task. Only check that state field tests pass now.

- [ ] **Step 6: Commit**

```bash
git add main.py test_main.py
git commit -m "feat: add chord learning events and state fields"
```

---

## Task 3: Update parse_events

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update parse_events — KeySelect release to check chord_learning_entry**

In `main.py`, in the `elif msg.control == CC_KEY_SELECT:` → `else:` branch (KeySelect release), after the Note Challenge toggle check (around line 344), add an `elif` for Chord Learning:

Find this block:
```python
                if (digits == e_digits
                        and state['key_select_bank_sep'] == e_bank_sep
                        and bank_digits == e_bank_digits):
                    if state['note_challenge_active']:
                        events.append(ExitNoteChallengeEvent())
                    else:
                        events.append(EnterNoteChallengeEvent())
                elif digits:
```

Replace with:
```python
                cl_digits, cl_bank_sep, cl_bank_digits = state['chord_learning_entry']
                if (digits == e_digits
                        and state['key_select_bank_sep'] == e_bank_sep
                        and bank_digits == e_bank_digits):
                    if state['note_challenge_active']:
                        events.append(ExitNoteChallengeEvent())
                    else:
                        events.append(EnterNoteChallengeEvent())
                elif (digits == cl_digits
                        and state['key_select_bank_sep'] == cl_bank_sep
                        and bank_digits == cl_bank_digits):
                    if state['chord_learning_active']:
                        events.append(ExitChordLearningEvent())
                    else:
                        events.append(EnterChordLearningEvent())
                elif digits:
```

- [ ] **Step 2: Update parse_events — note_on tracking for chord learning**

In `main.py`, in the `note_on` branch, find the block that handles Note Challenge tracking (around line 265):

```python
            # Note Challenge Mode: track key presses and check for a match
            if state['note_challenge_active'] and msg.channel == state['ch_keys']:
```

Add chord learning tracking immediately after that entire `if` block (before the `return events` or the next `elif`). Add it as a new `if` block (not `elif`, so it runs independently):

```python
            # Chord Learning Mode: track held notes
            if state['chord_learning_active'] and msg.channel == state['ch_keys']:
                state['chord_learning_held'].add(msg.note)
                events.append(ChordLearningNoteChangedEvent(held=frozenset(state['chord_learning_held'])))
```

- [ ] **Step 3: Update parse_events — note_off tracking for chord learning**

In `main.py`, in the `note_off` branch, find the final `else` block (around line 292):

```python
        else:
            ch = state['current_keys_channel'] if msg.channel == state['ch_keys'] else msg.channel
            events.append(NoteOffEvent(ch, msg.note))
```

Replace with:
```python
        else:
            ch = state['current_keys_channel'] if msg.channel == state['ch_keys'] else msg.channel
            events.append(NoteOffEvent(ch, msg.note))
            # Chord Learning Mode: update held notes
            if state['chord_learning_active'] and msg.channel == state['ch_keys']:
                state['chord_learning_held'].discard(msg.note)
                events.append(ChordLearningNoteChangedEvent(held=frozenset(state['chord_learning_held'])))
```

- [ ] **Step 4: Run all chord learning parse_events tests**

```bash
uv run python -m unittest test_main.ChordLearningParseEventsTests -v 2>&1
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add main.py test_main.py
git commit -m "feat: update parse_events to track held notes for chord learning mode"
```

---

## Task 4: Update handle_event

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add chord_learning import to main.py**

At the top of `main.py`, find:
```python
from modes import note_challenge
```

Replace with:
```python
from modes import chord_learning, note_challenge
```

- [ ] **Step 2: Add chord learning handlers to handle_event**

At the end of `handle_event` in `main.py`, after the `NoteChallengeBingoEvent` block, add:

```python
    elif isinstance(event, EnterChordLearningEvent):
        state['chord_learning_active'] = True
        state['chord_learning_held'] = set()
        print("Chord Learning Mode: active")
        speak("Chord Learning Mode")
    elif isinstance(event, ExitChordLearningEvent):
        state['chord_learning_active'] = False
        state['chord_learning_held'] = set()
        print("Chord Learning Mode: exited")
        speak("Goodbye")
    elif isinstance(event, ChordLearningNoteChangedEvent):
        name = chord_learning.identify_chord(event.held, state['chord_learning_chord_set'])
        if name:
            print(f"Chord Learning Mode: {name}")
            speak(name)
```

- [ ] **Step 3: Update PercussionChangeEvent handler to exit chord learning mode**

Find in `handle_event`:
```python
    elif isinstance(event, PercussionChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (drum kit changed)")
```

Replace with:
```python
    elif isinstance(event, PercussionChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (drum kit changed)")
        if state['chord_learning_active']:
            state['chord_learning_active'] = False
            state['chord_learning_held'] = set()
            print("Chord Learning Mode: exited (drum kit changed)")
```

- [ ] **Step 4: Update ProgramChangeEvent handler to exit chord learning mode**

Find in `handle_event`:
```python
    elif isinstance(event, ProgramChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (tone changed)")
```

Replace with:
```python
    elif isinstance(event, ProgramChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (tone changed)")
        if state['chord_learning_active']:
            state['chord_learning_active'] = False
            state['chord_learning_held'] = set()
            print("Chord Learning Mode: exited (tone changed)")
```

- [ ] **Step 5: Run full test suite**

```bash
uv run python -m unittest test_main -v 2>&1
```

Expected: all `ChordLearningTests` and `ChordLearningParseEventsTests` pass. The pre-existing `test_key_select_press_prints_latched_target_channel` failure continues to be the only failure.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: handle chord learning events in handle_event"
```

---

## Task 5: Config and main() wiring

**Files:**
- Modify: `config.toml`
- Modify: `main.py`

- [ ] **Step 1: Add `[chord_learning]` section to `config.toml`**

Append to the end of `config.toml`:

```toml
# -----------------------------------------------------------------------------
# Chord Learning Mode settings
# -----------------------------------------------------------------------------
[chord_learning]
entry_pads = "16,2"      # KeySelect pad sequence to enter/exit the mode
chord_set  = "core_set"  # "minimal", "core_set", or "extended"
```

- [ ] **Step 2: Wire config in `main()`**

In `main.py`, find the section after `challenge_cfg`:

```python
    cfg           = load_config()
    midi_cfg      = cfg.get('midi', {})
    synth_cfg     = cfg.get('synth', {})
    challenge_cfg = cfg.get('note_challenge', {})
```

Replace with:
```python
    cfg           = load_config()
    midi_cfg      = cfg.get('midi', {})
    synth_cfg     = cfg.get('synth', {})
    challenge_cfg = cfg.get('note_challenge', {})
    cl_cfg        = cfg.get('chord_learning', {})
```

Then find (near the end of `main()`) the block that sets Note Challenge config on state:

```python
    state['note_challenge_entry'] = parse_entry_pads(challenge_cfg.get('entry_pads', '16,1'))
```

After it, add:

```python
    state['chord_learning_entry'] = parse_entry_pads(cl_cfg.get('entry_pads', '16,2'))
    state['chord_learning_chord_set'] = cl_cfg.get('chord_set', 'core_set')
```

- [ ] **Step 3: Run full test suite**

```bash
uv run python -m unittest test_main -v 2>&1
```

Expected: same results as before — only the pre-existing test fails.

- [ ] **Step 4: Commit**

```bash
git add config.toml main.py
git commit -m "feat: wire chord_learning config in main()"
```

---

## Task 6: Update AGENT.md

**Files:**
- Modify: `AGENT.md`

- [ ] **Step 1: Add Chord Learning Mode section to AGENT.md**

In `AGENT.md`, add a new section after `## Note Challenge Mode`:

```markdown
## Chord Learning Mode

A real-time chord identification tool. While active, holding 2 or more keys simultaneously announces the chord name aloud via TTS (e.g., "C Major", "B flat minor seventh, first inversion", "G perfect fifth").

Entry/exit: hold KeySelect and press the pad sequence configured in `chord_learning.entry_pads` (default `16,2`).

While active:
- Key notes still play normally through FluidSynth
- Every change to the set of held keys triggers chord detection
- If the held notes form a recognized chord, its name is spoken via TTS
- Unrecognized combinations produce no output

Configuration in `config.toml` under `[chord_learning]`: `entry_pads`, `chord_set` (`"minimal"`, `"core_set"`, `"extended"`).

Logic is in `modes/chord_learning.py` (pure functions, no I/O). Orchestration is in `handle_event` in `main.py`.
```

Also update the **File Map** table in `AGENT.md` to add:

```
| `modes/chord_learning.py`  | Chord Learning Mode — interval-set chord detection (pure functions, no I/O) |
```

Also update the **Input State Machine** table to add:

```
| `chord_learning_active` | True when Chord Learning Mode is running |
| `chord_learning_held`   | Set of currently held MIDI note numbers |
| `chord_learning_chord_set` | Active chord recognition set name |
```

- [ ] **Step 2: Commit**

```bash
git add AGENT.md
git commit -m "docs: document chord learning mode in AGENT.md"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Entry: hold KeySelect + pad 16, pad 2 | Task 3 (parse_events KeySelect release) |
| Continuous announcement on note change | Task 3 (emits event on every note_on/note_off) |
| 2-note intervals named | Task 1 (_INTERVALS_2 table in chord_learning.py) |
| Inversions detected and named | Task 1 (inversion detection in identify_chord) |
| Configurable chord sets: minimal/core_set/extended | Task 1 (CHORD_SETS dict) + Task 5 (config) |
| Unrecognized combinations: say nothing | Task 4 (handle_event only speaks if name is not None) |
| Auto-exit on drum kit/tone change | Task 4 (PercussionChangeEvent + ProgramChangeEvent handlers) |
| Notes still play while in chord learning mode | Task 3 (NoteOnEvent still appended) |

**Placeholder scan:** None found.

**Type consistency:**
- `ChordLearningNoteChangedEvent.held` is `frozenset` — used as `frozenset` in parse_events and `identify_chord` signature. ✓
- `identify_chord(held_notes: frozenset, chord_set: str, bass_override: int | None = None)` — `bass_override` only used in tests; production always passes 2 args. ✓
- `state['chord_learning_held']` is a mutable `set`; converted to `frozenset` when creating `ChordLearningNoteChangedEvent`. ✓
- `parse_entry_pads` return type `(list, bool, list)` — matches `chord_learning_entry` usage. ✓
