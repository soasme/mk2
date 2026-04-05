"""
main.py — LaunchKey Mini MK2 synthesizer.
Loads config.toml for MIDI routing and sound configuration.
"""
import dataclasses
import threading
import tomllib
import pathlib
import mido
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
CONFIG_PATH = pathlib.Path(__file__).parent / 'config.toml'


@dataclasses.dataclass
class SequencerState:
    loop_mode:    bool      = False
    steps:        list[bool] = dataclasses.field(default_factory=lambda: [False] * 16)
    current_step: int       = 0
    loop_note:    int       = 60


# Sequencer globals — shared between main thread and sequencer thread
seq       = SequencerState()
_stop_seq = threading.Event()
_stop_seq.set()   # set = sequencer not running

# Mixer: list of [samples, position] — written by main thread, read by audio callback
_active = []
_lock   = threading.Lock()


# ---------------------------------------------------------------------------
# LED helpers
# ---------------------------------------------------------------------------

def set_pad_leds(outport, steps, current_step, pad_notes, loop_cfg):
    """Send a note_on to the InControl port for every pad to update colours."""
    assert len(steps) >= len(pad_notes), (
        f"steps has {len(steps)} entries but pad_notes has {len(pad_notes)}"
    )
    playhead_vel = loop_cfg.get('led_playhead', 12)
    active_vel   = loop_cfg.get('led_active',   15)
    off_vel      = loop_cfg.get('led_off',        0)
    for i, note in enumerate(pad_notes):
        if i == current_step:
            vel = playhead_vel
        elif steps[i]:
            vel = active_vel
        else:
            vel = off_vel
        outport.send(mido.Message('note_on', channel=0, note=note, velocity=vel))


def clear_pad_leds(outport, pad_notes):
    """Turn off all pad LEDs."""
    for note in pad_notes:
        outport.send(mido.Message('note_on', channel=0, note=note, velocity=0))


def sequencer_loop(seq, outport, loop_cfg, pads_sound, sounds_cfg):
    """Advance the step sequencer at 1/16-note intervals.

    Runs in a daemon thread. Exits when _stop_seq is set.
    """
    bpm      = loop_cfg.get('bpm', 120)
    interval = 60.0 / (bpm * 4)      # seconds per 1/16 note
    pad_notes = loop_cfg.get('pad_notes', [])

    while not _stop_seq.wait(timeout=interval):
        with _lock:
            step   = seq.current_step
            active = seq.steps[step]
            note   = seq.loop_note
            steps_snapshot = list(seq.steps)

        if active:
            samples = make_sound(note, 100, pads_sound, sounds_cfg)
            if samples is not None:
                with _lock:
                    _active.append([samples, 0])

        set_pad_leds(outport, steps_snapshot, step, pad_notes, loop_cfg)

        with _lock:
            seq.current_step = (step + 1) % 16


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, 'rb') as f:
        return tomllib.load(f)


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def velocity_to_volume(velocity, scale):
    # Square-root curve: audible even at low velocities
    return (velocity / 127) ** 0.5 * scale


# ---------------------------------------------------------------------------
# Sound generators
# ---------------------------------------------------------------------------

def make_piano(note, velocity, cfg):
    freq       = midi_to_freq(note)
    volume     = velocity_to_volume(velocity, cfg.get('volume', 0.4))
    brightness = 0.3 + 0.7 * (velocity / 127)

    decay_rate = 1.0 + max(0, note - 48) * 0.04
    duration   = max(0.8, 3.0 / decay_rate)
    n          = int(SAMPLE_RATE * duration)
    t          = np.linspace(0, duration, n, False)

    base = cfg.get('harmonics', [1.0, 0.50, 0.25, 0.12, 0.06, 0.03])
    amps = [base[0]] + [a * brightness for a in base[1:]]
    wave = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(amps))
    wave /= sum(amps)

    df   = cfg.get('decay_fast', 6.0)
    ds   = cfg.get('decay_slow', 1.2)
    env  = 0.4 * np.exp(-decay_rate * df * t) + 0.6 * np.exp(-decay_rate * ds * t)

    atk = int(cfg.get('attack_ms', 5) / 1000 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, env[atk], atk)

    return (wave * env * volume).astype(np.float32)


def make_guitar(note, velocity, cfg):
    """Karplus-Strong plucked string synthesis."""
    freq     = midi_to_freq(note)
    volume   = velocity_to_volume(velocity, cfg.get('volume', 0.5))
    duration = cfg.get('duration', 2.5)
    decay    = cfg.get('decay', 0.996)
    n        = int(SAMPLE_RATE * duration)

    buf_size = max(1, int(SAMPLE_RATE / freq))
    buf      = np.random.uniform(-1.0, 1.0, buf_size).astype(np.float32)
    output   = np.zeros(n, dtype=np.float32)

    for i in range(n):
        idx          = i % buf_size
        next_idx     = (i + 1) % buf_size
        output[i]    = buf[idx]
        buf[idx]     = decay * 0.5 * (buf[idx] + buf[next_idx])

    fade = int(0.05 * SAMPLE_RATE)
    output[-fade:] *= np.linspace(1, 0, fade)

    return (output * volume).astype(np.float32)


def make_organ(note, velocity, cfg):
    freq     = midi_to_freq(note)
    volume   = velocity_to_volume(velocity, cfg.get('volume', 0.3))
    duration = cfg.get('duration', 1.5)
    n        = int(SAMPLE_RATE * duration)
    t        = np.linspace(0, duration, n, False)

    harmonics = cfg.get('harmonics', [1.0, 0.50, 0.33, 0.25, 0.20])
    wave      = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))
    wave     /= sum(harmonics)

    atk = int(cfg.get('attack_ms', 15) / 1000 * SAMPLE_RATE)
    rel = int(cfg.get('release_ms', 50) / 1000 * SAMPLE_RATE)
    env = np.ones(n)
    env[:atk]  = np.linspace(0, 1, atk)
    env[-rel:] = np.linspace(1, 0, rel)

    return (wave * env * volume).astype(np.float32)


def make_drums(note, velocity, cfg):
    freq     = midi_to_freq(note)
    volume   = velocity_to_volume(velocity, cfg.get('volume', 0.6))
    duration = cfg.get('duration', 0.25)
    n        = int(SAMPLE_RATE * duration)
    t        = np.linspace(0, duration, n, False)

    tone_mix = cfg.get('tone_mix', 0.4)
    tone     = np.sin(2 * np.pi * freq * t)
    noise    = np.random.default_rng().standard_normal(n)
    wave     = tone * tone_mix + noise * (1.0 - tone_mix)

    decay = np.exp(-cfg.get('decay_rate', 18.0) * t)

    return (wave * decay * volume).astype(np.float32)


def make_bells(note, velocity, cfg):
    freq     = midi_to_freq(note)
    volume   = velocity_to_volume(velocity, cfg.get('volume', 0.4))
    duration = cfg.get('duration', 2.5)
    n        = int(SAMPLE_RATE * duration)
    t        = np.linspace(0, duration, n, False)

    # Slightly inharmonic partials give bell character
    amps   = cfg.get('harmonics', [1.0, 0.25, 0.06])
    ratios = [1.0, 2.76, 5.40]
    wave   = sum(a * np.sin(2 * np.pi * freq * r * t) for a, r in zip(amps, ratios))
    wave  /= sum(amps)

    env     = np.exp(-cfg.get('decay_rate', 0.8) * t)
    atk     = int(cfg.get('attack_ms', 2) / 1000 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)

    return (wave * env * volume).astype(np.float32)


SOUND_MAKERS = {
    'piano':  make_piano,
    'guitar': make_guitar,
    'organ':  make_organ,
    'drums':  make_drums,
    'bells':  make_bells,
}


def make_sound(note, velocity, sound_name, sounds_cfg):
    cfg    = sounds_cfg.get(sound_name, {})
    stype  = cfg.get('type', sound_name)
    maker  = SOUND_MAKERS.get(stype)
    if maker is None:
        return None
    return maker(note, velocity, cfg)


# ---------------------------------------------------------------------------
# Audio mixer
# ---------------------------------------------------------------------------

def audio_callback(outdata, frames, time, status):
    result = np.zeros(frames, dtype=np.float32)
    with _lock:
        still_active = []
        for entry in _active:
            samples, pos = entry
            chunk = min(frames, len(samples) - pos)
            result[:chunk] += samples[pos:pos + chunk]
            if pos + chunk < len(samples):
                still_active.append([samples, pos + chunk])
        _active[:] = still_active
    np.clip(result, -1.0, 1.0, out=result)
    outdata[:] = result.reshape(-1, 1)


# ---------------------------------------------------------------------------
# MIDI dispatch
# ---------------------------------------------------------------------------

def dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg,
             seq, outport, loop_cfg):
    # -----------------------------------------------------------------------
    # Play button: CC 108 ch0 value=127 → toggle loop mode
    # -----------------------------------------------------------------------
    if msg.type == 'control_change' and msg.channel == 0 and msg.control == 108:
        if msg.value == 127:
            with _lock:
                seq.loop_mode = not seq.loop_mode
                entering = seq.loop_mode
                if entering:
                    seq.current_step = 0
            if entering:
                _stop_seq.clear()
                t = threading.Thread(
                    target=sequencer_loop,
                    args=(seq, outport, loop_cfg, pads_sound, sounds_cfg),
                    daemon=True,
                )
                t.start()
            else:
                _stop_seq.set()
                clear_pad_leds(outport, loop_cfg.get('pad_notes', []))
        return

    # -----------------------------------------------------------------------
    # Loop mode — pad toggles step; key sets note
    # -----------------------------------------------------------------------
    with _lock:
        in_loop = seq.loop_mode

    if in_loop:
        if msg.type != 'note_on' or msg.velocity == 0:
            return
        if msg.channel == ch_pads:
            pad_notes = loop_cfg.get('pad_notes', [])
            if msg.note in pad_notes:
                i = pad_notes.index(msg.note)
                with _lock:
                    seq.steps[i] = not seq.steps[i]
                    vel = (loop_cfg.get('led_active', 15)
                           if seq.steps[i]
                           else loop_cfg.get('led_off', 0))
                outport.send(mido.Message('note_on', channel=0,
                                          note=msg.note, velocity=vel))
        elif msg.channel == ch_keys:
            with _lock:
                seq.loop_note = msg.note
        return

    if msg.type != 'note_on' or msg.velocity == 0:
        return

    # -----------------------------------------------------------------------
    # Normal mode — play sound immediately
    # -----------------------------------------------------------------------
    if msg.channel == ch_keys:
        samples = make_sound(msg.note, msg.velocity, keys_sound, sounds_cfg)
    elif msg.channel == ch_pads:
        samples = make_sound(msg.note, msg.velocity, pads_sound, sounds_cfg)
    else:
        return
    if samples is not None:
        with _lock:
            _active.append([samples, 0])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cfg        = load_config()
    midi_cfg   = cfg.get('midi', {})
    track_cfg  = cfg.get('track', {})
    sounds_cfg = cfg.get('sounds', {})

    port        = midi_cfg.get('port', 'Launchkey Mini LK Mini MIDI')
    ch_keys     = midi_cfg.get('channel_keys', 0)
    ch_pads     = midi_cfg.get('channel_pads', 9)
    keys_sound  = track_cfg.get('keys', 'piano')
    pads_sound  = track_cfg.get('pads', 'drums')

    print(f"Listening on : {port}")
    print(f"Keys sound   : {keys_sound}")
    print(f"Pads sound   : {pads_sound}")
    print("Ctrl-C to quit\n")

    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1,
                             dtype='float32', blocksize=512,
                             callback=audio_callback):
            with mido.open_input(port) as inport:
                for msg in inport:
                    # outport and loop_cfg are wired in Task 8; NameError here until then
                    dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg,
                             seq, outport, loop_cfg)
    except KeyboardInterrupt:
        print("Goodbye!")


if __name__ == '__main__':
    main()
