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

import math
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

        # ── Vergleich button ──────────────────────────────────────────────
        row_comp = ttk.Frame(main)
        row_comp.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(row_comp, text="", width=18, anchor="e").pack(side=tk.LEFT)
        self.vergleich_btn = ttk.Button(
            row_comp, text="Vergleich  (Dur → Moll → Mittelterz)",
            command=self._on_comparison,
        )
        self.vergleich_btn.pack(side=tk.LEFT, padx=(6, 0))

        # ── Keyboard ────────────────────────────────────────────────────
        self._build_keyboard_section(main)

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
            mults = core.PRESETS[preset_key]
            self.partials_text.set(" ".join(f"{m:g}" for m in mults))
            self._last_description = f"{preset_key} {list(mults)}"

        self._auto_play()

    def _on_comparison(self) -> None:
        """Play the three-chord comparison (Dur → Moll → Mittelterz)."""
        root_freq = self.root_freq.get()
        waveform = self.waveform.get()
        duration = self.duration.get()
        self.status_var.set("♫  Vergleich: Dur → Moll → Mittelterz ...")
        self.vergleich_btn.configure(state="disabled")

        def worker() -> None:
            samples = core.build_comparison(
                root_freq, duration, waveform, core.SAMPLE_RATE, gap=0.6,
            )
            core.play(samples, core.SAMPLE_RATE)
            self.after(0, lambda: self.vergleich_btn.configure(state="normal"))
            self.after(0, lambda: self.status_var.set("✓ Vergleich fertig"))

        threading.Thread(target=worker, daemon=True).start()

    # ── Keyboard ───────────────────────────────────────────────────────

    # Layout constants
    _SW = 32          # semitone width (px)
    _WHITE_H = 100    # white key height (px)
    _BLACK_H = 62     # black key height (px)
    _BLACK_W = 20     # black key width (px)
    _OCTAVES = 2      # number of octaves to display

    def _build_keyboard_section(self, parent: ttk.Frame) -> None:
        """Add the ET-vs-just overlay keyboard to *parent*."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(4, 2))

        # ── Tuning toggle + Clear button ────────────────────────────────
        ctrl_row = ttk.Frame(frame)
        ctrl_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(ctrl_row, text="Keyboard:", width=18, anchor="e").pack(side=tk.LEFT)

        self._tuning = tk.StringVar(value="just")
        et_rb = ttk.Radiobutton(ctrl_row, text="ET", variable=self._tuning,
                                value="et", command=self._on_tuning_change)
        et_rb.pack(side=tk.LEFT, padx=(6, 0))
        just_rb = ttk.Radiobutton(ctrl_row, text="Just", variable=self._tuning,
                                  value="just", command=self._on_tuning_change)
        just_rb.pack(side=tk.LEFT, padx=2)
        ttk.Label(ctrl_row, text="   click a key to add note",
                  foreground="gray").pack(side=tk.LEFT, padx=(8, 0))
        self._clear_kb_btn = ttk.Button(ctrl_row, text="Clear notes",
                                        command=self._on_clear_keyboard)
        self._clear_kb_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # ── Canvas ───────────────────────────────────────────────────────
        total_w = self._OCTAVES * 12 * self._SW
        canvas_h = self._WHITE_H + 20  # extra space for labels
        self._kb_canvas = tk.Canvas(frame, width=total_w, height=canvas_h,
                                    bg="#f8f8f8", highlightthickness=1,
                                    highlightbackground="#ccc")
        self._kb_canvas.pack(pady=(0, 0))
        self._kb_canvas.bind("<Button-1>", self._on_keyboard_click)

        # ── Offset scale note ────────────────────────────────────────────
        note_frame = ttk.Frame(frame)
        note_frame.pack(fill=tk.X)
        ttk.Label(note_frame, text="",
                  width=18, anchor="e").pack(side=tk.LEFT)
        self._offset_label = tk.StringVar(value="")
        ttk.Label(note_frame, textvariable=self._offset_label,
                  foreground="gray", font=("", 9)).pack(side=tk.LEFT, padx=(6, 0))

        # Draw the keyboard
        self._draw_keyboard()

    def _draw_keyboard(self) -> None:
        """Draw (or redraw) the piano keys and just markers on the canvas."""
        c = self._kb_canvas
        c.delete("all")
        SW = self._SW
        OCT = self._OCTAVES

        # Compute white-key boundaries per octave
        # semitone positions of white keys in one octave
        wk_semitones = [0, 2, 4, 5, 7, 9, 11]
        # For each white key, its left edge and right edge (in semitone units)
        wk_ranges: list[tuple[int, int, int]] = []  # (octave, start_semi, end_semi)
        for octave in range(OCT):
            for i, s in enumerate(wk_semitones):
                start = s
                end = wk_semitones[i + 1] if i + 1 < len(wk_semitones) else 12
                wk_ranges.append((octave, start, end))

        # Draw white keys
        for octave, start_s, end_s in wk_ranges:
            x1 = (octave * 12 + start_s) * SW
            x2 = (octave * 12 + end_s) * SW
            y1, y2 = 0, self._WHITE_H
            c.create_rectangle(x1, y1, x2, y2, fill="white", outline="#999",
                               tags="white_key")

            # Label (note name)
            semi_in_octave = start_s
            note_label = core.INTERVAL_NAMES.get(semi_in_octave, "")
            cx = (x1 + x2) / 2
            c.create_text(cx, self._WHITE_H - 8, text=note_label,
                          font=("", 8), fill="#666", tags="label")

        # Draw black keys
        bk_semitones = [1, 3, 6, 8, 10]
        for octave in range(OCT):
            for s in bk_semitones:
                cx = (octave * 12 + s) * SW + SW / 2
                x1 = cx - self._BLACK_W / 2
                x2 = cx + self._BLACK_W / 2
                y1, y2 = 0, self._BLACK_H
                c.create_rectangle(x1, y1, x2, y2, fill="#333", outline="#222",
                                   tags="black_key")

                # Label
                note_label = core.INTERVAL_NAMES.get(s, "")
                c.create_text(cx, self._BLACK_H - 8, text=note_label,
                              font=("", 7), fill="#ccc", tags="label")

        # Draw just markers
        for octave in range(OCT):
            for s in range(12):
                jr = core.JUST_RATIOS.get(s)
                if jr is None:
                    continue
                # Just position in semitones from root
                just_semi = 12.0 * math.log2(jr)
                # Offset from ET center (in pixels)
                et_center = (octave * 12 + s) * SW + SW / 2
                just_x = (octave * 12 + just_semi) * SW + SW / 2
                offset_px = just_x - et_center

                # Draw a vertical line for the just position
                y1, y2 = 2, self._WHITE_H - 4 if core.IS_WHITE_KEY[s] else self._BLACK_H - 4
                line_color = "#e74c3c" if abs(offset_px) > 1.0 else "#27ae60"
                c.create_line(just_x, y1, just_x, y2, fill=line_color,
                              width=2, tags="just_marker")

                # Draw a small circle at the just position
                dot_color = "#c0392b" if abs(offset_px) > 1.0 else "#2ecc71"
                dot_y = 6 if core.IS_WHITE_KEY[s] else 6
                c.create_oval(just_x - 3, dot_y - 3, just_x + 3, dot_y + 3,
                              fill=dot_color, outline="", tags="just_marker")

        # Draw border line between white and black key area
        c.create_line(0, self._BLACK_H, self._OCTAVES * 12 * SW, self._BLACK_H,
                      fill="#999", width=1)

    def _on_keyboard_click(self, event: tk.Event) -> None:
        """Handle a click on the keyboard canvas."""
        SW = self._SW
        x, y = event.x, event.y

        # Determine octave and semitone
        semi_float = x / SW
        octave = int(semi_float // 12)
        semi = int(semi_float % 12)
        if octave < 0 or octave >= self._OCTAVES:
            return
        if semi < 0 or semi > 11:
            return

        # Determine if black key was hit (within its narrow zone)
        is_black = not core.IS_WHITE_KEY[semi]
        if is_black and y < self._BLACK_H:
            # Check if x is within the black key width
            cx = int(semi_float) * SW + SW / 2
            if abs(x - cx) > self._BLACK_W / 2 + 3:
                # Missed the black key — check nearest white key instead
                is_black = False
                # Determine which white key this falls in
                semi = self._nearest_white_key(int(semi_float) % 12)
                if semi is None:
                    return

        self._add_note_from_keyboard(octave, semi)

    def _nearest_white_key(self, semi: int) -> int | None:
        """Return the nearest white-key semitone to *semi*."""
        wk = [0, 2, 4, 5, 7, 9, 11]
        if semi in wk:
            return semi
        # Find the containing white key range
        for i, w in enumerate(wk):
            if i + 1 < len(wk) and w <= semi < wk[i + 1]:
                # Return the closer edge
                if semi - w <= wk[i + 1] - semi:
                    return w
                else:
                    return wk[i + 1]
        if semi < wk[0]:
            return wk[0]
        return wk[-1]

    def _add_note_from_keyboard(self, octave: int, semi: int) -> None:
        """Add the note at *(octave, semi)* to the partials field and play."""
        if self._tuning.get() == "just":
            ratio = core.JUST_RATIOS.get(semi, 1.0)
        else:
            ratio = core.et_ratio(semi)
        # Account for octave
        multiplier = ratio * (2.0 ** octave)

        # Read current partials, append new multiplier
        raw = self.partials_text.get().strip()
        try:
            current = [float(x) for x in raw.split()] if raw else []
        except ValueError:
            current = []
        current.append(multiplier)

        # Format nicely — use integers where possible
        formatted = []
        for m in current:
            if abs(m - round(m)) < 1e-9:
                formatted.append(str(int(round(m))))
            else:
                formatted.append(f"{m:.4f}")
        self.partials_text.set(" ".join(formatted))

        # Show offset info
        if self._tuning.get() == "just":
            cents = core.cents_deviation(semi)
            note_name = core.NOTE_NAMES.get(semi, f"{semi}")
            self._offset_label.set(
                f"{note_name}: just = {core.JUST_RATIOS[semi]:.4f}, "
                f"ET = {core.et_ratio(semi):.4f}  "
                f"({'−' if cents < 0 else '+'}{abs(cents):.0f} cents)"
            )
        else:
            note_name = core.NOTE_NAMES.get(semi, f"{semi}")
            self._offset_label.set(
                f"{note_name}: ET = {core.et_ratio(semi):.4f}"
            )

        self._last_description = f"keyboard ({len(current)} notes)"
        self._auto_play()

    def _on_tuning_change(self) -> None:
        """Handle ET/Just toggle — clear the offset label."""
        self._offset_label.set("")

    def _on_clear_keyboard(self) -> None:
        """Clear the partials field and reset offset label."""
        self.partials_text.set("")
        self._offset_label.set("")
        self._last_description = "keyboard (cleared)"

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
