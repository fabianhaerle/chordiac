# chordiac

Hear pure frequency relations — harmonic-series partials, just-intonation chords,
and the geometric-mean "middle third" chord.

Built with **numpy** + **sounddevice** (audio engine) and **tkinter** (GUI).

## Quick start

```bash
pip install -r requirements.txt

# CLI (interactive menu)
python3 chordiac.py

# GUI (tkinter window)
python3 chordiac_gui.py
```

## What it does

Instead of equal temperament (12-tone tuning), chordiac plays chords built from
**exact frequency ratios**:

- **Harmonic-series partials** — type `1 3 5 7` to hear a just major chord
  (folded into one octave as `1, 5/4, 3/2, 7/4`). The raw harmonic series
  (`1 2 3 4 5 6 7 8 …`) is the source of all just-intonation intervals.
- **Geometric-mean "middle third"** — a chord where the third sits at the exact
  geometric mean between root and fifth (`1, √(3/2), 3/2`), neither equal-tempered
  nor just-intonation.
- **Just-intonation presets** — major, minor, harmonic seventh.
- **Octave folding** — toggle to fold all partials into a single octave
  (`[1, 2)`) so you hear them as a tight chord, or leave them at their
  literal frequencies spread across octaves.
- **Waveform switch** — pure sine waves (cleanest for hearing ratios) or
  "rich" mode (quiet 2nd/3rd harmonics added for warmth).
- **Auto-play** (GUI) — every control change re-triggers playback instantly
  so you can sweep values and hear the difference.

## Files

| File | Purpose |
|---|---|
| `core.py` | Shared audio engine — tone generation, chord building, playback, frequency parsing |
| `chordiac.py` | CLI — interactive text menu |
| `chordiac_gui.py` | GUI — tkinter window |
| `requirements.txt` | Python dependencies (`numpy`, `sounddevice`) |

## Requirements

- **Python 3.10+**
- **numpy** and **sounddevice** (install via `pip install -r requirements.txt`)
- **tkinter** — ships with Python, but your Python build must include Tk support.
  On macOS via Homebrew/pyenv, install `tcl-tk` first, then rebuild Python with
  `--with-tcltk-includes` / `--with-tcltk-libs` (see [pyenv wiki](https://github.com/pyenv/pyenv/wiki)).

## Example

```
Root: 220.0 Hz  │  Waveform: pure  │  Fold octaves: ON  │  Duration: 2.0s

  1)  Set root frequency
  2)  Toggle waveform        (pure ↔ rich)
  3)  Toggle octave folding  (on ↔ off)
  4)  Set duration
  5)  Play partials…         (enter numbers)
  6)  Geometric-mean chord   (1, √(3/2), 3/2)
  7)  Preset:  just major
  8)  Preset:  just minor
  9)  Preset:  harmonic seventh
  h)  Harmonic series        (partials 1–16)
  q)  Quit

  ❯
```

## License

MIT
