#!/usr/bin/env python3
"""
scripts/compile_audio.py — Compile-time audio cache generator.

Generates all WAV files used by speak() at runtime.  Run this script
(not the `say` or `espeak` command) whenever you add new phrases.
Commit the resulting WAV files under assets/ — no TTS engine is required
at runtime.

Usage:
    python3 scripts/compile_audio.py [--engine {say|espeak}]

Options:
    --engine    TTS engine to use (default: auto-detect).
                  say     — macOS built-in (best voice quality)
                  espeak  — Linux/cross-platform fallback

Output:
    assets/alphabet/{A,B,C,D,E,F,G}.wav    — single note letters
    assets/phrases/{phrase}.wav             — qualifiers and mode names
"""
import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent
ALPHABET_DIR = ROOT / 'assets' / 'alphabet'
PHRASES_DIR = ROOT / 'assets' / 'phrases'

# ── Catalogue ────────────────────────────────────────────────────────────────

# Single letters spoken before sharps/qualifiers (e.g. "A", "G")
LETTERS = list('ABCDEFG')

# All other phrases spoken at runtime, keyed by the text speak() receives.
# The dict value is the WAV filename stem (spaces → underscores).
PHRASES = {
    # Note qualifiers
    'sharp':               'sharp',
    'flat':                'flat',
    # Chord qualities
    'Major':               'Major',
    'Minor':               'Minor',
    'Augmented':           'Augmented',
    'Diminished':          'Diminished',
    # Mode announcements
    'Note Challenge Mode': 'Note_Challenge_Mode',
    'Chord Challenge Mode':'Chord_Challenge_Mode',
    'Loop Mode':           'Loop_Mode',
    # Feedback
    'Bingo':               'Bingo',
    'Correct':             'Correct',
    'Goodbye':             'Goodbye',
}

# ── Engine helpers ────────────────────────────────────────────────────────────

def detect_engine() -> str:
    if sys.platform == 'darwin':
        return 'say'
    for cmd in ('espeak-ng', 'espeak'):
        try:
            subprocess.run([cmd, '--version'], capture_output=True, check=True)
            return cmd
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    sys.exit('Error: no TTS engine found. Install espeak or run on macOS.')


def generate(engine: str, text: str, out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if engine == 'say':
        # macOS say: -o writes AIFF; convert to WAV with afconvert
        aiff = out.with_suffix('.aiff')
        subprocess.run(['say', '-o', str(aiff), '--data-format=LEI16@22050', text], check=True)
        subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16', str(aiff), str(out)], check=True)
        aiff.unlink()
    else:
        subprocess.run([engine, '-w', str(out), text], check=True)
    print(f'  {out.relative_to(ROOT)}')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--engine', choices=['say', 'espeak', 'espeak-ng'],
                        help='TTS engine (default: auto-detect)')
    args = parser.parse_args()
    engine = args.engine or detect_engine()
    print(f'Using engine: {engine}')

    print('\nGenerating alphabet (assets/alphabet/):')
    for letter in LETTERS:
        generate(engine, letter, ALPHABET_DIR / f'{letter}.wav')

    print('\nGenerating phrases (assets/phrases/):')
    for text, stem in PHRASES.items():
        generate(engine, text, PHRASES_DIR / f'{stem}.wav')

    print('\nDone. Commit the updated assets/ directory.')


if __name__ == '__main__':
    main()
