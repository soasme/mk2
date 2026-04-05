"""Unit tests for loop play mode — SequencerState, LED helpers, dispatch."""
import threading
from unittest.mock import MagicMock, patch, call

import mido
import pytest

import main as m
from main import _lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockPort:
    """Records note_on messages sent to it."""
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def fresh_seq():
    """Return a new default SequencerState."""
    return m.SequencerState()


LOOP_CFG = {
    'bpm': 120,
    'pad_notes': [40, 41, 42, 43, 44, 45, 46, 47,
                  48, 49, 50, 51, 52, 53, 54, 55],
    'led_playhead': 12,
    'led_active':   15,
    'led_off':       0,
}

# ---------------------------------------------------------------------------
# SequencerState
# ---------------------------------------------------------------------------

def test_sequencer_state_defaults():
    seq = m.SequencerState()
    assert seq.loop_mode is False
    assert seq.steps == [False] * 16
    assert seq.current_step == 0
    assert seq.loop_note == 60

# ---------------------------------------------------------------------------
# set_pad_leds
# ---------------------------------------------------------------------------

def test_set_pad_leds_playhead_color():
    """Current step gets led_playhead velocity."""
    outport = MockPort()
    steps = [False] * 16
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    # note=40 is pad 0 (current_step), must get playhead velocity
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 12   # led_playhead


def test_set_pad_leds_active_color():
    """Active non-current step gets led_active velocity."""
    outport = MockPort()
    steps = [False] * 16
    steps[3] = True   # pad 3 is on, but current_step is 0
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    msg = next(msg for msg in outport.sent if msg.note == 43)  # pad 3
    assert msg.velocity == 15   # led_active


def test_set_pad_leds_inactive_color():
    """Inactive non-current step gets led_off velocity."""
    outport = MockPort()
    steps = [False] * 16
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    msg = next(msg for msg in outport.sent if msg.note == 47)  # pad 7, off
    assert msg.velocity == 0    # led_off


def test_set_pad_leds_sends_all_16():
    """Exactly 16 note_on messages are sent."""
    outport = MockPort()
    m.set_pad_leds(outport, [False] * 16, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    assert len(outport.sent) == 16


def test_clear_pad_leds_sends_velocity_zero():
    """clear_pad_leds sends velocity=0 for every pad."""
    outport = MockPort()
    m.clear_pad_leds(outport, LOOP_CFG['pad_notes'])
    assert len(outport.sent) == 16
    assert all(msg.velocity == 0 for msg in outport.sent)


def test_set_pad_leds_playhead_overrides_active():
    """When current_step is also an active step, playhead color wins."""
    outport = MockPort()
    steps = [False] * 16
    steps[0] = True  # pad 0 is both active and the current_step
    m.set_pad_leds(outport, steps, current_step=0,
                   pad_notes=LOOP_CFG['pad_notes'], loop_cfg=LOOP_CFG)
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 12  # led_playhead, not led_active


# ---------------------------------------------------------------------------
# dispatch — CC 108 (play button)
# ---------------------------------------------------------------------------

def _dispatch_cc(value, seq=None, outport=None):
    """Helper: send CC 108 through dispatch."""
    if seq is None:
        seq = fresh_seq()
    if outport is None:
        outport = MockPort()
    msg = mido.Message('control_change', channel=0, control=108, value=value)
    with patch('main.threading.Thread') as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        m.dispatch(msg, ch_keys=0, ch_pads=9,
                   keys_sound='piano', pads_sound='drums', sounds_cfg={},
                   seq=seq, outport=outport, loop_cfg=LOOP_CFG)
        return seq, outport, mock_thread_cls


def test_cc108_press_enters_loop_mode():
    seq, outport, mock_thread_cls = _dispatch_cc(value=127)
    assert seq.loop_mode is True
    assert seq.current_step == 0
    mock_thread_cls.return_value.start.assert_called_once()
    assert not m._stop_seq.is_set()  # event must be cleared so sequencer thread runs


def test_cc108_press_exits_loop_mode():
    seq = fresh_seq()
    seq.loop_mode = True
    _dispatch_cc(value=127, seq=seq)
    assert seq.loop_mode is False
    assert m._stop_seq.is_set()  # event must be set to signal thread to stop


def test_cc108_release_ignored():
    """Value=0 (button release) must not change loop_mode."""
    seq, _, _ = _dispatch_cc(value=0)
    assert seq.loop_mode is False


def test_cc108_exit_clears_leds():
    """Exiting loop mode sends velocity=0 for all 16 pads."""
    seq = fresh_seq()
    seq.loop_mode = True
    _, outport, _ = _dispatch_cc(value=127, seq=seq)
    assert len(outport.sent) == 16
    assert all(msg.velocity == 0 for msg in outport.sent)


# ---------------------------------------------------------------------------
# dispatch — pad press in loop mode
# ---------------------------------------------------------------------------

def _pad_press(note, seq=None, outport=None):
    """Helper: send a pad note_on while in loop mode."""
    if seq is None:
        seq = fresh_seq()
        seq.loop_mode = True
    if outport is None:
        outport = MockPort()
    msg = mido.Message('note_on', channel=9, note=note, velocity=100)
    m.dispatch(msg, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    return seq, outport


def test_pad_press_toggles_step_on():
    seq, _ = _pad_press(note=40)   # pad 0 (first in pad_notes)
    assert seq.steps[0] is True


def test_pad_press_toggles_step_off():
    seq, _ = _pad_press(note=40)   # on
    _pad_press(note=40, seq=seq)   # off
    assert seq.steps[0] is False


def test_pad_press_sends_orange_led_when_on():
    _, outport = _pad_press(note=40)
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 15      # led_active (orange)


def test_pad_press_sends_off_led_when_toggled_off():
    seq, outport = _pad_press(note=40)   # on
    outport.sent.clear()
    _pad_press(note=40, seq=seq, outport=outport)   # off
    msg = next(msg for msg in outport.sent if msg.note == 40)
    assert msg.velocity == 0       # led_off


def test_pad_press_in_loop_mode_does_not_play_audio():
    """No audio buffers should be added when toggling a step."""
    with _lock:
        m._active.clear()
    _pad_press(note=40)
    with _lock:
        assert m._active == []


def test_pad_press_unknown_note_ignored():
    """A pad note not in pad_notes list must not crash or change any step."""
    seq, _ = _pad_press(note=99)   # not in LOOP_CFG['pad_notes']
    assert seq.steps == [False] * 16


def test_pad_note_off_in_loop_mode_does_not_toggle():
    """note_off (velocity=0) in loop mode must not toggle the step."""
    seq = fresh_seq()
    seq.loop_mode = True
    outport = MockPort()
    # note_on turns step on
    msg_on = mido.Message('note_on', channel=9, note=40, velocity=100)
    m.dispatch(msg_on, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    assert seq.steps[0] is True
    # note_off must not toggle it back off
    msg_off = mido.Message('note_on', channel=9, note=40, velocity=0)
    m.dispatch(msg_off, ch_keys=0, ch_pads=9,
               keys_sound='piano', pads_sound='drums', sounds_cfg={},
               seq=seq, outport=outport, loop_cfg=LOOP_CFG)
    assert seq.steps[0] is True   # still on — note_off was ignored
