#!/usr/bin/env python3
"""
chordiac GUI — tkinter frontend for exploring pure frequency ratios.

Run:  python3 chordiac_gui.py

Features:
  - Set root frequency (Hz or note name like A3, C#4)
  - Toggle waveform (pure sine / rich with harmonics)
  - Toggle octave folding
  - Adjust duration with a slider
  - Type arbitrary harmonic partials
  - One-click preset buttons (just intonation + geometric mean)
  - Auto-plays on every change — hear results instantly
"""

from __future__ import annotations

import threading
import time

import sounddevice as sd

import core

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("tkinter is not available on this system.")
    print("Install it via your package manager, or use the CLI: python3 chordiac.py")
    raise SystemExit(1)


# ── Constants ─────────────────────────────────────────────────────────────────

AUTO_PLAY_DELAY_MS = 250       # debounce delay for text-entry fields
PRESET_BUTTONS: list[tuple[str, str | None]] = [
    ("Just Major",      "just major"),
    ("Just Minor",      "just minor"),
    ("Harmonic 7th",    "harmonic seventh"),
    ("Geo Mean",        None),          # special: geometric mean
    ("Harmonic 1–16",   "harmonic"),
]


# ── Application ───────────────────────────────────────────────────────────────


class ChordiacApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        self.title("chordiac — pure ratios")
        self.minsize(480, 400)

        # ── State variables ──────────────────────────────────────────────
        self.root_freq = tk.DoubleVar(value=core.DEFAULT_ROOT)
        self.waveform = tk.StringVar(value="pure")
        self.fold_octaves = tk.BooleanVar(value=True)
        self.duration = tk.DoubleVar(value=core.DEFAULT_DURATION)
        self.partials_text = tk.StringVar(value="1 3 5")

        # Last played chord description (for status display)
        self._last_description = "just major (1, 5, 3)"

        # ── Playback thread management ───────────────────────────────────
        self._play_thread: threading.Thread | None = None
        self._auto_play_after_id: str | None = None
        self._current_samples: tuple[list[float], float, str, bool, float] | None = None

        # ── Build the UI ─────────────────────────────────────────────────
        self._build_ui()

        # ── Bind close ───────────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Initial auto-play after window appears ───────────────────────
        self.after(600, self._auto_play)

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Create all widgets in a vertically stacked layout."""
        padding = {"padx": 12, "pady": 4}

        # ── Title ────────────────────────────────────────────────────────
        title = ttk.Label(self, text="♫  chordiac  —  pure frequency ratios  ♫",
                          font=("", 14, "bold"))
        title.pack(pady=(12, 8))

        # ── Main content frame ───────────────────────────────────────────
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, **padding)

        # ── Row: Root frequency ──────────────────────────────────────────
        row_root = ttk.Frame(main)
        row_root.pack(fill=tk.X, pady=3)
        ttk.Label(row_root, text="Root frequency:", width=18, anchor="e").pack(side=tk.LEFT)
        self.root_entry = ttk.Entry(row_root, textvariable=self.root_freq, width=12)
        self.root_entry.pack(side=tk.LEFT, padx=(6, 4))
        ttk.Label(row_root, text="Hz  (or note, e.g. A3, C#4)", foreground="gray").pack(side=tk.LEFT)
        self.root_entry.bind("<KeyRelease>", self._on_root_key)

        # ── Row: Waveform ────────────────────────────────────────────────
        row_wave = ttk.Frame(main)
        row_wave.pack(fill=tk.X, pady=3)
        ttk.Label(row_wave, text="Waveform:", width=18, anchor="e").pack(side=tk.LEFT)
        pure_rb = ttk.Radiobutton(row_wave, text="pure", variable=self.waveform,
                                  value="pure", command=self._on_control_change)
        pure_rb.pack(side=tk.LEFT, padx=(6, 2))
        rich_rb = ttk.Radiobutton(row_wave, text="rich", variable=self.waveform,
                                  value="rich", command=self._on_control_change)
        rich_rb.pack(side=tk.LEFT, padx=2)

        # ── Row: Octave folding ──────────────────────────────────────────
        row_fold = ttk.Frame(main)
        row_fold.pack(fill=tk.X, pady=3)
        ttk.Label(row_fold, text="Octave folding:", width=18, anchor="e").pack(side=tk.LEFT)
        self.fold_cb = ttk.Checkbutton(row_fold, text="fold partials into [1, 2)",
                                       variable=self.fold_octaves,
                                       command=self._on_control_change)
        self.fold_cb.pack(side=tk.LEFT, padx=(6, 0))

        # ── Row: Duration ────────────────────────────────────────────────
        row_dur = ttk.Frame(main)
        row_dur.pack(fill=tk.X, pady=3)
        ttk.Label(row_dur, text="Duration:", width=18, anchor="e").pack(side=tk.LEFT)
        self.dur_slider = ttk.Scale(row_dur, from_=0.5, to=6.0,
                                    variable=self.duration,
                                    orient=tk.HORIZONTAL, length=200,
                                    command=self._on_duration_slider)
        self.dur_slider.pack(side=tk.LEFT, padx=(6, 8), fill=tk.X, expand=True)
        self.dur_label = ttk.Label(row_dur, text=f"{self.duration.get():.1f}s",
                                   width=5, anchor="w")
        self.dur_label.pack(side=tk.LEFT)

        # ── Separator ────────────────────────────────────────────────────
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ── Row: Partials entry ──────────────────────────────────────────
        row_parts = ttk.Frame(main)
        row_parts.pack(fill=tk.X, pady=3)
        ttk.Label(row_parts, text="Partials:", width=18, anchor="e").pack(side=tk.LEFT)
        self.parts_entry = ttk.Entry(row_parts, textvariable=self.partials_text, width=28)
        self.parts_entry.pack(side=tk.LEFT, padx=(6, 6), fill=tk.X, expand=True)
        self.parts_entry.bind("<KeyRelease>", self._on_partials_key)
        play_btn = ttk.Button(row_parts, text="▶ Play", command=self._auto_play)
        play_btn.pack(side=tk.LEFT)

        # ── Preset buttons ───────────────────────────────────────────────
        row_presets = ttk.Frame(main)
        row_presets.pack(fill=tk.X, pady=(8, 4))
        ttk.Label(row_presets, text="Presets:", width=18, anchor="e").pack(side=tk.LEFT)
        btn_frame = ttk.Frame(row_presets)
        btn_frame.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        for label, preset_key in PRESET_BUTTONS:
            btn = ttk.Button(btn_frame, text=label,
                             command=lambda k=preset_key, lbl=label: self._on_preset(k, lbl))
            btn.pack(side=tk.LEFT, padx=2)

        # ── Separator ────────────────────────────────────────────────────
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ── Status bar ───────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor="w",
                               font=("", 10))
        status_bar.pack(fill=tk.X, pady=(0, 4), ipady=3)

        # ── Quit button ──────────────────────────────────────────────────
        btn_frame2 = ttk.Frame(main)
        btn_frame2.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(btn_frame2, text="Quit", command=self._on_close).pack(side=tk.RIGHT)

    # ── Event handlers ──────────────────────────────────────────────────

    def _on_root_key(self, event: tk.Event | None = None) -> None:
        """Parse the root entry and schedule auto-play."""
        raw = self.root_entry.get().strip()
        parsed = core.parse_frequency(raw)
        if parsed is not None and parsed > 0:
            self.root_freq.set(parsed)
            self.root_entry.configure(foreground="")
        else:
            self.root_entry.configure(foreground="red")
        self._schedule_auto_play()

    def _on_control_change(self) -> None:
        """Radio / checkbox / immediate control changed — play now."""
        self._auto_play()

    def _on_duration_slider(self, value: str) -> None:
        """Update the duration label and schedule auto-play."""
        self.dur_label.configure(text=f"{self.duration.get():.1f}s")
        self._auto_play()

    def _on_partials_key(self, event: tk.Event | None = None) -> None:
        """Debounced auto-play when editing partials."""
        self._schedule_auto_play()

    def _on_preset(self, preset_key: str | None, label: str) -> None:
        """Handle a preset button click."""
        if preset_key is None:
            # Geometric mean
            mults = core.geometric_mean_multipliers()
            self.partials_text.set(" ".join(f"{m:.4f}" for m in mults))
            self._last_description = f"geometric mean ({', '.join(f'{m:.4f}' for m in mults)})"
        elif preset_key == "harmonic":
            mults = core.harmonic_series_multipliers(16)
            self.partials_text.set(" ".join(str(m) for m in mults))
            self._last_description = "harmonic series 1–16"
        else:
            partials = core.PRESETS[preset_key]
            self.partials_text.set(" ".join(str(int(p)) for p in partials))
            self._last_description = f"{preset_key} {partials}"

        self._auto_play()

    # ── Playback ────────────────────────────────────────────────────────

    def _schedule_auto_play(self) -> None:
        """Schedule an auto-play with debounce (cancels previous schedule)."""
        if self._auto_play_after_id is not None:
            self.after_cancel(self._auto_play_after_id)
        self._auto_play_after_id = self.after(AUTO_PLAY_DELAY_MS, self._auto_play)

    def _auto_play(self) -> None:
        """Read all controls, build the chord, and play it."""
        self._auto_play_after_id = None

        # Gather current state
        root_freq = self.root_freq.get()
        waveform = self.waveform.get()
        fold = self.fold_octaves.get()
        duration = self.duration.get()
        raw = self.partials_text.get().strip()

        # Parse partials
        try:
            multipliers = [float(x) for x in raw.split()]
            if not multipliers:
                self.status_var.set("⏸  No partials to play")
                return
        except ValueError:
            self.status_var.set("✗  Invalid partials — enter numbers")
            return

        # Build the chord
        samples = core.build_chord(
            multipliers, root_freq, duration, waveform,
            core.SAMPLE_RATE, fold,
        )

        # Describe what's playing
        fold_str = "fold" if fold else "no-fold"
        desc = (f"♫  {self._last_description}  |  "
                f"{root_freq:.1f} Hz  |  {waveform}  |  {fold_str}  |  "
                f"{duration:.1f}s")
        self.status_var.set(desc)

        # Play in a background thread
        self._play_samples(samples)

    def _play_samples(self, samples: object) -> None:
        """Play *samples* in a background thread, cancelling any previous play."""
        # Stop current playback immediately
        sd.stop()

        # Wait briefly for previous thread to notice the stop and finish
        if self._play_thread is not None and self._play_thread.is_alive():
            self._play_thread.join(timeout=0.3)

        def worker() -> None:
            sd.play(samples, samplerate=core.SAMPLE_RATE)
            sd.wait()

        self._play_thread = threading.Thread(target=worker, daemon=True)
        self._play_thread.start()

    def _on_close(self) -> None:
        """Clean shutdown — stop audio and close window."""
        sd.stop()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    app = ChordiacApp()
    app.mainloop()


if __name__ == "__main__":
    main()
