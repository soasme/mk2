"""
main.py — listens to LaunchKey Mini MK2 and plays sounds.

Keys  (channel 9):  piano-style sine tone at the correct pitch
Pads  (channel 10): percussive noise burst tuned to the pad's note
"""
import threading
import mido
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
MIDI_PORT   = 'Launchkey Mini LK Mini MIDI'

CH_KEYS = 0   # channel 1  (0-indexed) — in InControl mode
CH_PADS = 9   # channel 10 (0-indexed)

# Mixer: list of [samples, position] — written by main thread, read by audio callback
_active = []
_lock   = threading.Lock()


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def velocity_to_volume(velocity, scale=0.5):
    # Square-root curve: audible even at low velocities (keys often send 1–10)
    return (velocity / 127) ** 0.5 * scale


def make_key(note, velocity):
    freq     = midi_to_freq(note)
    volume   = velocity_to_volume(velocity, scale=0.5)
    n        = int(SAMPLE_RATE * 1.2)
    t        = np.linspace(0, 1.2, n, False)
    wave     = np.sin(2 * np.pi * freq * t)
    attack   = int(0.01 * SAMPLE_RATE)
    release  = int(0.40 * SAMPLE_RATE)
    env      = np.ones(n)
    env[:attack]   = np.linspace(0, 1, attack)
    env[-release:] = np.linspace(1, 0, release)
    return (wave * env * volume).astype(np.float32)


def make_pad(note, velocity):
    freq    = midi_to_freq(note)
    volume  = velocity_to_volume(velocity, scale=0.6)
    n       = int(SAMPLE_RATE * 0.25)
    t       = np.linspace(0, 0.25, n, False)
    tone    = np.sin(2 * np.pi * freq * t)
    noise   = np.random.default_rng().standard_normal(n)
    wave    = tone * 0.4 + noise * 0.6
    decay   = np.exp(-18 * t)
    return (wave * decay * volume).astype(np.float32)


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


def dispatch(msg):
    if msg.type != 'note_on' or msg.velocity == 0:
        return
    if msg.channel == CH_KEYS:
        samples = make_key(msg.note, msg.velocity)
    elif msg.channel == CH_PADS:
        samples = make_pad(msg.note, msg.velocity)
    else:
        return
    with _lock:
        _active.append([samples, 0])


def main():
    print(f"Listening on: {MIDI_PORT}")
    print("Keys → piano tone  |  Pads → drum hit  |  Ctrl-C to quit\n")

    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1,
                             dtype='float32', blocksize=512,
                             callback=audio_callback):
            with mido.open_input(MIDI_PORT) as inport:
                for msg in inport:
                    dispatch(msg)
    except KeyboardInterrupt:
        print("Goodbye!")


if __name__ == '__main__':
    main()
