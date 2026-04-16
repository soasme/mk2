import contextlib
import io
import unittest
from types import SimpleNamespace

import main
from modes import chord_learning


def msg(msg_type, **kwargs):
    return SimpleNamespace(type=msg_type, **kwargs)


class ParseEventsTests(unittest.TestCase):
    def test_scene_button_cc_mappings(self):
        self.assertEqual(main.CC_PAD_SELECT, 104)
        self.assertEqual(main.CC_KEY_SELECT, 105)

    def test_key_select_press_prints_latched_target_channel(self):
        state = main.make_input_state(ch_keys=0, ch_pads=9)
        state['current_keys_channel'] = 1

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


if __name__ == '__main__':
    unittest.main()
