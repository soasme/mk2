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
