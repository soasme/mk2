"""Unit tests for loop play mode — SequencerState, LED helpers, dispatch."""
import threading
from unittest.mock import MagicMock, patch, call

import mido
import pytest

import main as m


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
