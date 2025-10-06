#!/usr/bin/env python3
"""Full-featured GUI for RSD Studio.

This provides a complete Tk-based application for parsing RSD files and 
generating previews/exports. It includes file handling plus preview/export.
"""

from pathlib import Path
import importlib.util
import subprocess
import threading
import queue
import json
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image as PIm, ImageTk


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RSD Studio")
        
        # File handling vars
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.parser_pref = tk.StringVar(value="auto-nextgen-then-classic")
        
        # Preview/export vars  
        self.cmap = tk.StringVar(value="gray")
        self.preview_mode = tk.StringVar(value="auto")
        self.show_seam = tk.IntVar(value=1)
        self.vh = tk.StringVar(value="200")
        self.vfps = tk.StringVar(value="30")
        self.vmax = tk.StringVar(value="255")
        
        # Internal queue for log/preview
        self._q = queue.Queue()
        
        self._build_ui()
        self._check_loop()
    
    def _build_ui(self):
        """Build the complete user interface."""
        # File handling frame
        ff = ttk.LabelFrame(self, text="File Handling")
        ff.pack(fill="x", padx=8, pady=4)
        
        ttk.Label(ff, text="Input RSD:").pack(anchor="w", padx=4)
        f1 = ttk.Frame(ff)
        f1.pack(fill="x", padx=4)
        ttk.Entry(f1, textvariable=self.input_path).pack(side="left", fill="x", expand=True)
        ttk.Button(f1, text="Browse", command=self._browse_input).pack(side="right", padx=2)
        
        ttk.Label(ff, text="Output CSV:").pack(anchor="w", padx=4)
        f2 = ttk.Frame(ff)
        f2.pack(fill="x", padx=4)
        ttk.Entry(f2, textvariable=self.output_path).pack(side="left", fill="x", expand=True)
        ttk.Button(f2, text="Browse", command=self._browse_output).pack(side="right", padx=2)
        
        ttk.Label(ff, text="Parser:").pack(anchor="w", padx=4)
        ttk.OptionMenu(ff, self.parser_pref, 
                      "auto-nextgen-then-classic",
                      "auto-nextgen-then-classic",
                      "classic",
                      "nextgen").pack(fill="x", padx=4)
        
        ttk.Button(ff, text="Parse RSD File", command=self._parse).pack(pady=4)
        
        # Preview/Export frame  
        pf = ttk.LabelFrame(self, text="Preview/Export")
        pf.pack(fill="x", padx=8, pady=4)
        
        f3 = ttk.Frame(pf)
        f3.pack(fill="x", padx=4)
        ttk.Label(f3, text="Colormap:").pack(side="left")
        ttk.OptionMenu(f3, self.cmap, "gray", "gray", "jet", "plasma").pack(side="left", padx=4)
        ttk.Label(f3, text="Preview:").pack(side="left", padx=4)
        ttk.OptionMenu(f3, self.preview_mode, "auto", "auto", "left", "right", "both").pack(side="left", padx=4)
        ttk.Checkbutton(f3, text="Show Seam", variable=self.show_seam).pack(side="left", padx=4)
        
        f4 = ttk.Frame(pf)
        f4.pack(fill="x", padx=4, pady=4)
        ttk.Label(f4, text="Height:").pack(side="left")
        ttk.Entry(f4, textvariable=self.vh, width=6).pack(side="left", padx=4)
        ttk.Label(f4, text="FPS:").pack(side="left", padx=4)
        ttk.Entry(f4, textvariable=self.vfps, width=6).pack(side="left", padx=4)
        ttk.Label(f4, text="Max:").pack(side="left", padx=4)
        ttk.Entry(f4, textvariable=self.vmax, width=6).pack(side="left", padx=4)
        
        ttk.Button(pf, text="Preview", command=self._preview).pack(pady=4)
        ttk.Button(pf, text="Export Video", command=self._export).pack(pady=4)
        
        # Log frame
        lf = ttk.LabelFrame(self, text="Log")
        lf.pack(fill="both", expand=True, padx=8, pady=4)
        
        self.log = tk.Text(lf, height=10)
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Preview display
        self.preview = ttk.Label(self)
        self.preview.pack(padx=8, pady=4)
    
    def _browse_input(self):
        path = filedialog.askopenfilename(filetypes=[("RSD files", "*.RSD")])
        if path:
            self.input_path.set(path)
            if not self.output_path.get():
                self.output_path.set(str(Path(path).with_suffix(".csv")))
    
    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if path:
            self.output_path.set(path)
    
    def _parse(self):
        """Parse RSD file using selected engine."""
        in_path = self.input_path.get()
        if not in_path:
            return messagebox.showerror("Error", "Please select an input RSD file")
            
        out_path = self.output_path.get()
        if not out_path:
            return messagebox.showerror("Error", "Please select an output CSV path")
            
        def job():
            try:
                glue = Path(__file__).parent / "engine_glue.py"
                args = [
                    "python",
                    str(glue),
                    "--input", in_path,
                    "--out", str(Path(out_path).parent),
                    "--prefer", self.parser_pref.get()
                ]
                proc = subprocess.Popen(
                    args, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in proc.stdout:
                    self._q.put(("log", line.strip()))
                    
                proc.wait()
                if proc.returncode == 0:
                    self._q.put(("log", "Parsing complete!"))
                else:
                    self._q.put(("log", f"Parser failed with code {proc.returncode}"))
            except Exception as e:
                self._q.put(("log", f"ERROR: {str(e)}"))
        
        self._run_bg(job)
    
    def _paths_cfg(self):
        """Return (pdir, paths, cfg) for preview/export."""
        pdir = Path(self.output_path.get()).parent
        pats = []
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            pats.extend(sorted(pdir.glob(ext)))
        paths = [str(p) for p in pats]
        
        cfg = {
            "VIDEO_ENCODER": "mp4v",
            "ALIGN_CHANNELS": True,
            "FLIP_RIGHT": True,
            "SWAP_LR": False,
            "MAX_ALIGN_SHIFT": 128,
            "FORCE_SPLIT_MID": False,
            "AUTO_SPLIT": False,
            "COLORMAP": self.cmap.get(),
            "PREVIEW_MODE": self.preview_mode.get(),
            "SHOW_SEAM": bool(self.show_seam.get()),
            "SMOOTH_SHIFT": 11,
            "AUTO_DECIDE": True,
            "EDGE_PAD": 0,
        }
        return pdir, paths, cfg
    
    def _preview(self):
        """Preview selected images."""
        try:
            modp = Path(__file__).parent / "video_exporter.py"
            spec = importlib.util.spec_from_file_location("video_exporter_local", modp)
            vx = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vx)
        except Exception as e:
            return messagebox.showerror("Missing/Bad", "video_exporter.py not importable:\n" + str(e))
            
        pdir, paths, cfg = self._paths_cfg()
        if not paths:
            return messagebox.showerror("No images", "No .png/.jpg found.")
            
        arr0 = np.array(PIm.open(paths[0]))
        row_h = int(arr0.shape[0])
        
        def job():
            try:
                frame, seam, shift, score = vx.build_preview_frame(paths, cfg, row_h, int(self.vh.get()))
                if shift is not None:
                    self._q.put(("log", f"preview: shift={shift:+d}px"))
                self._q.put(("preview", frame))
            except Exception as e:
                self._q.put(("log", "ERROR (preview): " + str(e)))
                
        self._run_bg(job)

    def _export(self):
        """Export video from images."""
        try:
            modp = Path(__file__).parent / "video_exporter.py"
            spec = importlib.util.spec_from_file_location("video_exporter_local", modp)
            vx = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vx)
        except Exception as e:
            return messagebox.showerror("Missing/Bad", "video_exporter.py not importable:\n" + str(e))
            
        pdir, paths, cfg = self._paths_cfg()
        if not paths:
            return messagebox.showerror("No images", "No .png/.jpg found.")
            
        out_mp4 = str(pdir / "waterfall.mp4")
        self._append(f"Exporting → {out_mp4}")
        
        arr0 = np.array(PIm.open(paths[0]))
        row_h = int(arr0.shape[0])
        
        def job():
            try:
                def log(m):
                    self._q.put(("log", m))
                    
                vx.export_waterfall_mp4(
                    paths, cfg, out_mp4, row_h,
                    int(self.vh.get()),
                    int(self.vfps.get()),
                    int(self.vmax.get()),
                    log_func=log
                )
            except Exception as e:
                self._q.put(("log", "ERROR (export): " + str(e)))
                
        self._run_bg(job)
    
    def _append(self, msg: str):
        """Add message to log."""
        try:
            self._q.put(("log", msg))
        except Exception:
            pass
        print(msg)
    
    def _run_bg(self, fn):
        """Run function in background thread."""
        t = threading.Thread(target=fn, daemon=True)
        t.start()
    
    def _check_loop(self):
        """Process queue messages."""
        try:
            while True:
                msg_type, data = self._q.get_nowait()
                if msg_type == "log":
                    self.log.insert("end", str(data) + "\n")
                    self.log.see("end")
                elif msg_type == "preview":
                    img = ImageTk.PhotoImage(PIm.fromarray(data))
                    self.preview.configure(image=img)
                    self.preview.image = img
        except queue.Empty:
            pass
        self.after(100, self._check_loop)


if __name__ == "__main__":
    App().mainloop()