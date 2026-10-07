"""
core — shared audio engine for chordiac.

Provides tone generation, chord building, playback, frequency parsing,
and preset definitions. Used by both the CLI (chordiac.py) and the GUI
(chordiac_gui.py).
"""

from __future__ import annotations

import math
import re

import numpy as np
import sounddevice as sd

# ── Constants ─────────────────────────────────────────────────────────────────

SAMPLE_RATE = 44100       # Hz
FADE_MS = 10              # fade-in/out envelope (ms) to avoid clicks
DEFAULT_ROOT = 220.0      # Hz  (A3)
DEFAULT_DURATION = 2.0    # seconds

# Just-intonation presets stored as exact frequency multipliers (already in
# the [1, 2) range — close position). These are NOT raw harmonic partials
# because chords like the minor triad (10:12:15) cannot be expressed as
# folded harmonic partials.
PRESETS: dict[str, tuple[float, ...]] = {
    "just major":       (1.0, 1.25, 1.5),     # 1 : 5/4 : 3/2
    "just minor":       (1.0, 1.2, 1.5),      # 1 : 6/5 : 3/2
    "harmonic seventh": (1.0, 1.25, 1.5, 1.75),  # 1 : 5/4 : 3/2 : 7/4
}

# ── Audio helpers ─────────────────────────────────────────────────────────────


def _sine_tone(freq: float, duration: float, waveform: str,
               sample_rate: int) -> np.ndarray:
    """Return a single tone at *freq*.

    ``waveform`` is either ``"pure"`` (plain sine) or ``"rich"`` (sine + quiet
    2nd and 3rd harmonics added for a warmer timbre).
    """
    n = int(duration * sample_rate)
    t = np.arange(n, dtype=np.float64) / sample_rate
    sig = np.sin(2.0 * np.pi * freq * t)

    if waveform == "rich":
        sig += 0.25 * np.sin(2.0 * np.pi * 2.0 * freq * t)   # 2nd harmonic
        sig += 0.125 * np.sin(2.0 * np.pi * 3.0 * freq * t)  # 3rd harmonic
        sig /= 1.375  # keep peak near 1.0

    return sig


def _apply_envelope(sig: np.ndarray, sample_rate: int,
                    fade_ms: int) -> np.ndarray:
    """Apply a short fade-in and fade-out to prevent audible clicks."""
    fade_len = min(int(fade_ms * sample_rate / 1000), len(sig) // 2)
    if fade_len > 0:
        sig[:fade_len] *= np.linspace(0.0, 1.0, fade_len)
        sig[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
    return sig


def build_chord(multipliers: list[float],
                root_freq: float,
                duration: float,
                waveform: str,
                sample_rate: int,
                fold_octaves: bool) -> np.ndarray:
    """Sum tones at ``root_freq × multiplier`` for each entry.

    When *fold_octaves* is ``True`` each multiplier is shifted by powers of two
    into the range ``[1, 2)``, so all voices sit in a single octave.
    """
    if not multipliers:
        return np.zeros(int(duration * sample_rate), dtype=np.float32)

    # Prepare (optionally folded) frequencies
    freqs: list[float] = []
    for m in multipliers:
        if fold_octaves:
            while m >= 2.0:
                m /= 2.0
            while m < 1.0:
                m *= 2.0
        freqs.append(root_freq * m)

    # Sum all voices
    total: np.ndarray | None = None
    for f in freqs:
        tone = _sine_tone(f, duration, waveform, sample_rate)
        total = tone if total is None else total + tone

    # Normalise and envelope
    if total is not None:
        peak = float(np.max(np.abs(total)))
        if peak > 0.0:
            total /= peak
        total = _apply_envelope(total, sample_rate, FADE_MS)

    return total.astype(np.float32)


def play(samples: np.ndarray, sample_rate: int) -> None:
    """Play a waveform through the default audio output."""
    if len(samples) == 0:
        return
    sd.play(samples, samplerate=sample_rate)
    sd.wait()


# ── Preset multipliers ────────────────────────────────────────────────────────


def geometric_mean_multipliers() -> list[float]:
    """Return multipliers for the geometric-mean "middle third" chord.

    ``[1, √(3/2), 3/2]`` — the third sits at the exact geometric mean between
    root and fifth.
    """
    sq = math.sqrt(1.5)  # √(3/2) ≈ 1.2247
    return [1.0, sq, 1.5]


def harmonic_series_multipliers(n: int = 16) -> list[float]:
    """Return multipliers ``[1, 2, 3, …, n]``."""
    return [float(i) for i in range(1, n + 1)]


# ── Just intonation ratio table ───────────────────────────────────────────────

# Standard 5-limit just intonation ratios for each semitone (0 = unison).
# ET ratios are 2^(s/12); JUST_RATIOS are the pure-interval counterparts.
# The difference (offset in cents) is 1200 * log2(just_ratio / et_ratio).
JUST_RATIOS: dict[int, float] = {
     0: 1/1,      # unison
     1: 16/15,    # minor second   ≈ 1.0667
     2: 9/8,      # major second   ≈ 1.1250
     3: 6/5,      # minor third    ≈ 1.2000
     4: 5/4,      # major third    ≈ 1.2500
     5: 4/3,      # perfect fourth ≈ 1.3333
     6: 45/32,    # tritone (aug. fourth) ≈ 1.40625
     7: 3/2,      # perfect fifth  ≈ 1.5000
     8: 8/5,      # minor sixth    ≈ 1.6000
     9: 5/3,      # major sixth    ≈ 1.6667
    10: 9/5,      # minor seventh  ≈ 1.8000
    11: 15/8,     # major seventh  ≈ 1.8750
}

# Note names per semitone
NOTE_NAMES: dict[int, str] = {
     0: "C",   1: "C♯/D♭",  2: "D",   3: "D♯/E♭",
     4: "E",   5: "F",      6: "F♯/G♭", 7: "G",
     8: "G♯/A♭", 9: "A",  10: "A♯/B♭", 11: "B",
}

# Interval names per semitone
INTERVAL_NAMES: dict[int, str] = {
     0: "1",   1: "♭2",  2: "2",   3: "♭3",
     4: "3",   5: "4",   6: "♭5",  7: "5",
     8: "♭6",  9: "6",  10: "♭7", 11: "7",
}

# Whether a semitone is a "white key" on the piano
IS_WHITE_KEY: dict[int, bool] = {
     0: True,   1: False,  2: True,   3: False,
     4: True,   5: True,   6: False,  7: True,
     8: False,  9: True,  10: False, 11: True,
}


def et_ratio(semitone: int) -> float:
    """Return the equal-temperament frequency ratio for *semitone* steps above root."""
    return 2.0 ** (semitone / 12.0)


def cents_deviation(semitone: int) -> float:
    """Return the deviation of the just ratio from the ET ratio, in cents.

    Positive = just ratio is higher (sharper) than ET.
    """
    jr = JUST_RATIOS.get(semitone)
    if jr is None:
        return 0.0
    er = et_ratio(semitone)
    return 1200.0 * math.log2(jr / er)


# ── Dreiklang comparison ──────────────────────────────────────────────────────

# The three chords for sequential comparison: major, minor, geometric-mean.
COMPARISON: list[tuple[str, list[float] | None]] = [
    ("Dur  (just major)",       [1.0, 1.25, 1.5]),
    ("Moll (just minor)",       [1.0, 1.2, 1.5]),
    ("Mittelterz (geo. mean)",  None),  # special: geometric_mean_multipliers()
]
"""Name and multipliers for each chord in the comparison sequence.

``None`` means ``geometric_mean_multipliers()`` is used at call time.
"""


def build_comparison(root_freq: float, duration: float, waveform: str,
                     sample_rate: int, gap: float = 0.6
                     ) -> np.ndarray:
    """Build one long waveform that plays all three comparison chords
    (Dur → Moll → Mittelterz) separated by *gap* seconds of silence.

    Each chord is built with ``fold_octaves=True`` so they are all in
    close position (enge Lage).
    """
    parts: list[np.ndarray] = []
    gap_samples = int(gap * sample_rate)
    silence = np.zeros(gap_samples, dtype=np.float32)

    for name, mults in COMPARISON:
        if mults is None:
            mults = geometric_mean_multipliers()
        samples = build_chord(mults, root_freq, duration, waveform,
                              sample_rate, fold_octaves=False)
        parts.append(samples)
        parts.append(silence)

    return np.concatenate(parts).astype(np.float32)


# ── Frequency parsing ─────────────────────────────────────────────────────────

# Note → semitone offset (C=0, C#=1, … B=11)
_NOTE_TO_SEMITONE: dict[str, int] = {
    "c": 0, "c#": 1, "db": 1,
    "d": 2, "d#": 3, "eb": 3,
    "e": 4,
    "f": 5, "f#": 6, "gb": 6,
    "g": 7, "g#": 8, "ab": 8,
    "a": 9, "a#": 10, "bb": 10,
    "b": 11,
}
# Pattern: note name (optional accidental) + octave number, e.g. A4, C#3, Bb2
_NOTE_RE = re.compile(r"([a-g]#?b?)(-?\d+)$", re.IGNORECASE)


def parse_frequency(s: str) -> float | None:
    """Parse a frequency string.

    Acceptable forms:

    * A plain number — interpreted as Hz (``"220"``, ``"440.0"``).
    * A note name + octave — uses A4 = 440 Hz equal temperament
      (``"A3"``, ``"C#4"``, ``"Bb2"``).
    """
    s = s.strip()
    if not s:
        return None

    # Try plain float first
    try:
        return float(s)
    except ValueError:
        pass

    # Try note-name
    m = _NOTE_RE.match(s)
    if m:
        key = m.group(1).lower()
        semitone = _NOTE_TO_SEMITONE.get(key)
        if semitone is not None:
            octave = int(m.group(2))
            index = semitone + 12 * octave           # C0 = 0
            a4_index = 9 + 12 * 4                     # A4 = 57
            return 440.0 * (2.0 ** ((index - a4_index) / 12.0))

    return None
