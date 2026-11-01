"""Interactive Alert Ground Truth Studio and production-pipeline validator."""

from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

DESKTOP_DIR = Path(__file__).resolve().parents[2]
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from tools.video_validation.alert_validation_core import (
    ALERT_TYPES, EVENT_TYPES, collect_system_alerts, export_validation_report,
    load_alert_ground_truth, save_alert_ground_truth,
)


class AlertGroundTruthApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("PostGuard Alert Ground Truth Studio")
        root.geometry("1180x760")
        root.minsize(940, 660)
        self.capture = None
        self.video_path = None
        self.fps = 0.0
        self.frame_count = 0
        self.current_frame = 0
        self.playing = False
        self.updating_seek = False
        self.photo = None
        self.markers = []

        self.event_type = tk.StringVar(value=EVENT_TYPES[0])
        self.alert_type = tk.StringVar(value=ALERT_TYPES[0])
        self.note = tk.StringVar()
        self.time_text = tk.StringVar(value="00:00.000 / 00:00.000")
        self.status = tk.StringVar(value="Open a video and create Alert Ground Truth.")
        self.baseline_eye_distance = tk.StringVar()
        self.tolerance = tk.StringVar(value="2.0")

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)
        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Open Video", command=self.open_video).pack(side="left")
        ttk.Button(toolbar, text="Import Ground Truth", command=self.import_ground_truth).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Export Ground Truth", command=self.export_ground_truth).pack(side="left")
        ttk.Label(toolbar, textvariable=self.time_text, font=("Segoe UI", 11, "bold")).pack(side="right")

        content = ttk.Panedwindow(main, orient="horizontal")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content)
        right = ttk.Frame(content, padding=(14, 0, 0, 0))
        content.add(left, weight=3)
        content.add(right, weight=2)

        self.video_label = ttk.Label(left, anchor="center", text="No video selected")
        self.video_label.pack(fill="both", expand=True)
        self.seek = ttk.Scale(left, from_=0, to=1, command=self.seek_changed)
        self.seek.pack(fill="x", pady=8)
        controls = ttk.Frame(left)
        controls.pack()
        ttk.Button(controls, text="◀ Frame", command=lambda: self.step(-1)).pack(side="left")
        ttk.Button(controls, text="Play / Pause", command=self.toggle_play).pack(side="left", padx=8)
        ttk.Button(controls, text="Frame ▶", command=lambda: self.step(1)).pack(side="left")

        marker_box = ttk.LabelFrame(right, text="Add Alert Ground Truth", padding=12)
        marker_box.pack(fill="x")
        ttk.Label(marker_box, text="Event type").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            marker_box, textvariable=self.event_type, values=EVENT_TYPES,
            state="readonly", width=24,
        ).grid(row=1, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(marker_box, text="Alert transition").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            marker_box, textvariable=self.alert_type, values=ALERT_TYPES,
            state="readonly", width=24,
        ).grid(row=3, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(marker_box, text="Note (optional)").grid(row=4, column=0, sticky="w")
        ttk.Entry(marker_box, textvariable=self.note).grid(row=5, column=0, sticky="ew", pady=(2, 8))
        ttk.Button(marker_box, text="Add marker at current time", command=self.add_marker).grid(
            row=6, column=0, sticky="ew"
        )
        marker_box.columnconfigure(0, weight=1)

        list_box = ttk.LabelFrame(right, text="Ground Truth markers", padding=10)
        list_box.pack(fill="both", expand=True, pady=10)
        self.marker_list = tk.Listbox(list_box, font=("Consolas", 10))
        self.marker_list.pack(fill="both", expand=True)
        self.marker_list.bind("<Double-Button-1>", self.jump_to_marker)
        ttk.Button(list_box, text="Delete selected", command=self.delete_marker).pack(fill="x", pady=(8, 0))

        validation = ttk.LabelFrame(right, text="Run production Alert pipeline", padding=10)
        validation.pack(fill="x")
        ttk.Label(validation, text="Screen baseline eye distance (optional)").grid(row=0, column=0, sticky="w")
        ttk.Entry(validation, textvariable=self.baseline_eye_distance, width=14).grid(row=0, column=1, padx=6)
        ttk.Label(validation, text="Match tolerance (seconds)").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(validation, textvariable=self.tolerance, width=14).grid(row=1, column=1, padx=6)
        ttk.Button(validation, text="Run Alert Validation", command=self.run_validation).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0)
        )
        ttk.Label(main, textvariable=self.status, wraplength=1100).pack(fill="x", pady=(10, 0))

        root.bind("<space>", lambda _event: self.toggle_play())
        root.bind("<Left>", lambda _event: self.step(-1))
        root.bind("<Right>", lambda _event: self.step(1))
        root.protocol("WM_DELETE_WINDOW", self.close)

    @staticmethod
    def format_time(seconds):
        seconds = max(0.0, float(seconds))
        minutes = int(seconds // 60)
        return f"{minutes:02d}:{seconds - minutes * 60:06.3f}"

    def open_video(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Video", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")
        ])
        if not path:
            return
        capture = None
        try:
            capture = cv2.VideoCapture(path)
            if not capture.isOpened():
                raise RuntimeError(
                    "Cannot open this video. The file may be damaged or use an unsupported codec."
                )
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps <= 0 or frame_count <= 0:
                raise RuntimeError("The video has an invalid FPS or frame count.")

            # Decode one frame before replacing the current video. This keeps the
            # existing video usable when the newly selected file cannot be decoded.
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError(
                    "The video was opened, but its first frame could not be decoded."
                )
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

            old_capture = self.capture
            self.capture = capture
            capture = None
            if old_capture is not None:
                old_capture.release()
            self.video_path = Path(path)
            self.fps = fps
            self.frame_count = frame_count
            self.current_frame = 0
            self.playing = False
            self.seek.configure(to=max(1, frame_count - 1))
            self.show_frame(0)
            self.status.set(
                f"Video: {self.video_path.name} | {fps:.2f} FPS | "
                f"{frame_count:,} frames"
            )
        except Exception as exc:
            if capture is not None:
                capture.release()
            messagebox.showerror("Open Video", str(exc), parent=self.root)

    def show_frame(self, frame_index):
        if self.capture is None:
            return
        frame_index = max(0, min(self.frame_count - 1, int(frame_index)))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = self.capture.read()
        if not ok:
            return
        self.current_frame = frame_index
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        scale = min(720 / width, 500 / height, 1.0)
        image = Image.fromarray(rgb).resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
        self.photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self.photo, text="")
        # ttk.Scale invokes its command when its value changes. Suppress that
        # callback here so show_frame -> seek_changed -> show_frame cannot recurse.
        self.updating_seek = True
        try:
            self.seek.set(frame_index)
        finally:
            self.updating_seek = False
        current = frame_index / self.fps
        duration = self.frame_count / self.fps
        self.time_text.set(f"{self.format_time(current)} / {self.format_time(duration)}")

    def seek_changed(self, value):
        if (
            self.capture is not None
            and not self.playing
            and not self.updating_seek
        ):
            self.show_frame(int(float(value)))

    def step(self, amount):
        self.playing = False
        self.show_frame(self.current_frame + amount)

    def toggle_play(self):
        if self.capture is None:
            return
        self.playing = not self.playing
        if self.playing:
            self.play_next()

    def play_next(self):
        if not self.playing or self.capture is None:
            return
        if self.current_frame + 1 >= self.frame_count:
            self.playing = False
            return
        self.show_frame(self.current_frame + 1)
        self.root.after(max(1, round(1000 / self.fps)), self.play_next)

    def add_marker(self):
        if self.capture is None:
            messagebox.showwarning("Ground Truth", "Open a video first")
            return
        self.markers.append({
            "event_type": self.event_type.get(),
            "alert_type": self.alert_type.get(),
            "timestamp_sec": self.current_frame / self.fps,
            "note": self.note.get().strip(),
        })
        self.markers.sort(key=lambda item: (item["timestamp_sec"], item["event_type"]))
        self.note.set("")
        self.refresh_markers()

    def refresh_markers(self):
        self.marker_list.delete(0, tk.END)
        for marker in self.markers:
            self.marker_list.insert(
                tk.END,
                f"{self.format_time(marker['timestamp_sec'])} | "
                f"{marker['event_type']} | {marker['alert_type']} | {marker.get('note', '')}",
            )

    def delete_marker(self):
        selection = self.marker_list.curselection()
        if selection:
            del self.markers[selection[0]]
            self.refresh_markers()

    def jump_to_marker(self, _event=None):
        selection = self.marker_list.curselection()
        if selection and self.capture is not None:
            self.playing = False
            self.show_frame(round(self.markers[selection[0]]["timestamp_sec"] * self.fps))

    def import_ground_truth(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.markers = load_alert_ground_truth(path)
            self.refresh_markers()
            self.status.set(f"Imported {len(self.markers)} Alert Ground Truth markers")
        except Exception as exc:
            messagebox.showerror("Import Ground Truth", str(exc))

    def export_ground_truth(self):
        if not self.markers:
            messagebox.showwarning("Ground Truth", "Add at least one marker")
            return
        default = f"{self.video_path.stem}_alert_ground_truth.csv" if self.video_path else "alert_ground_truth.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default, filetypes=[("CSV", "*.csv")]
        )
        if path:
            try:
                save_alert_ground_truth(path, self.markers)
                self.status.set(f"Saved Ground Truth: {path}")
            except Exception as exc:
                messagebox.showerror("Export Ground Truth", str(exc))

    def run_validation(self):
        if self.video_path is None or not self.markers:
            messagebox.showwarning("Validation", "Open a video and add Ground Truth markers first")
            return
        output = filedialog.askdirectory(title="Select validation output folder")
        if not output:
            return
        try:
            baseline_text = self.baseline_eye_distance.get().strip()
            baseline = float(baseline_text) if baseline_text else None
            tolerance = float(self.tolerance.get())
            self.playing = False
            system_alerts, metadata = collect_system_alerts(
                self.video_path, baseline_eye_distance=baseline,
                status_callback=self.update_status,
            )
            report = export_validation_report(
                output, self.markers, system_alerts, metadata,
                tolerance_seconds=tolerance,
            )
            summary = report["summary"]
            percent = lambda value: "N/A" if value is None else f"{value * 100:.2f}%"
            text = (
                f"Matched {summary['matched']} | Missed {summary['missed']} | "
                f"System only {summary['system_only']}\n"
                f"Precision {percent(summary['precision'])} | "
                f"Recall {percent(summary['recall'])} | "
                f"F1 {percent(summary['f1_score'])}\n"
                f"Report: {report['report_path']}"
            )
            self.status.set(text)
            messagebox.showinfo("Alert Validation Complete", text)
        except Exception as exc:
            messagebox.showerror("Alert Validation", str(exc))

    def update_status(self, text):
        self.status.set(text)
        self.root.update_idletasks()

    def close(self):
        self.playing = False
        if self.capture is not None:
            self.capture.release()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="PostGuard Alert Ground Truth Studio")
    parser.add_argument("--validate-ground-truth")
    args = parser.parse_args()
    if args.validate_ground_truth:
        markers = load_alert_ground_truth(args.validate_ground_truth)
        print(json.dumps(markers, ensure_ascii=False, indent=2))
        return
    root = tk.Tk()
    AlertGroundTruthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
