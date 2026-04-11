"""
main.py — LaunchKey Mini MK2 synthesizer.
Loads config.toml for MIDI routing and sound configuration.
Uses FluidSynth (via pyfluidsynth) and a SoundFont for audio synthesis.

Event flow:
  MIDI message + input state → app events → synth calls
"""
import os
import pathlib
import subprocess
import sys
import tomllib
from dataclasses import dataclass
import mido
import fluidsynth

DEBUG = os.environ.get('DEBUG') == '1'
SAY_INSTRUMENT = os.environ.get('SAY_INSTRUMENT') == '1'

# GM program names, 0-indexed (bank 0 melodic, bank 128 percussion)
GM_MELODIC = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavi",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bag Pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]

GM_PERCUSSION = [
    "Standard Kit", "Room Kit", "Power Kit", "Electronic Kit",
    "TR-808 Kit", "Jazz Kit", "Brush Kit", "Orchestra Kit", "Sound FX Kit",
]


def gm_name(bank, program):
    """Return a human-readable GM instrument name for bank + program (0-indexed)."""
    if bank == 128:
        return GM_PERCUSSION[program] if program < len(GM_PERCUSSION) else f"Percussion {program}"
    if bank == 0 and program < len(GM_MELODIC):
        return GM_MELODIC[program]
    return f"Bank {bank} Program {program + 1}"

CONFIG_PATH = pathlib.Path(__file__).parent / 'config.toml'

CC_PAD_SELECT = 108  # First play button
CC_KEY_SELECT = 109  # Second play button

# Basic-mode note numbers for pads 1-10, mapped to digit (pad 10 → 0)
PAD_NOTE_TO_DIGIT = {
    40: 1, 41: 2, 42: 3, 43: 4,  # Pads 1-4
    48: 5, 49: 6, 50: 7, 51: 8,  # Pads 5-8
    36: 9, 37: 0,                 # Pads 9-10
}


# ---------------------------------------------------------------------------
# App events
# ---------------------------------------------------------------------------

@dataclass
class NoteOnEvent:
    channel: int
    note: int
    velocity: int

@dataclass
class NoteOffEvent:
    channel: int
    note: int

@dataclass
class PitchBendEvent:
    channel: int
    pitch: int

@dataclass
class CCEvent:
    channel: int
    control: int
    value: int

@dataclass
class PercussionChangeEvent:
    pads_program: int  # 0-indexed, maps to GM_PERCUSSION

@dataclass
class ProgramChangeEvent:
    keys_bank: int
    keys_program: int  # 0-indexed


# ---------------------------------------------------------------------------
# Input state (mutated by parse_events)
# ---------------------------------------------------------------------------

def make_input_state():
    return {
        'key_select_active': False,
        'key_select_digits': [],
        'key_select_captured': set(),
        'pad_select_active': False,
        'pad_select_program': None,   # digit 1-9 pressed during pad select
        'pad_select_captured': set(),
    }


# ---------------------------------------------------------------------------
# MIDI → app events
# ---------------------------------------------------------------------------

def parse_events(msg, state):
    """Convert one MIDI message (plus mutable input state) into app events."""
    events = []

    if msg.type == 'note_on':
        digit = PAD_NOTE_TO_DIGIT.get(msg.note)
        if state['pad_select_active'] and digit and 1 <= digit <= 9:
            state['pad_select_program'] = digit - 1  # last pad wins
            state['pad_select_captured'].add(msg.note)
        elif state['key_select_active'] and digit is not None:
            state['key_select_digits'].append(digit)
            state['key_select_captured'].add(msg.note)
        else:
            events.append(NoteOnEvent(msg.channel, msg.note, msg.velocity))

    elif msg.type == 'note_off':
        if msg.note in state['pad_select_captured']:
            state['pad_select_captured'].discard(msg.note)
        elif msg.note in state['key_select_captured']:
            state['key_select_captured'].discard(msg.note)
        else:
            events.append(NoteOffEvent(msg.channel, msg.note))

    elif msg.type == 'control_change':
        if msg.control == CC_PAD_SELECT:
            if msg.value == 127:
                state['pad_select_active'] = True
                state['pad_select_program'] = None
                state['pad_select_captured'] = set()
                print("PadSelect Button is pressed")
            else:
                state['pad_select_active'] = False
                print("PadSelect Button is released")
                if state['pad_select_program'] is not None:
                    events.append(PercussionChangeEvent(pads_program=state['pad_select_program']))

        elif msg.control == CC_KEY_SELECT:
            if msg.value == 127:
                state['key_select_active'] = True
                state['key_select_digits'] = []
                state['key_select_captured'] = set()
                print("KeySelect Button is pressed")
            else:
                state['key_select_active'] = False
                print("KeySelect Button is released")
                digits = state['key_select_digits']
                if len(digits) >= 2:
                    bank = digits[-1]
                    program_1indexed = int(''.join(str(d) for d in digits[:-1]))
                    events.append(ProgramChangeEvent(
                        keys_bank=bank,
                        keys_program=program_1indexed - 1,
                    ))
        else:
            events.append(CCEvent(msg.channel, msg.control, msg.value))

    elif msg.type == 'pitchwheel':
        events.append(PitchBendEvent(msg.channel, msg.pitch))

    return events


# ---------------------------------------------------------------------------
# App events → synth
# ---------------------------------------------------------------------------

def speak(text):
    if not SAY_INSTRUMENT:
        return
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['say', text])
        else:
            subprocess.Popen(['espeak', text])
    except Exception as e:
        print(f"Warning: TTS failed: {e}")


def program_select_with_fallback(fs, channel, sfid, bank, program):
    """Select program; if the preset doesn't exist, fall back to bank 0."""
    if fs.program_select(channel, sfid, bank, program) == -1:
        fs.program_select(channel, sfid, 0, program)
        return 0
    return bank


def handle_event(event, fs, ch_keys, ch_pads, sfid):
    if isinstance(event, NoteOnEvent):
        if DEBUG:
            print(f"note_on  ch={event.channel} note={event.note} vel={event.velocity}")
        fs.noteon(event.channel, event.note, event.velocity)
    elif isinstance(event, NoteOffEvent):
        if DEBUG:
            print(f"note_off ch={event.channel} note={event.note}")
        fs.noteoff(event.channel, event.note)
    elif isinstance(event, PitchBendEvent):
        fs.pitch_bend(event.channel, event.pitch)
    elif isinstance(event, CCEvent):
        fs.cc(event.channel, event.control, event.value)
    elif isinstance(event, PercussionChangeEvent):
        actual_bank = program_select_with_fallback(fs, ch_pads, sfid, 128, event.pads_program)
        name = gm_name(actual_bank, event.pads_program)
        if actual_bank != 128:
            print(f"Percussion: program={event.pads_program + 1} name={name} (fallback to bank {actual_bank})")
        else:
            print(f"Percussion: program={event.pads_program + 1} name={name}")
        speak(name)
    elif isinstance(event, ProgramChangeEvent):
        actual_bank = program_select_with_fallback(fs, ch_keys, sfid, event.keys_bank, event.keys_program)
        name = gm_name(actual_bank, event.keys_program)
        if actual_bank != event.keys_bank:
            print(f"Program: bank={actual_bank} program={event.keys_program + 1} name={name} (fallback to bank {actual_bank})")
        else:
            print(f"Program: bank={event.keys_bank} program={event.keys_program + 1} name={name}")
        speak(name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, 'rb') as f:
        return tomllib.load(f)


def main():
    cfg        = load_config()
    midi_cfg   = cfg.get('midi', {})
    synth_cfg  = cfg.get('synth', {})

    port    = midi_cfg.get('port', 'Launchkey Mini LK Mini MIDI')
    ch_keys = midi_cfg.get('channel_keys', 0)
    ch_pads = midi_cfg.get('channel_pads', 9)

    sf_path = pathlib.Path(synth_cfg.get('soundfont', 'soundfonts/GeneralUser_GS.sf2'))
    if not sf_path.is_absolute():
        sf_path = pathlib.Path(__file__).parent / sf_path
    sf_path = sf_path.expanduser()

    gain   = synth_cfg.get('gain', 0.5)
    driver = synth_cfg.get('driver', 'coreaudio')

    fs = fluidsynth.Synth(gain=gain)
    fs.start(driver=driver)
    if not fs.audio_driver:
        raise RuntimeError(
            f"Failed to start audio driver '{driver}'. "
            "Check [synth] driver in config.toml. "
            "macOS: 'coreaudio', Linux: 'alsa' or 'pulseaudio', Windows: 'dsound'."
        )
    sfid = fs.sfload(str(sf_path))
    if sfid == -1:
        raise RuntimeError(f"Failed to load SoundFont: {sf_path}")

    fs.program_select(ch_keys, sfid, 0, 0)    # Acoustic Grand Piano
    fs.program_select(ch_pads, sfid, 128, 0)  # Standard Kit
    fs.cc(ch_keys, 7, 127)   # channel volume
    fs.cc(ch_pads, 7, 127)
    fs.cc(ch_keys, 11, 127)  # expression
    fs.cc(ch_pads, 11, 127)

    print(f"SoundFont  : {sf_path}")
    print(f"Listening  : {port}")
    print(f"Keys       : ch{ch_keys + 1}")
    print(f"Pads       : ch{ch_pads + 1}")
    print("Ctrl-C to quit\n")

    state = make_input_state()

    try:
        with mido.open_input(port) as inport:
            for msg in inport:
                for event in parse_events(msg, state):
                    handle_event(event, fs, ch_keys, ch_pads, sfid)
    except KeyboardInterrupt:
        print("Goodbye!")
    finally:
        fs.delete()


if __name__ == '__main__':
    main()
