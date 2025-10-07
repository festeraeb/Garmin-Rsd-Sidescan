#!/usr/bin/env python3
import threading, queue, subprocess, shlex, sys, os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from PIL import Image, ImageTk

APP_NAME="Garmin RSD Studio (engines)"; APP_VER="1.5.13"

def _find_py(): return sys.executable or "python"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VER}")
        self.geometry("1200x820"); self.minsize(1050,700)
        self.preview_imgtk=None
        self._worker=None; self._q=queue.Queue()
        self._build(); self.after(100,self._poll)

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True)

        # Parser
        self.tab_parse=ttk.Frame(nb); nb.add(self.tab_parse, text="Parser"); self._build_parser(self.tab_parse)

        # Stitch (NEW)
        self.tab_stitch=ttk.Frame(nb); nb.add(self.tab_stitch, text="Stitch (ch4+ch5)")
        self._build_stitch(self.tab_stitch)

        # Preview/Export
        self.tab_px=ttk.Frame(nb); nb.add(self.tab_px, text="Preview / Export"); self._build_preview(self.tab_px)

        # Log
        self.tab_log=ttk.Frame(nb); nb.add(self.tab_log, text="Log")
        self.log=tk.Text(self.tab_log, height=10); self.log.pack(fill="both", expand=True)

    # ---------------- Parser tab ----------------
    def _build_parser(self, root):
        pad={"padx":8,"pady":5}
        frm=ttk.Labelframe(root, text="Run parser (engine_glue.py; NextGen → Classic fallback)")
        frm.pack(fill="x", padx=8, pady=8)
        self.infile=tk.StringVar(); self.outdir=tk.StringVar()
        row=0
        ttk.Label(frm,text="Input RSD/zip:").grid(row=row,column=0,sticky="e",**pad)
        ttk.Entry(frm,textvariable=self.infile,width=80).grid(row=row,column=1,sticky="we",**pad); frm.columnconfigure(1,weight=1)
        ttk.Button(frm,text="Browse…",command=self._pick_rsd).grid(row=row,column=2,**pad); row+=1
        ttk.Label(frm,text="Output folder:").grid(row=row,column=0,sticky="e",**pad)
        ttk.Entry(frm,textvariable=self.outdir,width=80).grid(row=row,column=1,sticky="we",**pad)
        ttk.Button(frm,text="Choose…",command=self._pick_out).grid(row=row,column=2,**pad); row+=1
        self.prefer=tk.StringVar(value="auto-nextgen-then-classic")
        ttk.Label(frm,text="Prefer engine:").grid(row=row,column=0,sticky="e",**pad)
        ttk.Combobox(frm,textvariable=self.prefer,state="readonly",width=22,values=["auto-nextgen-then-classic","nextgen","classic"]).grid(row=row,column=1,sticky="w",**pad); row+=1
        act=ttk.Frame(frm); act.grid(row=row,column=0,columnspan=3,sticky="we",**pad)
        self.prog=ttk.Progressbar(act,length=280,mode="indeterminate"); self.prog.pack(side="right", padx=6)
        ttk.Button(act,text="Run Parser",command=self._run_parser).pack(side="left")
        ttk.Button(act,text="Open Output",command=self._open_rows).pack(side="left", padx=8)
        ttk.Label(root, foreground="#666", text="This shells engine_glue.py. Parser logic untouched.").pack(anchor="w", padx=12, pady=(4,8))

    def _pick_rsd(self): 
        p=filedialog.askopenfilename(title="Pick Garmin file", filetypes=[("All","*.*")])
        if p: self.infile.set(p)
    def _pick_out(self):
        p=filedialog.askdirectory(title="Choose output folder")
        if p: self.outdir.set(p)
    def _open_rows(self):
        d=self.outdir.get().strip()
        if not d: return
        try: os.startfile(d)
        except Exception: 
            try: subprocess.Popen(["explorer", d])
            except Exception: pass

    def _run_parser(self):
        here=Path(__file__).parent; glue=here/"engine_glue.py"
        if not glue.exists(): return messagebox.showerror("Missing","engine_glue.py not found next to the GUI.")
        fin=self.infile.get().strip(); fout=self.outdir.get().strip()
        if not fin: return messagebox.showerror("Missing input","Choose an input RSD/zip.")
        if not fout: return messagebox.showerror("Missing output","Choose an output folder.")
        pref=self.prefer.get(); prefer_map={"nextgen":"--prefer=nextgen","classic":"--prefer=classic","auto-nextgen-then-classic":"--prefer=auto"}
        cmd=[_find_py(), str(glue), "--input", fin, "--out", fout, prefer_map.get(pref,"--prefer=auto")]
        self._append("Parser: " + " ".join(shlex.quote(x) for x in cmd))
        def job():
            try:
                self._q.put(("prog",("spin",None)))
                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as P:
                    for line in P.stdout: self._q.put(("log", line.rstrip("\n")))
                self._q.put(("log","Parser finished."))
            except Exception as e:
                self._q.put(("log", f"ERROR (parser): {e}"))
            finally:
                self._q.put(("done", None))
        self._run_bg(job)

    # ---------------- Stitch tab (NEW) ----------------
    def _build_stitch(self, root):
        pad={"padx":8,"pady":5}
        frm=ttk.Labelframe(root, text="Stitch per-channel rows (ch4 + ch5) using records CSV")
        frm.pack(fill="x", padx=8, pady=8)
        self.rows_st=tk.StringVar(); self.csv_st=tk.StringVar(); self.out_st=tk.StringVar()
        r=0
        ttk.Label(frm,text="Rows folder:").grid(row=r,column=0,sticky="e",**pad)
        ttk.Entry(frm,textvariable=self.rows_st,width=80).grid(row=r,column=1,sticky="we",**pad); frm.columnconfigure(1,weight=1)
        ttk.Button(frm,text="Browse…",command=lambda:self._pick_dir(self.rows_st)).grid(row=r,column=2,**pad); r+=1
        ttk.Label(frm,text="records CSV:").grid(row=r,column=0,sticky="e",**pad)
        ttk.Entry(frm,textvariable=self.csv_st,width=80).grid(row=r,column=1,sticky="we",**pad)
        ttk.Button(frm,text="Pick CSV…",command=lambda:self._pick_csv(self.csv_st)).grid(row=r,column=2,**pad); r+=1
        ttk.Label(frm,text="Output folder:").grid(row=r,column=0,sticky="e",**pad)
        ttk.Entry(frm,textvariable=self.out_st,width=80).grid(row=r,column=1,sticky="we",**pad)
        ttk.Button(frm,text="Choose…",command=lambda:self._pick_dir(self.out_st)).grid(row=r,column=2,**pad); r+=1

        par=ttk.Labelframe(root, text="Parameters")
        par.pack(fill="x", padx=8, pady=2)
        self.key_every=tk.IntVar(value=50); self.max_shift=tk.IntVar(value=128); self.flip_right=tk.BooleanVar(value=True); self.swap_lr=tk.BooleanVar(value=False); self.water=tk.IntVar(value=2)
        ttk.Label(par,text="Keyframe every (rows)").grid(row=0,column=0,sticky="e"); ttk.Spinbox(par,from_=1,to=500,increment=1,textvariable=self.key_every,width=8).grid(row=0,column=1,sticky="w")
        ttk.Label(par,text="Max shift (px)").grid(row=0,column=2,sticky="e"); ttk.Spinbox(par,from_=0,to=512,textvariable=self.max_shift,width=8).grid(row=0,column=3,sticky="w")
        ttk.Checkbutton(par,text="Flip right beam",variable=self.flip_right).grid(row=0,column=4,sticky="w",padx=10)
        ttk.Checkbutton(par,text="Swap L/R before stitch",variable=self.swap_lr).grid(row=0,column=5,sticky="w",padx=10)
        ttk.Label(par,text="Water seam (px)").grid(row=0,column=5,sticky="e"); ttk.Spinbox(par,from_=0,to=32,textvariable=self.water,width=6).grid(row=0,column=6,sticky="w")

        act=ttk.Frame(root); act.pack(fill="x", padx=8, pady=8)
        self.prog_st=ttk.Progressbar(act,length=280,mode="indeterminate"); self.prog_st.pack(side="right", padx=6)
        ttk.Button(act,text="Run Stitch",command=self._run_stitch).pack(side="left")

        ttk.Label(root, foreground="#666",
                  text="Tip: This does NOT touch the parser. It pairs ch4 & ch5 by CSV order, aligns every N rows, and writes stitched frames.").pack(anchor="w", padx=12, pady=(0,8))

    def _pick_dir(self, var):
        p=filedialog.askdirectory(title="Choose folder")
        if p: var.set(p)
    def _pick_csv(self, var):
        p=filedialog.askopenfilename(title="Pick records CSV", filetypes=[("CSV","*.csv"),("All","*.*")])
        if p: var.set(p)

    def _run_stitch(self):
        rows=self.rows_st.get().strip(); csvp=self.csv_st.get().strip(); outp=self.out_st.get().strip()
        if not rows or not csvp or not outp: return messagebox.showerror("Missing","Set Rows, CSV, and Output.")
        def job():
            try:
                self._q.put(("spin","stitch"))
                # import local module
                import importlib.util
                modp = Path(__file__).parent / "rows_from_csv_rsd.py"
                spec = importlib.util.spec_from_file_location("rows_from_csv_rsd", modp)
                m   = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
                m.stitch_from_csv(rows, csvp, outp,
                                  key_every=int(self.key_every.get()),
                                  max_shift=int(self.max_shift.get()),
                                  flip_right=bool(self.flip_right.get()),
                                  water_px=int(self.water.get()),
                                  log=lambda s: self._q.put(("log", s)))
                self._q.put(("log","Stitch finished."))
            except Exception as e:
                self._q.put(("log","ERROR (stitch): "+str(e)))
            finally:
                self._q.put(("done",None))
        self._run_bg(job)

    # ---------------- Preview/Export tab ----------------
    def _build_preview(self, root):
        pad={"padx":6,"pady":4}
        top=ttk.Frame(root); top.pack(fill="x", padx=8, pady=8)
        self.rows=tk.StringVar()
        ttk.Label(top,text="Rows folder:").grid(row=0,column=0,sticky="e",**pad)
        ttk.Entry(top,textvariable=self.rows).grid(row=0,column=1,sticky="we",**pad); top.columnconfigure(1,weight=1)
        ttk.Button(top,text="Browse…",command=self._pick_rows).grid(row=0,column=2,**pad)

        opts=ttk.Frame(root); opts.pack(fill="x", padx=8)
        v=ttk.Labelframe(opts,text="Video"); v.grid(row=0,column=0,sticky="nsew",padx=4,pady=2)
        self.vfps=tk.IntVar(value=30); self.vh=tk.IntVar(value=1080); self.vmax=tk.IntVar(value=300000); self.enc=tk.StringVar(value="mp4v")
        ttk.Label(v,text="FPS").grid(row=0,column=0,sticky="e"); ttk.Spinbox(v,from_=1,to=60,textvariable=self.vfps,width=6).grid(row=0,column=1,sticky="w")
        ttk.Label(v,text="Height").grid(row=1,column=0,sticky="e"); ttk.Spinbox(v,from_=360,to=2160,increment=60,textvariable=self.vh,width=6).grid(row=1,column=1,sticky="w")
        ttk.Label(v,text="Max frames").grid(row=2,column=0,sticky="e"); ttk.Spinbox(v,from_=1000,to=2000000,increment=1000,textvariable=self.vmax,width=12).grid(row=2,column=1,sticky="w")
        ttk.Label(v,text="Encoder").grid(row=3,column=0,sticky="e"); ttk.Combobox(v,textvariable=self.enc,state="readonly",width=12,values=["mp4v","XVID","MJPG","avc1","auto"]).grid(row=3,column=1,sticky="w")

        a=ttk.Labelframe(opts,text="Align & Stitch"); a.grid(row=0,column=1,sticky="nsew",padx=4,pady=2)
        self.align=tk.BooleanVar(value=True); self.flipr=tk.BooleanVar(value=True); self.swaplr=tk.BooleanVar(value=False)
        self.maxs=tk.IntVar(value=128); self.force_split=tk.BooleanVar(value=False); self.auto_split=tk.BooleanVar(value=False)
        self.smooth=tk.IntVar(value=11); self.auto_dec=tk.BooleanVar(value=True); self.edge=tk.IntVar(value=0)
        ttk.Checkbutton(a,text="Auto-detect L/R split",variable=self.auto_split).grid(row=0,column=0,sticky="w")
        ttk.Checkbutton(a,text="Force split at midpoint",variable=self.force_split).grid(row=0,column=1,sticky="w")
        ttk.Checkbutton(a,text="Align channels",variable=self.align).grid(row=1,column=0,sticky="w")
        ttk.Checkbutton(a,text="Flip right",variable=self.flipr).grid(row=1,column=1,sticky="w")
        ttk.Checkbutton(a,text="Swap L/R",variable=self.swaplr).grid(row=2,column=0,sticky="w")
        ttk.Label(a,text="Max shift (px)").grid(row=2,column=1,sticky="e"); ttk.Spinbox(a,from_=0,to=512,textvariable=self.maxs,width=6).grid(row=2,column=2,sticky="w")
        ttk.Label(a,text="Shift smooth (rows)").grid(row=3,column=0,sticky="e"); ttk.Spinbox(a,from_=1,to=51,increment=2,textvariable=self.smooth,width=6).grid(row=3,column=1,sticky="w")
        ttk.Label(a,text="Edge pad (px)").grid(row=3,column=2,sticky="e"); ttk.Spinbox(a,from_=0,to=64,textvariable=self.edge,width=6).grid(row=3,column=3,sticky="w")
        ttk.Checkbutton(a,text="Auto choose flip/swap",variable=self.auto_dec).grid(row=4,column=0,sticky="w")

        c=ttk.Labelframe(opts,text="Color / Preview"); c.grid(row=0,column=2,sticky="nsew",padx=4,pady=2)
        self.cmap=tk.StringVar(value="amber"); self.preview_mode=tk.StringVar(value="compose"); self.show_seam=tk.BooleanVar(value=True)
        ttk.Label(c,text="Color map").grid(row=0,column=0,sticky="e")
        ttk.Combobox(c,textvariable=self.cmap,state="readonly",width=14,
            values=["grayscale","amber","copper","blue","ice","purple","fire","viridis","magma","inferno"]).grid(row=0,column=1,sticky="w")
        ttk.Label(c,text="Preview mode").grid(row=1,column=0,sticky="e")
        ttk.Combobox(c,textvariable=self.preview_mode,state="readonly",width=14,
            values=["compose","left","right","overlay","difference"]).grid(row=1,column=1,sticky="w")
        ttk.Checkbutton(c,text="Show seam",variable=self.show_seam).grid(row=2,column=1,sticky="w")

        act=ttk.Frame(root); act.pack(fill="x", padx=8, pady=(6,8))
        ttk.Button(act,text="Preview frame",command=self._preview).pack(side="left")
        ttk.Button(act,text="Make MP4",command=self._export).pack(side="left", padx=10)
        self.prog_px=ttk.Progressbar(act,length=260,mode="determinate"); self.prog_px.pack(side="left", padx=12)
        self.prev_lbl=ttk.Label(root); self.prev_lbl.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------- common helpers / BG harness -------------
    def _append(self,msg): self.log.insert("end",msg+"\n"); self.log.see("end")
    def _run_bg(self, fn):
        if self._worker and self._worker.is_alive(): return
        if hasattr(self,"prog"): self.prog.start(10)
        if hasattr(self,"prog_px"): self.prog_px.start(10)
        if hasattr(self,"prog_st"): self.prog_st.start(10)
        def work():
            try: fn()
            finally: self._q.put(("done", None))
        self._worker=threading.Thread(target=work,daemon=True); self._worker.start()
    def _poll(self):
        try:
            while True:
                kind,pay=self._q.get_nowait()
                if kind=="log": self._append(pay)
                elif kind=="preview":
                    im=Image.fromarray(pay); 
                    im.thumbnail((self.prev_lbl.winfo_width() or 1000, self.prev_lbl.winfo_height() or 520), Image.NEAREST)
                    self.preview_imgtk=ImageTk.PhotoImage(im); self.prev_lbl.configure(image=self.preview_imgtk)
                elif kind=="spin":
                    # start spinners
                    if pay=="stitch" and hasattr(self,"prog_st"): self.prog_st.start(10)
                elif kind=="done":
                    if hasattr(self,"prog"): self.prog.stop()
                    if hasattr(self,"prog_px"): self.prog_px.stop()
                    if hasattr(self,"prog_st"): self.prog_st.stop()
        except queue.Empty:
            pass
        self.after(100,self._poll)

    # ------------- Preview/Export actions -------------
    def _pick_rows(self):
        p=filedialog.askdirectory(title="Pick rows folder (images)")
        if p: self.rows.set(p)
    def _paths_cfg(self):
        pdir=Path(self.rows.get().strip())
        paths=sorted([str(p) for p in pdir.glob("*.png")]) or sorted([str(p) for p in pdir.glob("*.jpg")])
        cfg={
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
        try:
            import importlib.util
            modp = Path(__file__).parent / "video_exporter.py"
            spec = importlib.util.spec_from_file_location("video_exporter_local", modp)
            vx   = importlib.util.module_from_spec(spec); spec.loader.exec_module(vx)
        except Exception as e:
            return messagebox.showerror("Missing/Bad","video_exporter.py not importable:\n"+str(e))
        pdir, paths, cfg = self._paths_cfg()
        if not paths: return messagebox.showerror("No images","No .png/.jpg found.")
        from PIL import Image as PIm
        arr0=np.array(PIm.open(paths[0])); row_h=int(arr0.shape[0])
        def job():
            try:
                frame, seam, shift, score = vx.build_preview_frame(paths, cfg, row_h, int(self.vh.get()))
                if shift is not None: self._q.put(("log", f"preview: shift={shift:+d}px"))
                self._q.put(("preview", frame))
            except Exception as e:
                self._q.put(("log","ERROR (preview): "+str(e)))
        self._run_bg(job)
    def _export(self):
        try:
            import importlib.util
            modp = Path(__file__).parent / "video_exporter.py"
            spec = importlib.util.spec_from_file_location("video_exporter_local", modp)
            vx   = importlib.util.module_from_spec(spec); spec.loader.exec_module(vx)
        except Exception as e:
            return messagebox.showerror("Missing/Bad","video_exporter.py not importable:\n"+str(e))
        pdir, paths, cfg = self._paths_cfg()
        if not paths: return messagebox.showerror("No images","No .png/.jpg found.")
        out_mp4=str(pdir.parent/(pdir.name+"_waterfall.mp4"))
        self._append("Exporting → "+out_mp4)
        from PIL import Image as PIm
        arr0=np.array(PIm.open(paths[0])); row_h=int(arr0.shape[0])
        def job():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("video_exporter_local", Path(__file__).parent/"video_exporter.py")
                vx   = importlib.util.module_from_spec(spec); spec.loader.exec_module(vx)
                def log(m): self._q.put(("log", m))
                vx.export_waterfall_mp4(paths, cfg, out_mp4, row_h, int(self.vh.get()), int(self.vfps.get()), int(self.vmax.get()), log_func=log)
            except Exception as e:
                self._q.put(("log","ERROR (export): "+str(e)))
        self._run_bg(job)

if __name__=="__main__":
    App().mainloop()
