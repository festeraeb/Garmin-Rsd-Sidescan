import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from threaded_runner import start_parse_and_rows
from group_suggest_hinted import suggest as suggest_groups
from preview_runner import compose_preview

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Garmin RSD Studio — Modular Full")
        self.geometry("980x700")

        # ---- FIX: define all Tk variables before building widgets ----
        self.hints_path_var = tk.StringVar(value="")

        self.offset_var     = tk.IntVar(value=0)
        self.seq_start_var  = tk.IntVar(value=0)
        self.window_var     = tk.IntVar(value=40)

        self.flipX_var      = tk.BooleanVar(value=False)
        self.flipY_var      = tk.BooleanVar(value=False)
        self.swap_var       = tk.BooleanVar(value=False)

        self.prefer_var     = tk.StringVar(value="auto")
        self.limit_var      = tk.StringVar(value="0")

        self.detected_channels = []
        self.selected_channels = []

        # ---- build UI after variables exist ----
        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_parse   = ttk.Frame(nb); nb.add(self.tab_parse, text="1) Parse")
        self.tab_preview = ttk.Frame(nb); nb.add(self.tab_preview, text="2) Group & Preview")
        self.tab_render  = ttk.Frame(nb); nb.add(self.tab_render, text="3) Render (Video + KML)")

        # Parse tab
        row=0
        ttk.Label(self.tab_parse, text="Input RSD:").grid(row=row, column=0, sticky="e")
        self.infile = ttk.Entry(self.tab_parse, width=70)
        self.infile.grid(row=row, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(self.tab_parse, text="Browse…", command=self._pick_in).grid(row=row, column=2, padx=4); row+=1

        ttk.Label(self.tab_parse, text="Output folder:").grid(row=row, column=0, sticky="e")
        self.outdir = ttk.Entry(self.tab_parse, width=70)
        self.outdir.grid(row=row, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(self.tab_parse, text="Browse…", command=self._pick_out).grid(row=row, column=2, padx=4); row+=1

        ttk.Label(self.tab_parse, text="Prefer engine:").grid(row=row, column=0, sticky="e")
        self.prefer = ttk.Combobox(self.tab_parse, values=["auto","nextgen","classic","both"], state="readonly", width=10)
        self.prefer.set("auto"); self.prefer.grid(row=row, column=1, sticky="w"); row+=1

        ttk.Label(self.tab_parse, text="Row limit (0=all):").grid(row=row, column=0, sticky="e")
        self.limit = ttk.Entry(self.tab_parse, width=8)
        self.limit.insert(0,"0"); self.limit.grid(row=row, column=1, sticky="w"); row+=1

        self.run_btn = ttk.Button(self.tab_parse, text="Run Parser (threaded)", command=self._run_parser)
        self.run_btn.grid(row=row, column=1, sticky="w", pady=6); row+=1

        self.logbox = tk.Text(self.tab_parse, height=18, width=110)
        self.logbox.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=8)
        self.tab_parse.grid_rowconfigure(row, weight=1); self.tab_parse.grid_columnconfigure(1, weight=1)

        # Preview tab
        fr = ttk.Frame(self.tab_preview); fr.pack(fill="x", padx=4, pady=4)
        ttk.Label(fr, text="Hints JSON (optional):").pack(side="left")
        self.hints_entry = ttk.Entry(fr, textvariable=self.hints_path_var, width=60)
        self.hints_entry.pack(side="left", padx=6)
        ttk.Button(fr, text="Browse…", command=self._pick_hints).pack(side="left", padx=4)
        ttk.Button(fr, text="Auto-pick Pair", command=self._auto_pick).pack(side="left", padx=8)

        fr2 = ttk.Frame(self.tab_preview); fr2.pack(fill="x", padx=4, pady=4)
        self.chan_vars = {}  # ch -> tk.BooleanVar
        self.chan_box = ttk.LabelFrame(fr2, text="Detected Channels")
        self.chan_box.pack(side="left", padx=6, pady=6, fill="y")

        ctrl_box = ttk.LabelFrame(fr2, text="Alignment Controls")
        ctrl_box.pack(side="left", padx=6, pady=6, fill="x", expand=True)
        ttk.Label(ctrl_box, text="Offset (rows):").grid(row=0, column=0, sticky="e")
        ttk.Entry(ctrl_box, textvariable=self.offset_var, width=6).grid(row=0, column=1, sticky="w")
        ttk.Label(ctrl_box, text="Seq start:").grid(row=1, column=0, sticky="e")
        ttk.Entry(ctrl_box, textvariable=self.seq_start_var, width=6).grid(row=1, column=1, sticky="w")
        ttk.Label(ctrl_box, text="Window (rows):").grid(row=2, column=0, sticky="e")
        ttk.Entry(ctrl_box, textvariable=self.window_var, width=6).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(ctrl_box, text="Flip X", variable=self.flipX_var).grid(row=0, column=2, padx=8)
        ttk.Checkbutton(ctrl_box, text="Flip Y", variable=self.flipY_var).grid(row=1, column=2, padx=8)
        ttk.Checkbutton(ctrl_box, text="Swap XY", variable=self.swap_var).grid(row=2, column=2, padx=8)

        ttk.Button(self.tab_preview, text="Build Live Preview", command=self._build_preview).pack(pady=8)

        # Render tab
        ttk.Label(self.tab_render, text="When ready, click to render video + KML using the first selected channel:").pack(pady=6)
        ttk.Button(self.tab_render, text="Render (Video + KML)", command=self._render_full).pack()

    # --------------- UI helpers ---------------
    def _append(self, s: str):
        self.logbox.insert("end", s + "\n")
        self.logbox.see("end")

    def _pick_in(self):
        p = filedialog.askopenfilename(title="Select RSD file", filetypes=[("RSD","*.RSD"),("All","*.*")])
        if p:
            self.infile.delete(0,"end"); self.infile.insert(0,p)

    def _pick_out(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.outdir.delete(0,"end"); self.outdir.insert(0,d)

    def _pick_hints(self):
        p = filedialog.askopenfilename(title="Select hints JSON", filetypes=[("JSON","*.json"),("All","*.*")])
        if p:
            self.hints_path_var.set(p)

    # --------------- Pipeline ---------------
    def _run_parser(self):
        fin  = self.infile.get().strip()
        fout = self.outdir.get().strip()
        if not fin or not fout:
            return messagebox.showerror("Missing paths","Choose input RSD and output folder.")
        prefer = self.prefer.get().strip().lower()
        try:
            limit = int(self.limit.get().strip() or "0")
        except:
            limit = 0
        self._append("Launching threaded parse → per-channel rows → stitch preview…")
        start_parse_and_rows(
            root=self, log_func=self._append,
            input_path=fin, out_dir=fout, prefer=prefer,
            limit_rows=limit, preview_channels=None, preview_only=True
        )
        # populate detected channels after a moment
        self.after(1500, self._refresh_channels_ui)

    def _records_csv(self) -> Path:
        fin  = Path(self.infile.get().strip())
        fout = Path(self.outdir.get().strip())
        return fout / f"{fin.stem}_records.csv"

    def _refresh_channels_ui(self):
        csv_path = self._records_csv()
        if not csv_path.exists():
            return
        # detect channels
        chans=set()
        import csv as _csv
        with csv_path.open("r", encoding="utf-8", newline="") as fp:
            r=_csv.DictReader(fp)
            for row in r:
                try: chans.add(int(float(row.get("channel_id") or 0)))
                except: pass
        self.detected_channels = sorted(chans)
        for w in self.chan_box.winfo_children(): w.destroy()
        self.chan_vars.clear()
        for ch in self.detected_channels:
            v=tk.BooleanVar(value=False); self.chan_vars[ch]=v
            ttk.Checkbutton(self.chan_box, text=f"ch{ch:02d}", variable=v).pack(anchor="w")
        self._append(f"[ui] detected channels: {', '.join('ch%02d'%c for c in self.detected_channels)}")

    def _auto_pick(self):
        csv_path = self._records_csv()
        if not csv_path.exists(): return messagebox.showerror("CSV missing","Run Parse first.")
        hints = self.hints_path_var.get().strip() or None
        info = suggest_groups(str(csv_path), hints_json=hints)
        self._append(f"[auto] boost={info.get('boost')} pairs={len(info.get('pairs',[]))}")
        if info.get("default"):
            a,b = info["default"]["channels"]; off = info["default"]["offset"]
            for ch,v in self.chan_vars.items():
                v.set(ch in (a,b))
            self.offset_var.set(off)
            self._append(f"[auto] selected ch{a:02d}+ch{b:02d}, offset {off:+d}")
        else:
            self._append("[auto] no pair suggested")

    def _selected_pair(self):
        sel=[ch for ch,v in self.chan_vars.items() if v.get()]
        if len(sel)!=2:
            messagebox.showwarning("Pick two","Select exactly two channels for preview."); return None
        return sel[0], sel[1]

    def _build_preview(self):
        pair = self._selected_pair()
        if not pair: return
        chX, chY = pair
        csv_path = self._records_csv()
        rsd_path = Path(self.infile.get().strip())
        if not csv_path.exists() or not rsd_path.exists():
            return messagebox.showerror("Missing inputs","Run Parse first.")
        seq_start = self.seq_start_var.get() or 0
        window    = self.window_var.get() or 40
        offset    = self.offset_var.get() or 0
        flipX     = self.flipX_var.get()
        flipY     = self.flipY_var.get()
        swapXY    = self.swap_var.get()
        self._append(f"[preview] ch{chX:02d}+ch{chY:02d} seq={seq_start} win={window} off={offset} flipX={flipX} flipY={flipY} swap={swapXY}")
        try:
            meta = compose_preview(csv_path, rsd_path, chX, chY, seq_start, window, offset, flipX, flipY, swapXY)
            self._append(f"[preview] ✓ {meta['png']}")
        except Exception as e:
            self._append(f"[preview] ERROR: {e}")

    def _render_full(self):
        fin  = self.infile.get().strip()
        fout = self.outdir.get().strip()
        if not fin or not fout: return messagebox.showerror("Missing paths","Choose input RSD and output folder.")
        prefer = self.prefer.get().strip().lower()
        try: limit = int(self.limit.get().strip() or "0")
        except: limit = 0
        sel=[ch for ch,v in self.chan_vars.items() if v.get()]
        self._append(f"[render] channels={sel or 'auto'}")
        start_parse_and_rows(
            root=self, log_func=self._append,
            input_path=fin, out_dir=fout, prefer=prefer,
            limit_rows=limit, preview_channels=sel or None, preview_only=False
        )

if __name__ == "__main__":
    app = App()
    app.mainloop()
