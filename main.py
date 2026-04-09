"""
main.py — LaunchKey Mini MK2 synthesizer.
Loads config.toml for MIDI routing and sound configuration.
Uses FluidSynth (via pyfluidsynth) and a SoundFont for audio synthesis.
"""
import pathlib
import tomllib
import mido
import fluidsynth

CONFIG_PATH = pathlib.Path(__file__).parent / 'config.toml'


def load_config():
    with open(CONFIG_PATH, 'rb') as f:
        return tomllib.load(f)


def main():
    cfg        = load_config()
    midi_cfg   = cfg.get('midi', {})
    track_cfg  = cfg.get('track', {})
    synth_cfg  = cfg.get('synth', {})

    port     = midi_cfg.get('port', 'Launchkey Mini LK Mini MIDI')
    ch_keys  = midi_cfg.get('channel_keys', 0)
    ch_pads  = midi_cfg.get('channel_pads', 9)

    sf_path = pathlib.Path(synth_cfg.get('soundfont', 'soundfonts/GeneralUser_GS.sf2'))
    if not sf_path.is_absolute():
        sf_path = pathlib.Path(__file__).parent / sf_path
    sf_path = sf_path.expanduser()

    gain   = synth_cfg.get('gain', 0.5)
    driver = synth_cfg.get('driver', 'coreaudio')

    fs   = fluidsynth.Synth(gain=gain)
    fs.start(driver=driver)
    sfid = fs.sfload(str(sf_path))
    if sfid == -1:
        raise RuntimeError(f"Failed to load SoundFont: {sf_path}")

    # Keys channel: select instrument by bank + program
    keys_bank    = track_cfg.get('keys_bank', 0)
    keys_program = track_cfg.get('keys_program', 0)
    fs.program_select(ch_keys, sfid, keys_bank, keys_program)

    # Pads channel 9 is GM percussion — no program_select needed

    print(f"SoundFont  : {sf_path}")
    print(f"Listening  : {port}")
    print(f"Keys       : ch{ch_keys + 1}, bank {keys_bank}, program {keys_program}")
    print(f"Pads       : ch{ch_pads + 1} (GM percussion)")
    print("Ctrl-C to quit\n")

    try:
        with mido.open_input(port) as inport:
            for msg in inport:
                if msg.type == 'note_on':
                    fs.noteon(msg.channel, msg.note, msg.velocity)
                elif msg.type == 'note_off':
                    fs.noteoff(msg.channel, msg.note)
                elif msg.type == 'control_change':
                    fs.cc(msg.channel, msg.control, msg.value)
                elif msg.type == 'pitchwheel':
                    fs.pitch_bend(msg.channel, msg.pitch)
    except KeyboardInterrupt:
        print("Goodbye!")
    finally:
        fs.delete()


if __name__ == '__main__':
    main()
