#!/usr/bin/env python3
"""
chordiac — hear pure frequency relations through harmonic-series partials,
just-intonation chords, and the geometric-mean "middle third" chord.

CLI entry point. For the GUI, run chordiac_gui.py.

Dependencies: numpy, sounddevice
    pip install numpy sounddevice
"""

from __future__ import annotations

import math

import core

# ── CLI helpers ───────────────────────────────────────────────────────────────


def _play_preset(name: str, partials: tuple[float, ...],
                 root_freq: float, duration: float,
                 waveform: str, fold_octaves: bool) -> None:
    print(f"  ♪ {name}: partials {partials}")
    samples = core.build_chord(
        list(partials), root_freq, duration, waveform, core.SAMPLE_RATE, fold_octaves,
    )
    core.play(samples, core.SAMPLE_RATE)


def _play_geometric_mean(root_freq: float, duration: float,
                         waveform: str) -> None:
    """Play  root, √(3/2), 3/2  — the "middle third" between root and fifth."""
    multipliers = core.geometric_mean_multipliers()
    print(f"  ♪ geometric-mean chord: {multipliers}")
    samples = core.build_chord(
        multipliers, root_freq, duration, waveform, core.SAMPLE_RATE,
        fold_octaves=False,  # multipliers already in [1, 2)
    )
    core.play(samples, core.SAMPLE_RATE)


# ── Interactive menu ──────────────────────────────────────────────────────────


def _show_status(root_freq: float, waveform: str,
                 fold_octaves: bool, duration: float) -> None:
    line = (
        f"Root: {root_freq:.1f} Hz  │  "
        f"Waveform: {waveform}  │  "
        f"Fold octaves: {'ON' if fold_octaves else 'OFF'}  │  "
        f"Duration: {duration:.1f}s"
    )
    print()
    print("┌" + "─" * (len(line) + 2) + "┐")
    print(f"│ {line} │")
    print("└" + "─" * (len(line) + 2) + "┘")


def main() -> None:
    root_freq = core.DEFAULT_ROOT
    waveform = "pure"
    fold_octaves = True
    duration = core.DEFAULT_DURATION

    print("╔══════════════════════════════════════════════╗")
    print("║          chordiac  —  pure ratios           ║")
    print("╚══════════════════════════════════════════════╝")

    while True:
        _show_status(root_freq, waveform, fold_octaves, duration)

        print()
        print("  1)  Set root frequency")
        print("  2)  Toggle waveform        (pure ↔ rich)")
        print("  3)  Toggle octave folding  (on ↔ off)")
        print("  4)  Set duration")
        print("  5)  Play partials…         (enter numbers)")
        print("  6)  Geometric-mean chord   (1, √(3/2), 3/2)")
        print("  7)  Preset:  just major")
        print("  8)  Preset:  just minor")
        print("  9)  Preset:  harmonic seventh")
        print("  v)  Vergleich              (Dur → Moll → Mittelterz)")
        print("  h)  Harmonic series        (partials 1–16)")
        print("  q)  Quit")
        print()

        choice = input("  ❯ ").strip().lower()

        # ── 1  Root frequency ────────────────────────────────────────────
        if choice == "1":
            val = input("  Root (Hz or note, e.g. 220 or A3): ").strip()
            parsed = core.parse_frequency(val)
            if parsed is not None and parsed > 0:
                root_freq = parsed
                print(f"  ✓ Root = {root_freq:.1f} Hz")
            else:
                print("  ✗ Could not parse frequency.")

        # ── 2  Waveform toggle ───────────────────────────────────────────
        elif choice == "2":
            waveform = "rich" if waveform == "pure" else "pure"
            print(f"  ✓ Waveform → {waveform}")

        # ── 3  Octave-folding toggle ─────────────────────────────────────
        elif choice == "3":
            fold_octaves = not fold_octaves
            print(f"  ✓ Octave folding → {'ON' if fold_octaves else 'OFF'}")

        # ── 4  Duration ──────────────────────────────────────────────────
        elif choice == "4":
            val = input("  Duration (seconds): ").strip()
            try:
                d = float(val)
                if d > 0:
                    duration = d
                    print(f"  ✓ Duration = {duration:.1f}s")
                else:
                    print("  ✗ Must be positive.")
            except ValueError:
                print("  ✗ Invalid number.")

        # ── 5  Play arbitrary partials ───────────────────────────────────
        elif choice == "5":
            val = input("  Partials (space-separated, e.g. 1 3 5 7): ").strip()
            try:
                parts = [float(x) for x in val.split()]
                if not parts:
                    print("  ✗ No numbers entered.")
                    continue
                print(f"  ♪ partials {parts}")
                samples = core.build_chord(
                    parts, root_freq, duration, waveform, core.SAMPLE_RATE, fold_octaves,
                )
                core.play(samples, core.SAMPLE_RATE)
            except ValueError:
                print("  ✗ Invalid numbers.")

        # ── 6  Geometric-mean chord ──────────────────────────────────────
        elif choice == "6":
            _play_geometric_mean(root_freq, duration, waveform)

        # ── 7–9  Presets ─────────────────────────────────────────────────
        elif choice == "7":
            _play_preset("just major", core.PRESETS["just major"],
                         root_freq, duration, waveform, fold_octaves)
        elif choice == "8":
            _play_preset("just minor", core.PRESETS["just minor"],
                         root_freq, duration, waveform, fold_octaves)
        elif choice == "9":
            _play_preset("harmonic seventh", core.PRESETS["harmonic seventh"],
                         root_freq, duration, waveform, fold_octaves)

        # ── v  Vergleich ─────────────────────────────────────────────────
        elif choice == "v":
            print("  ♪ Vergleich: Dur → Moll → Mittelterz")
            samples = core.build_comparison(
                root_freq, duration, waveform, core.SAMPLE_RATE, gap=0.6,
            )
            core.play(samples, core.SAMPLE_RATE)

        # ── h  Harmonic series ───────────────────────────────────────────
        elif choice == "h":
            parts = core.harmonic_series_multipliers(16)
            print(f"  ♪ harmonic series: partials 1–16")
            samples = core.build_chord(
                parts, root_freq, duration, waveform, core.SAMPLE_RATE, fold_octaves,
            )
            core.play(samples, core.SAMPLE_RATE)

        # ── q  Quit ──────────────────────────────────────────────────────
        elif choice == "q":
            print("  Bye!")
            break

        else:
            print("  ✗ Unknown option.")


if __name__ == "__main__":
    main()
