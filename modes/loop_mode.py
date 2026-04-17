"""
modes/loop_mode.py — Loop Mode track storage and playback.

Each LoopTrack stores a list of timestamped MIDI events and a total duration.
play_track_loop() runs in a daemon thread and loops the track until stop_event is set.
"""
import time
from dataclasses import dataclass

AUTO_FIT_TOLERANCE = 0.10
FIRST_TRACK_QUANTIZE_SUBDIVISIONS = (2, 3, 4, 6, 8, 12, 16)
FIRST_TRACK_QUANTIZE_TOLERANCE = 0.12


@dataclass
class LoopTrack:
    events: list  # [(time_offset, event_type, channel, note, velocity), ...]
    duration: float  # total loop duration in seconds


def fit_track_to_reference(track, reference_duration, tolerance=AUTO_FIT_TOLERANCE):
    """Snap a track to the nearest integer multiple of the reference length.

    Returns the possibly adjusted track plus fit metadata, or ``None`` metadata
    when the duration is too far away to safely auto-fit.
    """
    if not track.events or reference_duration is None:
        return track, None
    if reference_duration <= 0 or track.duration <= 0:
        return track, None

    multiple = max(1, int(round(track.duration / reference_duration)))
    target_duration = reference_duration * multiple
    error_ratio = abs(track.duration - target_duration) / target_duration
    if error_ratio > tolerance:
        return track, None

    scale = target_duration / track.duration
    fitted = LoopTrack(
        events=[
            (time_offset * scale, event_type, channel, note, velocity)
            for time_offset, event_type, channel, note, velocity in track.events
        ],
        duration=target_duration,
    )
    return fitted, {
        'multiple': multiple,
        'source_duration': track.duration,
        'target_duration': target_duration,
        'error_ratio': error_ratio,
    }


def quantize_first_track(track,
                         subdivisions=FIRST_TRACK_QUANTIZE_SUBDIVISIONS,
                         tolerance=FIRST_TRACK_QUANTIZE_TOLERANCE):
    """Quantize a first-pass loop to a coarse beat grid derived from its length.

    The smallest subdivision count that explains all note-on offsets within the
    tolerance window wins. This biases toward musically simple grids such as
    halves, thirds, quarters, and eighths instead of overfitting finer grids.
    """
    if track.duration <= 0 or not track.events:
        return track, None

    note_on_offsets = sorted(
        {time_offset for time_offset, event_type, *_ in track.events if event_type == 'note_on'}
    )
    if len(note_on_offsets) < 2:
        return track, None

    chosen = None
    chosen_max_error = None
    for subdivision in subdivisions:
        step = track.duration / subdivision
        if step <= 0:
            continue
        errors = []
        for offset in note_on_offsets:
            snapped = round(offset / step) * step
            snapped = min(track.duration, max(0.0, snapped))
            errors.append(abs(offset - snapped))
        max_error = max(errors)
        if max_error <= tolerance * step:
            chosen = subdivision
            chosen_max_error = max_error
            break

    if chosen is None:
        return track, None

    step = track.duration / chosen
    quantized_events = []
    for index, (time_offset, event_type, channel, note, velocity) in enumerate(track.events):
        snapped = round(time_offset / step) * step
        snapped = min(track.duration, max(0.0, snapped))
        quantized_events.append((snapped, event_type, channel, note, velocity, index))

    # Stable ordering matters when multiple events collapse onto the same beat.
    quantized_events.sort(
        key=lambda event: (
            event[0],
            0 if event[1] == 'note_off' else 1,
            event[5],
        )
    )
    quantized_track = LoopTrack(
        events=[(offset, event_type, channel, note, velocity)
                for offset, event_type, channel, note, velocity, _ in quantized_events],
        duration=track.duration,
    )
    return quantized_track, {
        'subdivision': chosen,
        'max_error': chosen_max_error,
        'step': step,
    }


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
