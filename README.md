# chordiac

Hear pure frequency relations — harmonic-series partials, just-intonation chords,
the geometric-mean "middle third" chord, and an **ET-vs-just overlay keyboard**
for comparing equal temperament with pure intervals by ear and by eye.

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
- **Just-intonation presets** — major (`1, 5/4, 3/2`), minor (`1, 6/5, 3/2`),
  harmonic seventh (`1, 5/4, 3/2, 7/4`).
- **Octave folding** — toggle to fold all partials into a single octave
  (`[1, 2)`) so you hear them as a tight chord, or leave them at their
  literal frequencies spread across octaves.
- **Waveform switch** — pure sine waves (cleanest for hearing ratios) or
  "rich" mode (quiet 2nd/3rd harmonics added for warmth).
- **Auto-play** (GUI) — every control change re-triggers playback instantly
  so you can sweep values and hear the difference.

### ET-vs-just overlay keyboard (GUI)

A two-octave piano keyboard that visualises the difference between equal
temperament and pure just intonation:

- **White and black keys** labelled with interval names from the root
  (1, ♭2, 2, ♭3, 3, 4, …).
- **Just markers** overlaid as coloured vertical lines + dots:
  - **Green** — the just interval is nearly identical to ET (fifth, fourth).
  - **Red** — the just interval is visibly offset (thirds, sixths — up to
    ±16 cents).
- **ET / Just toggle** — switch between temperaments. Notes entered via the
  keyboard are automatically recalculated in the new tuning when you toggle.
- **Click to build chords** — click keys to accumulate notes into the partials
  field; the chord plays immediately. The info line shows the exact ratio and
  cent deviation for each clicked note.
- **Clear notes** button resets the keyboard input.

### Dreiklang-Vergleich (CLI & GUI)

Compare all three triad types in sequence — Dur → Moll → Mittelterz — with
a single action. Each chord plays for the current duration, separated by a
short gap, so you hear the difference directly.

## Files

| File | Purpose |
|---|---|
| `core.py` | Shared audio engine — tone generation, chord building, playback, frequency parsing, just-intonation ratio table |
| `chordiac.py` | CLI — interactive text menu |
| `chordiac_gui.py` | GUI — tkinter window with keyboard overlay |
| `requirements.txt` | Python dependencies (`numpy`, `sounddevice`) |

## Requirements

- **Python 3.10+**
- **numpy** and **sounddevice** (install via `pip install -r requirements.txt`)
- **tkinter** — ships with Python, but your Python build must include Tk support.
  On macOS via Homebrew/pyenv, install `tcl-tk` first, then rebuild Python with
  `--with-tcltk-includes` / `--with-tcltk-libs` (see [pyenv wiki](https://github.com/pyenv/pyenv/wiki)).

## CLI example

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
  v)  Vergleich              (Dur → Moll → Mittelterz)
  h)  Harmonic series        (partials 1–16)
  q)  Quit

  ❯
```

## License

MIT
