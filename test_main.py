import contextlib
import io
import sys
import threading
import time
import types
import unittest
from types import SimpleNamespace

sys.modules.setdefault('mido', types.SimpleNamespace())
sys.modules.setdefault('fluidsynth', types.SimpleNamespace())

import main
from modes import chord_learning
import modes.loop_mode as loop_mode_module


def msg(msg_type, **kwargs):
    return SimpleNamespace(type=msg_type, **kwargs)


class ParseEventsTests(unittest.TestCase):
    def test_scene_button_cc_mappings(self):
        self.assertEqual(main.CC_PAD_SELECT, 104)
        self.assertEqual(main.CC_KEY_SELECT, 105)
        self.assertEqual(main.CC_LOOP_RECORD, 108)
        self.assertEqual(main.CC_LOOP_PLAYBACK, 109)

    def test_key_select_press_prints_latched_target_channel(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['last_keys_channel'] = 1

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            events = main.parse_events(
                msg('control_change', control=main.CC_KEY_SELECT, value=127),
                state,
            )

        self.assertEqual(events, [])
        self.assertEqual(state['key_select_channel'], 1)
        self.assertIn(
            "KeySelect Button is pressed (target channel index 1, ch2)",
            stdout.getvalue(),
        )

    def test_key_select_uses_channel_latched_on_press(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        original_channel_select = main.CC_CHANNEL_SELECT
        main.CC_CHANNEL_SELECT = 110
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                main.parse_events(
                    msg('control_change', control=main.CC_KEY_SELECT, value=127),
                    state,
                )
                main.parse_events(
                    msg('control_change', control=main.CC_CHANNEL_SELECT, value=127),
                    state,
                )
                main.parse_events(
                    msg('note_on', note=41, velocity=127, channel=state['ch_pads']),
                    state,
                )
                main.parse_events(
                    msg('control_change', control=main.CC_CHANNEL_SELECT, value=0),
                    state,
                )
                main.parse_events(
                    msg('note_on', note=40, velocity=127, channel=state['ch_pads']),
                    state,
                )

                events = main.parse_events(
                    msg('control_change', control=main.CC_KEY_SELECT, value=0),
                    state,
                )
        finally:
            main.CC_CHANNEL_SELECT = original_channel_select

        self.assertEqual(state['current_keys_channel'], 1)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.ProgramChangeEvent)
        self.assertEqual(events[0].channel, 0)
        self.assertEqual(events[0].keys_program, 0)


class TtsTests(unittest.TestCase):
    def test_normalize_say_text_marks_standalone_a(self):
        self.assertEqual(main.normalize_say_text('A Major'), 'A. Major')
        self.assertEqual(main.normalize_say_text('A minor seventh, first inversion'), 'A. minor seventh, first inversion')

    def test_normalize_say_text_leaves_normal_words_alone(self):
        self.assertEqual(main.normalize_say_text('Acoustic Grand Piano'), 'Acoustic Grand Piano')
        self.assertEqual(main.normalize_say_text('Bingo'), 'Bingo')
        self.assertEqual(main.normalize_say_text('B flat minor seventh'), 'B flat minor seventh')
        self.assertEqual(main.normalize_say_text('C 4, E 4, G 4'), 'C 4, E 4, G 4')


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
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67}), 'core_set', _bass_override=64), 'C Major, first inversion')

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

    def test_prefers_root_position_sus4_over_inverted_sus2(self):
        # A3=57, D4=62, E4=64 can be heard as Dsus2/A or Asus4; prefer root-position Asus4.
        self.assertEqual(chord_learning.identify_chord(frozenset({57, 62, 64}), 'core_set'), 'A suspended fourth')

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
        # G is bass (67), C4=60, Eb4=63, Bb4=70; _bass_override=67
        self.assertEqual(
            chord_learning.identify_chord(frozenset({60, 63, 67, 70}), 'core_set', _bass_override=67),
            'C minor seventh, second inversion'
        )

    def test_prefers_root_position_major_sixth_over_inverted_minor_seventh(self):
        # C4=60, E4=64, G4=67, A4=69 can be heard as C6 or Am7/C; prefer root-position C6.
        self.assertEqual(chord_learning.identify_chord(frozenset({60, 64, 67, 69}), 'extended'), 'C major sixth')

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


class ChordLearningParseEventsTests(unittest.TestCase):
    def test_chord_learning_state_defaults(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        self.assertFalse(state['chord_learning_active'])
        self.assertEqual(state['chord_learning_held'], set())
        self.assertEqual(state['chord_learning_chord_set'], 'core_set')
        self.assertEqual(state['chord_learning_announce_delay'], 0.2)
        self.assertIsNone(state['chord_learning_announce_timer'])
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

    def test_reenter_chord_learning_mode_when_already_active(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=41, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.EnterChordLearningEvent)

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
        self.assertFalse(changed_events[0].is_release)

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
        self.assertTrue(changed_events[0].is_release)
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


class ChordLearningHandleEventTests(unittest.TestCase):
    def test_note_changed_uses_configured_delay_and_ignores_stale_timer(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        state['chord_learning_announce_delay'] = 0.75
        state['chord_learning_held'] = {60, 64}

        timers = []
        spoken = []

        class FakeTimer:
            def __init__(self, delay, func):
                self.delay = delay
                self.func = func
                self.daemon = False
                self.started = False
                self.canceled = False
                timers.append(self)

            def start(self):
                self.started = True

            def cancel(self):
                self.canceled = True

        original_timer = main.threading.Timer
        original_speak = main.speak
        original_identify = main.chord_learning.identify_chord
        try:
            main.threading.Timer = FakeTimer
            main.speak = lambda text, wait=False: spoken.append((text, wait))
            main.chord_learning.identify_chord = lambda held, chord_set: {
                frozenset({60, 64}): 'C major third',
                frozenset({60, 64, 67}): 'C Major',
            }.get(held)

            main.handle_event(
                main.ChordLearningNoteChangedEvent(held=frozenset({60, 64}), is_release=False),
                fs=None,
                ch_keys=0,
                ch_pads=9,
                sfid=0,
                state=state,
            )
            first_timer = timers[-1]
            self.assertEqual(first_timer.delay, 0.75)
            self.assertTrue(first_timer.started)
            self.assertIs(state['chord_learning_announce_timer'], first_timer)

            state['chord_learning_held'] = {60, 64, 67}
            main.handle_event(
                main.ChordLearningNoteChangedEvent(held=frozenset({60, 64, 67}), is_release=False),
                fs=None,
                ch_keys=0,
                ch_pads=9,
                sfid=0,
                state=state,
            )
            second_timer = timers[-1]
            self.assertTrue(first_timer.canceled)
            self.assertIs(state['chord_learning_announce_timer'], second_timer)

            first_timer.func()
            self.assertEqual(spoken, [])

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                second_timer.func()
            self.assertEqual(spoken, [('C Major', False)])
            self.assertIn("Chord Learning Mode: C Major", stdout.getvalue())
            self.assertIsNone(state['chord_learning_announce_timer'])
        finally:
            main.threading.Timer = original_timer
            main.speak = original_speak
            main.chord_learning.identify_chord = original_identify

    def test_note_release_cancels_pending_announcement_without_scheduling_new_one(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        state['chord_learning_held'] = {57, 59, 64}

        timers = []

        class FakeTimer:
            def __init__(self, delay, func):
                self.delay = delay
                self.func = func
                self.daemon = False
                self.started = False
                self.canceled = False
                timers.append(self)

            def start(self):
                self.started = True

            def cancel(self):
                self.canceled = True

        original_timer = main.threading.Timer
        try:
            main.threading.Timer = FakeTimer

            main.handle_event(
                main.ChordLearningNoteChangedEvent(held=frozenset({57, 59, 64}), is_release=False),
                fs=None,
                ch_keys=0,
                ch_pads=9,
                sfid=0,
                state=state,
            )
            first_timer = timers[-1]
            self.assertIs(state['chord_learning_announce_timer'], first_timer)

            state['chord_learning_held'] = {57, 64}
            main.handle_event(
                main.ChordLearningNoteChangedEvent(held=frozenset({57, 64}), is_release=True),
                fs=None,
                ch_keys=0,
                ch_pads=9,
                sfid=0,
                state=state,
            )

            self.assertTrue(first_timer.canceled)
            self.assertIsNone(state['chord_learning_announce_timer'])
            self.assertEqual(len(timers), 1)
        finally:
            main.threading.Timer = original_timer

    def test_program_change_cancels_pending_chord_learning_announcement(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['chord_learning_active'] = True
        state['chord_learning_held'] = {60, 64, 67}

        class FakeTimer:
            def __init__(self):
                self.canceled = False

            def cancel(self):
                self.canceled = True

        class FakeSynth:
            def program_select(self, channel, sfid, bank, program):
                return 0

            def cc(self, channel, control, value):
                pass

        timer = FakeTimer()
        state['chord_learning_announce_timer'] = timer

        with contextlib.redirect_stdout(io.StringIO()):
            main.handle_event(
                main.ProgramChangeEvent(channel=0, keys_bank=0, keys_program=0),
                fs=FakeSynth(),
                ch_keys=0,
                ch_pads=9,
                sfid=1,
                state=state,
            )

        self.assertTrue(timer.canceled)
        self.assertFalse(state['chord_learning_active'])
        self.assertEqual(state['chord_learning_held'], set())
        self.assertIsNone(state['chord_learning_announce_timer'])



class LoopModeTests(unittest.TestCase):
    def test_loop_track_default_is_empty(self):
        track = loop_mode_module.LoopTrack(events=[], duration=0.0)
        self.assertEqual(track.events, [])
        self.assertEqual(track.duration, 0.0)

    def test_play_track_loop_plays_events_in_order(self):
        played = []
        stop_event = threading.Event()

        class FakeSynth:
            def noteon(self, channel, note, velocity):
                played.append(('noteon', channel, note, velocity))

            def noteoff(self, channel, note):
                played.append(('noteoff', channel, note))

        track = loop_mode_module.LoopTrack(
            events=[
                (0.0,  'note_on',  0, 60, 100),
                (0.05, 'note_off', 0, 60, 0),
            ],
            duration=0.1,
        )

        t = threading.Thread(
            target=loop_mode_module.play_track_loop,
            args=(track, FakeSynth(), stop_event),
            daemon=True,
        )
        t.start()
        time.sleep(0.25)  # let it loop twice
        stop_event.set()
        t.join(timeout=1.0)

        # At least two iterations: noteon, noteoff, noteon, noteoff
        self.assertGreaterEqual(played.count(('noteon', 0, 60, 100)), 2)
        self.assertGreaterEqual(played.count(('noteoff', 0, 60)), 2)

    def test_play_track_loop_stops_promptly_on_stop_event(self):
        stop_event = threading.Event()

        class FakeSynth:
            def noteon(self, *a): pass
            def noteoff(self, *a): pass

        track = loop_mode_module.LoopTrack(
            events=[(0.0, 'note_on', 0, 60, 100)],
            duration=60.0,  # very long loop
        )

        t = threading.Thread(
            target=loop_mode_module.play_track_loop,
            args=(track, FakeSynth(), stop_event),
            daemon=True,
        )
        t.start()
        time.sleep(0.05)
        stop_event.set()
        t.join(timeout=0.5)
        self.assertFalse(t.is_alive())


class LoopModeParseEventsTests(unittest.TestCase):
    def test_loop_mode_state_defaults(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        self.assertFalse(state['loop_mode_active'])
        self.assertEqual(state['loop_mode_n_tracks'], 4)
        self.assertEqual(len(state['loop_mode_tracks']), 4)
        self.assertTrue(all(t is None for t in state['loop_mode_tracks']))
        self.assertEqual(state['loop_mode_current_track'], 0)
        self.assertFalse(state['loop_mode_recording'])
        self.assertEqual(state['loop_mode_record_start'], 0.0)
        self.assertEqual(state['loop_mode_record_buffer'], [])
        self.assertFalse(state['loop_mode_playing'])
        self.assertEqual(len(state['loop_mode_play_stop_events']), 4)
        self.assertTrue(all(e is None for e in state['loop_mode_play_stop_events']))
        # entry = parse_entry_pads('16,3') = ([], True, [3])
        self.assertEqual(state['loop_mode_entry'], ([], True, [3]))

    def test_cc_track_constants(self):
        self.assertEqual(main.CC_TRACK_LEFT, 103)
        self.assertEqual(main.CC_TRACK_RIGHT, 102)

    def test_enter_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=42, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.EnterLoopModeEvent)

    def test_exit_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=42, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.ExitLoopModeEvent)

    def test_loop_mode_entry_does_not_also_emit_program_change(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127), state)
            main.parse_events(msg('note_on', note=47, velocity=127, channel=state['ch_pads']), state)
            main.parse_events(msg('note_on', note=42, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0), state)

        self.assertFalse(any(isinstance(e, main.ProgramChangeEvent) for e in events))

    def test_track_right_in_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_TRACK_RIGHT, value=127), state
        )
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModeTrackRightEvent)

    def test_track_left_in_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_TRACK_LEFT, value=127), state
        )
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModeTrackLeftEvent)

    def test_track_right_release_ignored(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', channel=0, control=main.CC_TRACK_RIGHT, value=0), state
        )
        self.assertFalse(any(isinstance(e, main.LoopModeTrackRightEvent) for e in events))

    def test_track_right_outside_loop_mode_is_passthrough_cc(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = False
        events = main.parse_events(
            msg('control_change', channel=0, control=main.CC_TRACK_RIGHT, value=127), state
        )
        self.assertTrue(any(isinstance(e, main.CCEvent) for e in events))
        self.assertFalse(any(isinstance(e, main.LoopModeTrackRightEvent) for e in events))

    def test_pad_select_bare_tap_in_loop_mode_emits_record_toggle(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            # Press PadSelect (CC 104)
            main.parse_events(msg('control_change', control=main.CC_PAD_SELECT, value=127, channel=0), state)
            # Release without pressing any digit pad
            events = main.parse_events(msg('control_change', control=main.CC_PAD_SELECT, value=0, channel=0), state)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModeRecordToggleEvent)

    def test_pad_select_with_digit_in_loop_mode_emits_percussion_change(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_PAD_SELECT, value=127, channel=0), state)
            main.parse_events(msg('note_on', note=40, velocity=127, channel=state['ch_pads']), state)
            events = main.parse_events(msg('control_change', control=main.CC_PAD_SELECT, value=0, channel=0), state)
        self.assertTrue(any(isinstance(e, main.PercussionChangeEvent) for e in events))
        self.assertFalse(any(isinstance(e, main.LoopModeRecordToggleEvent) for e in events))

    def test_key_select_bare_tap_in_loop_mode_emits_playback_toggle(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127, channel=0), state)
            # Release without pressing any pad at all
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0, channel=0), state)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModePlaybackToggleEvent)

    def test_loop_record_button_in_loop_mode_emits_record_toggle(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_LOOP_RECORD, value=127, channel=0), state
        )
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModeRecordToggleEvent)

    def test_loop_record_button_release_ignored_in_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_LOOP_RECORD, value=0, channel=0), state
        )
        self.assertEqual(events, [])

    def test_loop_playback_button_in_loop_mode_emits_playback_toggle(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_LOOP_PLAYBACK, value=127, channel=0), state
        )
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], main.LoopModePlaybackToggleEvent)

    def test_loop_playback_button_release_ignored_in_loop_mode(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        events = main.parse_events(
            msg('control_change', control=main.CC_LOOP_PLAYBACK, value=0, channel=0), state
        )
        self.assertEqual(events, [])

    def test_key_select_with_digits_in_loop_mode_emits_program_change(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        with contextlib.redirect_stdout(io.StringIO()):
            main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=127, channel=0), state)
            main.parse_events(msg('note_on', note=40, velocity=127, channel=state['ch_pads']), state)  # digit 1
            events = main.parse_events(msg('control_change', control=main.CC_KEY_SELECT, value=0, channel=0), state)
        self.assertTrue(any(isinstance(e, main.ProgramChangeEvent) for e in events))
        self.assertFalse(any(isinstance(e, main.LoopModePlaybackToggleEvent) for e in events))

    def test_note_on_buffered_during_recording_and_still_plays(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time()

        events = main.parse_events(
            msg('note_on', note=60, velocity=100, channel=state['ch_keys']), state
        )

        # NoteOnEvent still emitted
        self.assertTrue(any(isinstance(e, main.NoteOnEvent) for e in events))
        # Event buffered
        self.assertEqual(len(state['loop_mode_record_buffer']), 1)
        buf_entry = state['loop_mode_record_buffer'][0]
        self.assertEqual(buf_entry[1], 'note_on')
        self.assertEqual(buf_entry[2], state['ch_keys'])
        self.assertEqual(buf_entry[3], 60)
        self.assertEqual(buf_entry[4], 100)

    def test_note_off_buffered_during_recording(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time()

        events = main.parse_events(
            msg('note_off', note=60, channel=state['ch_keys']), state
        )

        self.assertTrue(any(isinstance(e, main.NoteOffEvent) for e in events))
        self.assertEqual(len(state['loop_mode_record_buffer']), 1)
        buf_entry = state['loop_mode_record_buffer'][0]
        self.assertEqual(buf_entry[1], 'note_off')
        self.assertEqual(buf_entry[3], 60)

    def test_pad_notes_also_buffered_during_recording(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time()

        main.parse_events(
            msg('note_on', note=36, velocity=100, channel=state['ch_pads']), state
        )

        self.assertEqual(len(state['loop_mode_record_buffer']), 1)
        self.assertEqual(state['loop_mode_record_buffer'][0][2], state['ch_pads'])

    def test_notes_not_buffered_when_not_recording(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = False

        main.parse_events(
            msg('note_on', note=60, velocity=100, channel=state['ch_keys']), state
        )

        self.assertEqual(state['loop_mode_record_buffer'], [])


class LoopModeHandleEventTests(unittest.TestCase):
    def _make_fake_synth(self):
        class FakeSynth:
            def noteon(self, *a): pass
            def noteoff(self, *a): pass
            def program_select(self, *a): return 0
            def cc(self, *a): pass
        return FakeSynth()

    def _call_handle(self, event, state):
        with contextlib.redirect_stdout(io.StringIO()):
            main.handle_event(
                event,
                fs=self._make_fake_synth(),
                ch_keys=0, ch_pads=9, sfid=1,
                state=state,
            )

    def test_enter_loop_mode_sets_active_and_clears_state(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        # Simulate prior loop state that should be cleaned up
        state['loop_mode_tracks'][0] = object()
        state['loop_mode_current_track'] = 2
        state['loop_mode_recording'] = True
        state['loop_mode_playing'] = True

        spoken = []
        original_speak = main.speak
        main.speak = lambda text, wait=False: spoken.append(text)
        try:
            self._call_handle(main.EnterLoopModeEvent(), state)
        finally:
            main.speak = original_speak

        self.assertTrue(state['loop_mode_active'])
        self.assertTrue(all(t is None for t in state['loop_mode_tracks']))
        self.assertEqual(state['loop_mode_current_track'], 0)
        self.assertFalse(state['loop_mode_recording'])
        self.assertEqual(state['loop_mode_record_buffer'], [])
        self.assertFalse(state['loop_mode_playing'])
        self.assertIn('Loop Mode', spoken[0])

    def test_exit_loop_mode_clears_active_and_stops_playback(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_playing'] = True
        stop_ev = threading.Event()
        state['loop_mode_play_stop_events'][0] = stop_ev

        spoken = []
        original_speak = main.speak
        main.speak = lambda text, wait=False: spoken.append(text)
        try:
            self._call_handle(main.ExitLoopModeEvent(), state)
        finally:
            main.speak = original_speak

        self.assertFalse(state['loop_mode_active'])
        self.assertFalse(state['loop_mode_playing'])
        self.assertTrue(stop_ev.is_set())
        self.assertIn('Goodbye', spoken[0])

    def test_enter_loop_mode_stops_existing_playback_threads(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_playing'] = True
        stop_ev0 = threading.Event()
        stop_ev1 = threading.Event()
        state['loop_mode_play_stop_events'][0] = stop_ev0
        state['loop_mode_play_stop_events'][1] = stop_ev1

        original_speak = main.speak
        main.speak = lambda text, wait=False: None
        try:
            self._call_handle(main.EnterLoopModeEvent(), state)
        finally:
            main.speak = original_speak

        self.assertTrue(stop_ev0.is_set())
        self.assertTrue(stop_ev1.is_set())

    def test_track_right_advances_track(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_current_track'] = 0
        self._call_handle(main.LoopModeTrackRightEvent(), state)
        self.assertEqual(state['loop_mode_current_track'], 1)

    def test_track_right_wraps_at_end(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_current_track'] = 3  # last track (0-indexed, n=4)
        self._call_handle(main.LoopModeTrackRightEvent(), state)
        self.assertEqual(state['loop_mode_current_track'], 0)

    def test_track_left_decrements_track(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_current_track'] = 2
        self._call_handle(main.LoopModeTrackLeftEvent(), state)
        self.assertEqual(state['loop_mode_current_track'], 1)

    def test_track_left_wraps_at_start(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_current_track'] = 0
        self._call_handle(main.LoopModeTrackLeftEvent(), state)
        self.assertEqual(state['loop_mode_current_track'], 3)

    def test_record_toggle_starts_recording(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = False
        self._call_handle(main.LoopModeRecordToggleEvent(), state)
        self.assertTrue(state['loop_mode_recording'])
        self.assertEqual(state['loop_mode_record_buffer'], [])
        self.assertGreater(state['loop_mode_record_start'], 0.0)

    def test_record_toggle_stops_recording_and_saves_track_with_events(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time() - 1.0  # 1 second ago
        state['loop_mode_record_buffer'] = [
            (0.0,  'note_on',  0, 60, 100),
            (0.5,  'note_off', 0, 60, 0),
        ]
        self._call_handle(main.LoopModeRecordToggleEvent(), state)
        self.assertFalse(state['loop_mode_recording'])
        track = state['loop_mode_tracks'][0]
        self.assertIsNotNone(track)
        self.assertEqual(len(track.events), 2)
        self.assertGreater(track.duration, 0.9)

    def test_record_toggle_stops_recording_clears_track_on_empty_buffer(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time()
        state['loop_mode_record_buffer'] = []
        state['loop_mode_tracks'][0] = object()  # existing content
        self._call_handle(main.LoopModeRecordToggleEvent(), state)
        self.assertFalse(state['loop_mode_recording'])
        self.assertIsNone(state['loop_mode_tracks'][0])

    def test_record_toggle_stops_current_track_playback(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = False
        state['loop_mode_playing'] = True
        stop_ev = threading.Event()
        state['loop_mode_play_stop_events'][0] = stop_ev
        self._call_handle(main.LoopModeRecordToggleEvent(), state)
        self.assertTrue(stop_ev.is_set())
        self.assertIsNone(state['loop_mode_play_stop_events'][0])

    def test_record_toggle_restarts_track_playback_if_playing_and_track_has_content(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_recording'] = True
        state['loop_mode_record_start'] = time.time() - 1.0
        state['loop_mode_record_buffer'] = [
            (0.0, 'note_on', 0, 60, 100),
            (0.5, 'note_off', 0, 60, 0),
        ]
        state['loop_mode_playing'] = True  # global playback is ON

        threads_started = []
        original_thread = main.threading.Thread

        class FakeThread:
            def __init__(self, target=None, args=(), daemon=False):
                self.target = target
                self.daemon = daemon
                threads_started.append(self)

            def start(self):
                pass

        main.threading.Thread = FakeThread
        try:
            self._call_handle(main.LoopModeRecordToggleEvent(), state)
        finally:
            main.threading.Thread = original_thread

        self.assertTrue(len(threads_started) > 0)
        self.assertIsNotNone(state['loop_mode_play_stop_events'][0])

    def test_playback_toggle_starts_playback_for_tracks_with_content(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_playing'] = False
        state['loop_mode_tracks'][0] = loop_mode_module.LoopTrack(
            events=[(0.0, 'note_on', 0, 60, 100)],
            duration=1.0,
        )
        state['loop_mode_tracks'][1] = None

        threads_started = []
        original_thread = main.threading.Thread

        class FakeThread:
            def __init__(self, target=None, args=(), daemon=False):
                self.target = target
                self.daemon = daemon
                threads_started.append(self)

            def start(self):
                pass

        main.threading.Thread = FakeThread
        try:
            self._call_handle(main.LoopModePlaybackToggleEvent(), state)
        finally:
            main.threading.Thread = original_thread

        self.assertTrue(state['loop_mode_playing'])
        self.assertEqual(len(threads_started), 1)
        self.assertIsNotNone(state['loop_mode_play_stop_events'][0])
        self.assertIsNone(state['loop_mode_play_stop_events'][1])

    def test_playback_toggle_stops_all_tracks(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['loop_mode_active'] = True
        state['loop_mode_playing'] = True
        stop_ev0 = threading.Event()
        stop_ev1 = threading.Event()
        state['loop_mode_play_stop_events'][0] = stop_ev0
        state['loop_mode_play_stop_events'][1] = stop_ev1
        self._call_handle(main.LoopModePlaybackToggleEvent(), state)
        self.assertFalse(state['loop_mode_playing'])
        self.assertTrue(stop_ev0.is_set())
        self.assertTrue(stop_ev1.is_set())
        self.assertTrue(all(e is None for e in state['loop_mode_play_stop_events']))


if __name__ == '__main__':
    unittest.main()
