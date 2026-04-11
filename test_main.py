import contextlib
import io
import unittest
from types import SimpleNamespace

import main


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


if __name__ == '__main__':
    unittest.main()
