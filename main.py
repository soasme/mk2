"""
main.py — LaunchKey Mini MK2 synthesizer.
Loads config.toml for MIDI routing and sound configuration.
Uses FluidSynth (via pyfluidsynth) and a SoundFont for audio synthesis.

Event flow:
  MIDI message + input state → app events → synth calls
"""
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass
import mido
import fluidsynth
from modes import chord_learning, note_challenge
from modes import loop_mode

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

CC_PAD_SELECT     = 104   # Scene Up (upper round pad)
CC_KEY_SELECT     = 105   # Scene Down (lower round pad)
CC_TRACK_LEFT     = 103   # Track Left (left arrow button)
CC_TRACK_RIGHT    = 102   # Track Right (right arrow button)
CC_CHANNEL_SELECT = None  # TODO: discover with DEBUG=1 — hold button + press pads 1-9 to pick channel

# Basic-mode note numbers for pads 1-10, mapped to digit (pad 10 → 0)
PAD_NOTE_TO_DIGIT = {
    40: 1, 41: 2, 42: 3, 43: 4,  # Pads 1-4
    48: 5, 49: 6, 50: 7, 51: 8,  # Pads 5-8
    36: 9, 37: 0,                 # Pads 9-10
}

# Pad 16 (basic mode note 47) acts as a bank separator in KeySelect sequences.
# Digits before pad 16 = patch number (1-indexed); digits after = bank number.
# Without pad 16, bank defaults to 0.
# Example: 1,2,8       → patch 128, bank 0
# Example: 1,2,8,16,3  → patch 128, bank 3
PAD_NOTE_BANK_SEP = 47  # Pad 16, basic mode


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
    channel: int       # target MIDI channel (0-indexed)
    keys_bank: int
    keys_program: int  # 0-indexed

@dataclass
class EnterNoteChallengeEvent:
    pass

@dataclass
class ExitNoteChallengeEvent:
    pass

@dataclass
class NoteChallengePlayEvent:
    pass

@dataclass
class NoteChallengeNewEvent:
    pass

@dataclass
class NoteChallengeHintEvent:
    pass

@dataclass
class NoteChallengeBingoEvent:
    pass

@dataclass
class EnterChordLearningEvent:
    pass

@dataclass
class ExitChordLearningEvent:
    pass

@dataclass
class ChordLearningNoteChangedEvent:
    held: frozenset  # current set of held MIDI notes
    is_release: bool  # whether this change came from a note-off

@dataclass
class EnterLoopModeEvent:
    pass

@dataclass
class ExitLoopModeEvent:
    pass

@dataclass
class LoopModeTrackLeftEvent:
    pass

@dataclass
class LoopModeTrackRightEvent:
    pass

@dataclass
class LoopModeRecordToggleEvent:
    pass

@dataclass
class LoopModePlaybackToggleEvent:
    pass


# ---------------------------------------------------------------------------
# Input state (mutated by parse_events)
# ---------------------------------------------------------------------------

# Pad number → KeySelect digit (matches PAD_NOTE_TO_DIGIT via pad layout)
_PAD_TO_DIGIT = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 0}


def parse_entry_pads(pad_str: str):
    """Parse an entry-pad config string into (digits, bank_sep, bank_digits).

    The string is a comma-separated list of pad numbers.  Pad 16 acts as the
    bank separator (same role as in KeySelect), and pads 1-10 contribute
    digits.  Example: "16,1" → ([], True, [1]).
    """
    digits: list = []
    bank_digits: list = []
    bank_sep = False
    for part in pad_str.split(','):
        pad = int(part.strip())
        if pad == 16:
            bank_sep = True
        else:
            d = _PAD_TO_DIGIT.get(pad)
            if d is not None:
                (bank_digits if bank_sep else digits).append(d)
    return digits, bank_sep, bank_digits


def make_input_state(ch_keys, ch_pads, n_notes=4):
    return {
        'ch_keys': ch_keys,
        'ch_pads': ch_pads,
        'current_keys_channel': ch_keys,  # which channel KeySelect and key notes target
        'channel_select_active': False,
        'channel_select_captured': set(),
        'last_keys_channel': ch_keys,  # most recent actual channel key notes were sent on
        'key_select_active': False,
        'key_select_channel': ch_keys,  # latched target when KeySelect is pressed
        'key_select_digits': [],       # patch digits (before pad 16)
        'key_select_bank_digits': [],  # bank digits (after pad 16)
        'key_select_bank_sep': False,  # whether pad 16 has been pressed
        'key_select_captured': set(),
        'pad_select_active': False,
        'pad_select_program': None,        # digit 1-9 pressed during pad select
        'pad_select_captured': set(),
        # Note Challenge Mode
        'note_challenge_active': False,
        'note_challenge_target': [],       # target MIDI note sequence
        'note_challenge_history': [],      # recent key notes played by user
        'note_challenge_n': n_notes,       # number of notes in the challenge
        'note_challenge_min': 48,          # lowest possible note (C3)
        'note_challenge_max': 72,          # highest possible note (C5)
        'note_challenge_entry': parse_entry_pads('16,1'),  # (digits, bank_sep, bank_digits)
        'note_challenge_captured': set(),  # pad notes consumed by the mode
        # Chord Learning Mode
        'chord_learning_active': False,
        'chord_learning_held': set(),
        'chord_learning_entry': parse_entry_pads('16,2'),
        'chord_learning_chord_set': 'core_set',
        'chord_learning_announce_delay': 0.2,  # seconds to wait after last key change
        'chord_learning_announce_timer': None,  # pending threading.Timer
        # Loop Mode
        'loop_mode_active': False,
        'loop_mode_entry': parse_entry_pads('16,3'),
        'loop_mode_n_tracks': 4,
        'loop_mode_tracks': [None] * 4,
        'loop_mode_current_track': 0,
        'loop_mode_recording': False,
        'loop_mode_record_start': 0.0,
        'loop_mode_record_buffer': [],
        'loop_mode_playing': False,
        'loop_mode_play_stop_events': [None] * 4,
    }


# ---------------------------------------------------------------------------
# MIDI → app events
# ---------------------------------------------------------------------------

def parse_events(msg, state):
    """Convert one MIDI message (plus mutable input state) into app events."""
    events = []

    if msg.type == 'note_on':
        digit = PAD_NOTE_TO_DIGIT.get(msg.note)
        if state['channel_select_active'] and digit and 1 <= digit <= 9:
            # Pads 1-9 → channels 0-8; pad 10 (digit 0) ignored (would be ch10)
            state['current_keys_channel'] = digit - 1
            state['channel_select_captured'].add(msg.note)
            print(f"Channel selected: ch{digit}")
        elif state['pad_select_active'] and digit and 1 <= digit <= 9:
            state['pad_select_program'] = digit - 1  # last pad wins
            state['pad_select_captured'].add(msg.note)
        elif state['key_select_active'] and msg.note == PAD_NOTE_BANK_SEP:
            state['key_select_bank_sep'] = True
            state['key_select_captured'].add(msg.note)
        elif state['key_select_active'] and digit is not None:
            if state['key_select_bank_sep']:
                state['key_select_bank_digits'].append(digit)
            else:
                state['key_select_digits'].append(digit)
            state['key_select_captured'].add(msg.note)
        else:
            # Note Challenge Mode: intercept pad 1/2/3 for game controls
            if state['note_challenge_active'] and msg.channel == state['ch_pads']:
                if msg.note == 40:   # Pad 1 — replay target
                    state['note_challenge_captured'].add(msg.note)
                    events.append(NoteChallengePlayEvent())
                    return events
                elif msg.note == 41: # Pad 2 — new target
                    state['note_challenge_captured'].add(msg.note)
                    events.append(NoteChallengeNewEvent())
                    return events
                elif msg.note == 42: # Pad 3 — hint
                    state['note_challenge_captured'].add(msg.note)
                    events.append(NoteChallengeHintEvent())
                    return events

            # Reroute hardware key notes to current_keys_channel
            ch = state['current_keys_channel'] if msg.channel == state['ch_keys'] else msg.channel
            # Track the actual output channel so KeySelect can target it
            if msg.channel != state['ch_pads']:
                state['last_keys_channel'] = ch
            events.append(NoteOnEvent(ch, msg.note, msg.velocity))

            # Note Challenge Mode: track key presses and check for a match
            if state['note_challenge_active'] and msg.channel == state['ch_keys']:
                history = state['note_challenge_history']
                history.append(msg.note)
                n = state['note_challenge_n']
                # Keep history bounded
                if len(history) > n * 4:
                    state['note_challenge_history'] = history[-(n * 4):]
                if note_challenge.check_match(history, state['note_challenge_target']):
                    events.append(NoteChallengeBingoEvent())
                elif DEBUG:
                    target = state['note_challenge_target']
                    recent = history[-n:]
                    hits = sum(1 for a, b in zip(reversed(recent), reversed(target)) if a == b)
                    print(f"Note Challenge: played {note_challenge.midi_note_name(msg.note)} "
                          f"— last {len(recent)}: {note_challenge.note_names_display(recent)} "
                          f"(target: {note_challenge.note_names_display(target)}, {hits}/{n} trailing match)")

            # Chord Learning Mode: track held notes
            if state['chord_learning_active'] and msg.channel == state['ch_keys']:
                state['chord_learning_held'].add(msg.note)
                events.append(ChordLearningNoteChangedEvent(
                    held=frozenset(state['chord_learning_held']),
                    is_release=False,
                ))

    elif msg.type == 'note_off':
        if msg.note in state['channel_select_captured']:
            state['channel_select_captured'].discard(msg.note)
        elif msg.note in state['pad_select_captured']:
            state['pad_select_captured'].discard(msg.note)
        elif msg.note in state['key_select_captured']:
            state['key_select_captured'].discard(msg.note)
        elif msg.note in state['note_challenge_captured']:
            state['note_challenge_captured'].discard(msg.note)
        else:
            ch = state['current_keys_channel'] if msg.channel == state['ch_keys'] else msg.channel
            events.append(NoteOffEvent(ch, msg.note))
            # Chord Learning Mode: update held notes
            if state['chord_learning_active'] and msg.channel == state['ch_keys']:
                state['chord_learning_held'].discard(msg.note)
                events.append(ChordLearningNoteChangedEvent(
                    held=frozenset(state['chord_learning_held']),
                    is_release=True,
                ))

    elif msg.type == 'control_change':
        if CC_CHANNEL_SELECT is not None and msg.control == CC_CHANNEL_SELECT:
            if msg.value == 127:
                state['channel_select_active'] = True
                state['channel_select_captured'] = set()
                print("ChannelSelect Button is pressed")
            else:
                state['channel_select_active'] = False
                print("ChannelSelect Button is released")

        elif msg.control == CC_PAD_SELECT:
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
                state['key_select_channel'] = state['last_keys_channel']
                state['key_select_digits'] = []
                state['key_select_bank_digits'] = []
                state['key_select_bank_sep'] = False
                state['key_select_captured'] = set()
                print(
                    "KeySelect Button is pressed "
                    f"(target channel index {state['key_select_channel']}, "
                    f"ch{state['key_select_channel'] + 1})"
                )
            else:
                state['key_select_active'] = False
                print("KeySelect Button is released")
                digits = state['key_select_digits']
                bank_digits = state['key_select_bank_digits']
                key_select_channel = state['key_select_channel']
                # Configured pad sequence: toggle Note Challenge Mode
                e_digits, e_bank_sep, e_bank_digits = state['note_challenge_entry']
                cl_digits, cl_bank_sep, cl_bank_digits = state['chord_learning_entry']
                lm_digits, lm_bank_sep, lm_bank_digits = state['loop_mode_entry']
                if (digits == e_digits
                        and state['key_select_bank_sep'] == e_bank_sep
                        and bank_digits == e_bank_digits):
                    if state['note_challenge_active']:
                        events.append(ExitNoteChallengeEvent())
                    else:
                        events.append(EnterNoteChallengeEvent())
                elif (digits == cl_digits
                        and state['key_select_bank_sep'] == cl_bank_sep
                        and bank_digits == cl_bank_digits):
                    events.append(EnterChordLearningEvent())
                elif (digits == lm_digits
                        and state['key_select_bank_sep'] == lm_bank_sep
                        and bank_digits == lm_bank_digits):
                    if state['loop_mode_active']:
                        events.append(ExitLoopModeEvent())
                    else:
                        events.append(EnterLoopModeEvent())
                elif digits:
                    if key_select_channel == state['ch_pads']:
                        print(
                            "KeySelect ignored: "
                            f"target channel is ch{key_select_channel + 1} (percussion)"
                        )
                    else:
                        program_1indexed = int(''.join(str(d) for d in digits))
                        bank = int(''.join(str(d) for d in bank_digits)) if bank_digits else 0
                        events.append(ProgramChangeEvent(
                            channel=key_select_channel,
                            keys_bank=bank,
                            keys_program=program_1indexed - 1,
                        ))
        else:
            if DEBUG:
                print(f"CC ch={msg.channel} ctrl={msg.control} val={msg.value}")
            events.append(CCEvent(msg.channel, msg.control, msg.value))

    elif msg.type == 'pitchwheel':
        events.append(PitchBendEvent(msg.channel, msg.pitch))

    return events


# ---------------------------------------------------------------------------
# App events → synth
# ---------------------------------------------------------------------------

def speak(text, wait=False):
    if not SAY_INSTRUMENT:
        return
    try:
        if sys.platform == 'darwin':
            cmd = ['say', normalize_say_text(text)]
        else:
            cmd = ['espeak', text]
        proc = subprocess.Popen(cmd)
        if wait:
            proc.wait()
    except Exception as e:
        print(f"Warning: TTS failed: {e}")


def normalize_say_text(text: str) -> str:
    """Make standalone A speak as a letter on macOS `say`."""
    return re.sub(r'\bA\b', 'A.', text)


def play_sound(path, wait=False):
    """Play an audio file using afplay (macOS) or mpg123 (Linux)."""
    try:
        cmd = ['afplay', str(path)] if sys.platform == 'darwin' else ['mpg123', '--quiet', str(path)]
        proc = subprocess.Popen(cmd)
        if wait:
            proc.wait()
    except Exception as e:
        print(f"Warning: audio playback failed: {e}")


def program_select_with_fallback(fs, channel, sfid, bank, program):
    """Select program; if the preset doesn't exist, fall back to bank 0."""
    if fs.program_select(channel, sfid, bank, program) == -1:
        fs.program_select(channel, sfid, 0, program)
        return 0
    return bank


def cancel_chord_learning_announce_timer(state):
    """Cancel any pending chord-learning announcement."""
    timer = state.get('chord_learning_announce_timer')
    if timer is not None:
        timer.cancel()
        state['chord_learning_announce_timer'] = None


def schedule_chord_learning_announcement(state, held):
    """Debounce chord-learning announcements until held notes settle."""
    cancel_chord_learning_announce_timer(state)
    if len(held) < 2:
        return

    chord_set = state['chord_learning_chord_set']
    delay = max(0.0, float(state.get('chord_learning_announce_delay', 0.2)))
    timer = None

    def _announce(h=held, cs=chord_set):
        if state.get('chord_learning_announce_timer') is not timer:
            return
        state['chord_learning_announce_timer'] = None
        if not state['chord_learning_active']:
            return
        if frozenset(state['chord_learning_held']) != h:
            return
        name = chord_learning.identify_chord(h, cs)
        if name:
            print(f"Chord Learning Mode: {name}")
            speak(name)

    timer = threading.Timer(delay, _announce)
    timer.daemon = True
    timer.start()
    state['chord_learning_announce_timer'] = timer


def handle_event(event, fs, ch_keys, ch_pads, sfid, state):
    if isinstance(event, NoteOnEvent):
        vel = event.velocity if state.get('enable_key_velocity') else 100
        if DEBUG:
            print(f"note_on  ch={event.channel} note={event.note} ({note_challenge.midi_note_name(event.note)}) vel={vel}")
        fs.noteon(event.channel, event.note, vel)
    elif isinstance(event, NoteOffEvent):
        if DEBUG:
            print(f"note_off ch={event.channel} note={event.note} ({note_challenge.midi_note_name(event.note)})")
        fs.noteoff(event.channel, event.note)
    elif isinstance(event, PitchBendEvent):
        fs.pitch_bend(event.channel, event.pitch)
    elif isinstance(event, CCEvent):
        fs.cc(event.channel, event.control, event.value)
    elif isinstance(event, PercussionChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (drum kit changed)")
        if state['chord_learning_active']:
            cancel_chord_learning_announce_timer(state)
            state['chord_learning_active'] = False
            state['chord_learning_held'] = set()
            print("Chord Learning Mode: exited (drum kit changed)")
        actual_bank = program_select_with_fallback(fs, ch_pads, sfid, 128, event.pads_program)
        name = gm_name(actual_bank, event.pads_program)
        fallback = actual_bank != 128
        if fallback:
            print(f"Percussion: program={event.pads_program + 1} name={name} (fallback to bank {actual_bank})")
        else:
            print(f"Percussion: program={event.pads_program + 1} name={name}")
        speak(name)
    elif isinstance(event, ProgramChangeEvent):
        if state['note_challenge_active']:
            state['note_challenge_active'] = False
            state['note_challenge_history'] = []
            print("Note Challenge Mode: exited (tone changed)")
        if state['chord_learning_active']:
            cancel_chord_learning_announce_timer(state)
            state['chord_learning_active'] = False
            state['chord_learning_held'] = set()
            print("Chord Learning Mode: exited (tone changed)")
        actual_bank = program_select_with_fallback(fs, event.channel, sfid, event.keys_bank, event.keys_program)
        fs.cc(event.channel, 7, 127)
        fs.cc(event.channel, 11, 127)
        name = gm_name(actual_bank, event.keys_program)
        fallback = actual_bank != event.keys_bank
        if fallback:
            print(f"Program: ch{event.channel + 1} bank={actual_bank} program={event.keys_program + 1} name={name} (fallback to bank {actual_bank})")
        else:
            print(f"Program: ch{event.channel + 1} bank={event.keys_bank} program={event.keys_program + 1} name={name}")
        speak(name)
    elif isinstance(event, EnterNoteChallengeEvent):
        state['note_challenge_active'] = True
        state['note_challenge_history'] = []
        target = note_challenge.generate_target(state['note_challenge_n'], state['note_challenge_min'], state['note_challenge_max'])
        state['note_challenge_target'] = target
        print(f"Note Challenge Mode: target={note_challenge.note_names_display(target)}")
        def _announce_then_play(t=target):
            speak("Note Challenge Mode", wait=True)
            note_challenge.play_notes_async(t, ch_keys, fs)
        threading.Thread(target=_announce_then_play, daemon=True).start()
    elif isinstance(event, ExitNoteChallengeEvent):
        state['note_challenge_active'] = False
        state['note_challenge_history'] = []
        speak("Goodbye")
    elif isinstance(event, NoteChallengePlayEvent):
        note_challenge.play_notes_async(state['note_challenge_target'], ch_keys, fs)
    elif isinstance(event, NoteChallengeNewEvent):
        target = note_challenge.generate_target(state['note_challenge_n'], state['note_challenge_min'], state['note_challenge_max'])
        state['note_challenge_target'] = target
        state['note_challenge_history'] = []
        print(f"Note Challenge Mode: new target={note_challenge.note_names_display(target)}")
        note_challenge.play_notes_async(target, ch_keys, fs)
    elif isinstance(event, NoteChallengeHintEvent):
        text = note_challenge.note_names_tts(state['note_challenge_target'])
        display = note_challenge.note_names_display(state['note_challenge_target'])
        print(f"Note Challenge Mode: hint={display}")
        speak(text)
    elif isinstance(event, NoteChallengeBingoEvent):
        print("Note Challenge Mode: Bingo!")
        target = note_challenge.generate_target(state['note_challenge_n'], state['note_challenge_min'], state['note_challenge_max'])
        state['note_challenge_target'] = target
        state['note_challenge_history'] = []
        print(f"Note Challenge Mode: new target={note_challenge.note_names_display(target)}")
        bingo_sound = state.get('note_challenge_bingo_sound')
        def _bingo_then_play(t=target, sound=bingo_sound):
            if sound:
                play_sound(sound, wait=True)
            else:
                speak("Bingo", wait=True)
            note_challenge.play_notes_async(t, ch_keys, fs)
        threading.Thread(target=_bingo_then_play, daemon=True).start()
    elif isinstance(event, EnterChordLearningEvent):
        cancel_chord_learning_announce_timer(state)
        state['chord_learning_active'] = True
        state['chord_learning_held'] = set()
        print("Chord Learning Mode: active")
        speak("Chord Learning Mode")
    elif isinstance(event, ExitChordLearningEvent):
        cancel_chord_learning_announce_timer(state)
        state['chord_learning_active'] = False
        state['chord_learning_held'] = set()
        print("Chord Learning Mode: exited")
        speak("Goodbye")
    elif isinstance(event, ChordLearningNoteChangedEvent):
        cancel_chord_learning_announce_timer(state)
        if not event.is_release:
            schedule_chord_learning_announcement(state, event.held)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, 'rb') as f:
        return tomllib.load(f)


def main():
    cfg           = load_config()
    midi_cfg      = cfg.get('midi', {})
    synth_cfg     = cfg.get('synth', {})
    challenge_cfg = cfg.get('note_challenge', {})
    cl_cfg        = cfg.get('chord_learning', {})

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

    # Initialize all melodic channels so any channel is ready when selected
    for ch in range(16):
        if ch == ch_pads:
            continue
        fs.program_select(ch, sfid, 0, 0)  # Acoustic Grand Piano
        fs.cc(ch, 7, 127)                  # channel volume
        fs.cc(ch, 11, 127)                 # expression
    fs.program_select(ch_pads, sfid, 128, 0)  # Standard Kit
    fs.cc(ch_pads, 7, 127)
    fs.cc(ch_pads, 11, 127)

    print(f"SoundFont  : {sf_path}")
    print(f"Listening  : {port}")
    print(f"Keys       : ch{ch_keys + 1}")
    print(f"Pads       : ch{ch_pads + 1}")
    print("Ctrl-C to quit\n")

    n_notes = challenge_cfg.get('n_notes', 4)
    state = make_input_state(ch_keys, ch_pads, n_notes=n_notes)
    state['note_challenge_min'] = challenge_cfg.get('note_min', 48)
    state['note_challenge_max'] = challenge_cfg.get('note_max', 72)
    state['note_challenge_entry'] = parse_entry_pads(challenge_cfg.get('entry_pads', '16,1'))
    state['chord_learning_entry'] = parse_entry_pads(cl_cfg.get('entry_pads', '16,2'))
    state['chord_learning_chord_set'] = cl_cfg.get('chord_set', 'core_set')
    state['chord_learning_announce_delay'] = max(
        0.0,
        float(cl_cfg.get('announce_delay', state['chord_learning_announce_delay'])),
    )
    _bingo_sound = challenge_cfg.get('bingo_sound')
    if _bingo_sound:
        _bingo_path = pathlib.Path(_bingo_sound)
        if not _bingo_path.is_absolute():
            _bingo_path = pathlib.Path(__file__).parent / _bingo_path
        state['note_challenge_bingo_sound'] = str(_bingo_path.expanduser())
    else:
        state['note_challenge_bingo_sound'] = None
    state['enable_key_velocity'] = midi_cfg.get('enable_key_velocity', False)

    try:
        with mido.open_input(port) as inport:
            for msg in inport:
                for event in parse_events(msg, state):
                    handle_event(event, fs, ch_keys, ch_pads, sfid, state)
    except KeyboardInterrupt:
        print("Goodbye!")
    finally:
        fs.delete()


if __name__ == '__main__':
    main()
