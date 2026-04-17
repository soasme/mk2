"""
modes/loop_mode.py — Loop Mode track storage and playback.

Each LoopTrack stores a list of timestamped MIDI events and a total duration.
play_track_loop() runs in a daemon thread and loops the track until stop_event is set.
"""
import time
from dataclasses import dataclass, field


@dataclass
class LoopTrack:
    events: list  # [(time_offset, event_type, channel, note, velocity), ...]
    duration: float  # total loop duration in seconds


def play_track_loop(track, fs, stop_event):
    """Loop track events forever until stop_event is set.

    Args:
        track: LoopTrack instance.
        fs: FluidSynth instance with noteon(ch, note, vel) and noteoff(ch, note).
        stop_event: threading.Event — set it to stop the loop.
    """
    while not stop_event.is_set():
        loop_start = time.monotonic()
        for time_offset, event_type, channel, note, velocity in track.events:
            target = loop_start + time_offset
            wait = target - time.monotonic()
            if wait > 0:
                if stop_event.wait(wait):
                    break
            if stop_event.is_set():
                break
            if event_type == 'note_on':
                fs.noteon(channel, note, velocity)
            elif event_type == 'note_off':
                fs.noteoff(channel, note)
        remaining = loop_start + track.duration - time.monotonic()
        if remaining > 0:
            stop_event.wait(remaining)
