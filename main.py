"""
main.py — LaunchKey Mini MK2 synthesizer.
Loads config.toml for MIDI routing and sound configuration.
"""
import threading
import tomllib
import pathlib
import mido
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
CONFIG_PATH = pathlib.Path(__file__).parent / 'config.toml'

# Mixer: list of [samples, position] — written by main thread, read by audio callback
_active = []
_lock   = threading.Lock()


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


# ---------------------------------------------------------------------------
# TR-808-style inharmonic metal oscillator (6 sine waves at non-integer ratios)
# Used as the base for hi-hats and cymbals.
# ---------------------------------------------------------------------------

_METAL_RATIOS = [2.0, 3.01, 3.67, 4.33, 4.89, 5.56]


def _metal_osc(t, base_freq):
    sines = [np.sin(2 * np.pi * base_freq * r * t) for r in _METAL_RATIOS]
    return sum(sines) / len(sines)


# ---------------------------------------------------------------------------
# Individual GM drum voices — each note has its own unique synthesis
# ---------------------------------------------------------------------------

def _drum_35(volume):
    """Acoustic Bass Drum: deep boom, slow 120→45 Hz sweep, two-stage decay."""
    dur = 0.6
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 120 * np.exp(-18 * t) + 45
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.25 * np.sin(2 * phase)
    tone /= 1.25
    noise = np.random.default_rng().standard_normal(n) * 0.04
    wave  = tone * 0.96 + noise
    env   = 0.35 * np.exp(-4 * t) + 0.65 * np.exp(-1.8 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_36(volume):
    """Bass Drum 1 (TR-808 style): tight punch, fast 150→50 Hz sweep, no noise."""
    dur = 0.45
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 150 * np.exp(-40 * t) + 50
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    wave  = np.sin(phase)
    env   = np.exp(-9 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_37(volume):
    """Side Stick: sharp high-freq click, diff-filtered noise + 1800 Hz ping, no body."""
    dur = 0.10
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    noise    = np.random.default_rng().standard_normal(n)
    noise_hp = np.diff(noise, prepend=noise[0])          # 1st-order diff ≈ highpass
    click    = np.sin(2 * np.pi * 1800 * t) * np.exp(-160 * t)
    wave     = noise_hp * 0.55 + click * 0.45
    env      = np.exp(-45 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_38(volume):
    """Acoustic Snare: warm 170 Hz body + organic wire noise, 55/45 tone/noise."""
    dur = 0.22
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    tone  = np.sin(2 * np.pi * 170 * t) + 0.4 * np.sin(2 * np.pi * 285 * t)
    tone /= 1.4
    noise = np.random.default_rng().standard_normal(n)
    wave  = tone * 0.55 + noise * 0.45
    env   = np.exp(-18 * t)
    atk   = int(0.003 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_39(volume):
    """Hand Clap: 4 staggered noise bursts (0, 8, 15, 22 ms) with diff-filter brightness."""
    dur  = 0.25
    n    = int(SAMPLE_RATE * dur)
    t    = np.linspace(0, dur, n, False)
    rng  = np.random.default_rng()
    wave = np.zeros(n)
    for i, off_ms in enumerate([0, 8, 15, 22]):
        off   = int(off_ms / 1000 * SAMPLE_RATE)
        seg   = rng.standard_normal(n - off)
        seg   = np.diff(seg, prepend=seg[0])
        seg_t = t[:n - off]
        wave[off:] += seg * np.exp(-85 * seg_t) * (0.75 ** i)
    env = np.exp(-11 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_40(volume):
    """Electric Snare: brighter 200 Hz, diff-filtered noise dominant (28/72), snappier."""
    dur = 0.18
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    tone    = np.sin(2 * np.pi * 200 * t) + 0.3 * np.sin(2 * np.pi * 400 * t)
    tone   /= 1.3
    noise   = np.random.default_rng().standard_normal(n)
    noise_b = np.diff(noise, prepend=noise[0])
    wave    = tone * 0.28 + noise_b * 0.72
    env     = np.exp(-28 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_41(volume):
    """Low Floor Tom: ~70 Hz, long deep rumble, two-harmonic body, 380 ms."""
    dur = 0.38
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 90 * np.exp(-12 * t) + 68
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.15 * np.sin(2 * phase)
    tone /= 1.15
    noise = np.random.default_rng().standard_normal(n) * 0.07
    wave  = tone * 0.93 + noise
    env   = np.exp(-10 * t)
    atk   = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_42(volume):
    """Closed Hi-Hat: 6-osc TR-808 metal @ 449 Hz, 55 ms sharp decay."""
    dur = 0.055
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    metal = _metal_osc(t, 449)
    noise = np.random.default_rng().standard_normal(n)
    wave  = metal * 0.65 + noise * 0.35
    env   = np.exp(-85 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_43(volume):
    """High Floor Tom: ~105 Hz, 320 ms, slightly shorter and brighter than low floor."""
    dur = 0.32
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 130 * np.exp(-13 * t) + 100
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.12 * np.sin(2 * phase)
    tone /= 1.12
    noise = np.random.default_rng().standard_normal(n) * 0.07
    wave  = tone * 0.93 + noise
    env   = np.exp(-11 * t)
    atk   = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_44(volume):
    """Pedal Hi-Hat: darker (380 Hz base), shorter 40 ms, softer than closed."""
    dur = 0.040
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    metal = _metal_osc(t, 380)
    noise = np.random.default_rng().standard_normal(n)
    wave  = metal * 0.5 + noise * 0.5
    env   = np.exp(-110 * t)
    return (wave * env * volume * 0.75).astype(np.float32)


def _drum_45(volume):
    """Low Tom: ~110 Hz, 300 ms."""
    dur = 0.30
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 140 * np.exp(-14 * t) + 108
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.12 * np.sin(2 * phase)
    tone /= 1.12
    noise = np.random.default_rng().standard_normal(n) * 0.08
    wave  = tone * 0.92 + noise
    env   = np.exp(-12 * t)
    atk   = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_46(volume):
    """Open Hi-Hat: same 6-osc metal source as closed, long 480 ms shimmer."""
    dur = 0.48
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    metal = _metal_osc(t, 449)
    noise = np.random.default_rng().standard_normal(n)
    wave  = metal * 0.65 + noise * 0.35
    env   = np.exp(-7 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_47(volume):
    """Low-Mid Tom: ~138 Hz, 280 ms."""
    dur = 0.28
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 165 * np.exp(-15 * t) + 135
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.10 * np.sin(2 * phase)
    tone /= 1.10
    noise = np.random.default_rng().standard_normal(n) * 0.08
    wave  = tone * 0.92 + noise
    env   = np.exp(-13 * t)
    atk   = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_48(volume):
    """Hi-Mid Tom: ~165 Hz, 260 ms."""
    dur = 0.26
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 195 * np.exp(-16 * t) + 160
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.10 * np.sin(2 * phase)
    tone /= 1.10
    noise = np.random.default_rng().standard_normal(n) * 0.08
    wave  = tone * 0.92 + noise
    env   = np.exp(-14 * t)
    atk   = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_49(volume):
    """Crash Cymbal 1: bright inharmonic wash (600 Hz × 7 ratios), 1.5 s decay."""
    dur = 1.5
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    ratios = [1.0, 2.14, 3.43, 4.21, 5.07, 6.82, 8.11]
    metal  = sum(np.sin(2 * np.pi * 600 * r * t) for r in ratios) / len(ratios)
    noise  = np.random.default_rng().standard_normal(n)
    wave   = metal * 0.45 + noise * 0.55
    env    = np.exp(-3.2 * t)
    atk    = int(0.003 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_50(volume):
    """High Tom: ~205 Hz, 220 ms, shortest tom."""
    dur = 0.22
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    freq  = 240 * np.exp(-18 * t) + 200
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    tone  = np.sin(phase) + 0.08 * np.sin(2 * phase)
    tone /= 1.08
    noise = np.random.default_rng().standard_normal(n) * 0.09
    wave  = tone * 0.91 + noise
    env   = np.exp(-16 * t)
    atk   = int(0.001 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_51(volume):
    """Ride Cymbal 1: clear bell ping (3150 Hz) + 6-osc shimmer, 1.2 s sustain."""
    dur = 1.2
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    bell  = np.sin(2 * np.pi * 3150 * t) + 0.5 * np.sin(2 * np.pi * 6300 * t)
    bell /= 1.5
    metal = _metal_osc(t, 300)
    noise = np.random.default_rng().standard_normal(n)
    wave  = bell * 0.50 + metal * 0.30 + noise * 0.20
    env   = np.exp(-3.8 * t)
    return (wave * env * volume).astype(np.float32)


def _drum_52(volume):
    """Chinese Cymbal: trashy detuned partials (420 Hz × 6 ratios) + 8 Hz warble, 0.9 s."""
    dur = 0.9
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    ratios = [1.0, 2.33, 3.58, 4.72, 5.44, 7.15]
    metal  = sum(np.sin(2 * np.pi * 420 * r * t) for r in ratios) / len(ratios)
    lfo    = 1.0 + 0.15 * np.sin(2 * np.pi * 8 * t)
    noise  = np.random.default_rng().standard_normal(n)
    wave   = metal * lfo * 0.6 + noise * 0.4
    env    = np.exp(-5.5 * t)
    atk    = int(0.002 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_55(volume):
    """Splash Cymbal: small and sharp, high 780 Hz base, quick 0.4 s tail."""
    dur = 0.40
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    ratios = [1.0, 2.07, 3.21, 4.45, 5.63, 7.02]
    metal  = sum(np.sin(2 * np.pi * 780 * r * t) for r in ratios) / len(ratios)
    noise  = np.random.default_rng().standard_normal(n)
    wave   = metal * 0.55 + noise * 0.45
    env    = np.exp(-9 * t)
    atk    = int(0.001 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_57(volume):
    """Crash Cymbal 2: darker (520 Hz base), denser noise blend, longer 1.8 s tail."""
    dur = 1.8
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    ratios = [1.0, 2.28, 3.51, 4.63, 5.84, 7.39, 9.02]
    metal  = sum(np.sin(2 * np.pi * 520 * r * t) for r in ratios) / len(ratios)
    noise  = np.random.default_rng().standard_normal(n)
    wave   = metal * 0.40 + noise * 0.60
    env    = np.exp(-2.8 * t)
    atk    = int(0.003 * SAMPLE_RATE)
    env[:atk] = np.linspace(0, 1, atk)
    return (wave * env * volume).astype(np.float32)


def _drum_59(volume):
    """Ride Cymbal 2: warmer dark bell (2500 Hz) + lower 240 Hz metal shimmer, 1.0 s."""
    dur = 1.0
    n   = int(SAMPLE_RATE * dur)
    t   = np.linspace(0, dur, n, False)
    bell  = np.sin(2 * np.pi * 2500 * t) + 0.4 * np.sin(2 * np.pi * 4800 * t)
    bell /= 1.4
    metal = _metal_osc(t, 240)
    noise = np.random.default_rng().standard_normal(n)
    wave  = bell * 0.45 + metal * 0.35 + noise * 0.20
    env   = np.exp(-4.5 * t)
    return (wave * env * volume).astype(np.float32)


# GM note → synthesis function (one unique voice per note)
_DRUM_VOICES = {
    35: _drum_35,   # Acoustic Bass Drum
    36: _drum_36,   # Bass Drum 1 (TR-808 style)
    37: _drum_37,   # Side Stick
    38: _drum_38,   # Acoustic Snare
    39: _drum_39,   # Hand Clap
    40: _drum_40,   # Electric Snare
    41: _drum_41,   # Low Floor Tom
    42: _drum_42,   # Closed Hi-Hat
    43: _drum_43,   # High Floor Tom
    44: _drum_44,   # Pedal Hi-Hat
    45: _drum_45,   # Low Tom
    46: _drum_46,   # Open Hi-Hat
    47: _drum_47,   # Low-Mid Tom
    48: _drum_48,   # Hi-Mid Tom
    49: _drum_49,   # Crash Cymbal 1
    50: _drum_50,   # High Tom
    51: _drum_51,   # Ride Cymbal 1
    52: _drum_52,   # Chinese Cymbal
    55: _drum_55,   # Splash Cymbal
    57: _drum_57,   # Crash Cymbal 2
    59: _drum_59,   # Ride Cymbal 2
}


def make_drums(note, velocity, cfg):
    volume = velocity_to_volume(velocity, cfg.get('volume', 0.6))
    fn     = _DRUM_VOICES.get(note, _drum_38)   # fallback: acoustic snare
    return fn(volume)


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

def dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg):
    if msg.type != 'note_on' or msg.velocity == 0:
        return
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
                    dispatch(msg, ch_keys, ch_pads, keys_sound, pads_sound, sounds_cfg)
    except KeyboardInterrupt:
        print("Goodbye!")


if __name__ == '__main__':
    main()
