# AGENTS.md — Guidelines for AI Coding Agents

This document describes conventions and constraints that AI agents (Copilot,
Claude, Codex, etc.) must follow when working on this repository.

---

## Audio / TTS Policy

**No TTS engine (`say`, `espeak`, `espeak-ng`, …) is called at runtime.**

All spoken audio is served from pre-recorded WAV files checked in under
`assets/`.  The `speak()` function in `main.py` is a pure WAV-lookup-and-play
function.

### Compile-time generation

Run the compile script **once** after adding or changing any phrase, then
commit the resulting WAV files:

```bash
python3 scripts/compile_audio.py          # auto-detects say (macOS) or espeak
python3 scripts/compile_audio.py --engine say      # force macOS say
python3 scripts/compile_audio.py --engine espeak   # force espeak
```

WAVs are written to:

| Directory | Contents |
|---|---|
| `assets/alphabet/` | Single note letters: `A.wav` … `G.wav` |
| `assets/phrases/` | Qualifiers and mode names: `sharp.wav`, `Major.wav`, … |

### Adding a new spoken phrase

1. Add the phrase text → filename mapping to `PHRASES` in
   `scripts/compile_audio.py`.
2. Run `python3 scripts/compile_audio.py`.
3. Commit both the script change **and** the new WAV file(s) together.

### Rules for agents

- **Do not** add calls to `say`, `espeak`, `subprocess.run(['say', …])`, or
  any other TTS engine in `main.py` or any mode file.
- **Do not** use Python's `pyttsx3`, `gtts`, or similar libraries at runtime.
- If a new phrase needs to be spoken, follow the *Adding a new spoken phrase*
  workflow above and commit the WAV.
- `speak()` silently logs and skips any token that has no cached WAV — missing
  audio is a bug; fix it by running the compile script and committing.

---

## General conventions

- Python 3.12+; no external runtime deps beyond those in `requirements.txt`.
- All MIDI and audio I/O is in `main.py`; game logic lives in `modes/`.
- Config lives in `config.toml`; never hard-code MIDI channels or pad numbers.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
