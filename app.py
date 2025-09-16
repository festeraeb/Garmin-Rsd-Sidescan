#!/usr/bin/env python3
import os, json, threading, importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE=Path(__file__).resolve().parent
def _import(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
core=_import(HERE/'rsd_core_crc_plus.py','strict_core')
sig=_import(HERE/'rsd_core_signature.py','sig_core')

APP="Garmin RSD Desktop (Adaptive)"
class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP); self.geometry("900x620")
        self.cancel=False; self.out_dir=None; self._build(); self.after(120,self._pump)
    def _build(self):
        pad={'padx':8,'pady':6}; f=ttk.Frame(self); f.pack(fill="both", expand=True)
        self.rsd=tk.StringVar(); ttk.Label(f,text="RSD:").grid(row=0,column=0,sticky="w",**pad)
        ttk.Entry(f,textvariable=self.rsd,width=70).grid(row=0,column=1,sticky="we",**pad)
        ttk.Button(f,text="Browse…",command=self._pick).grid(row=0,column=2,**pad)
        self.outp=tk.StringVar(value=str(Path.home()/ "Garmin_RSD_Runs")); self.run=tk.StringVar(value="run_adaptive")
        ttk.Label(f,text="Output parent:").grid(row=1,column=0,sticky="w",**pad)
        ttk.Entry(f,textvariable=self.outp,width=50).grid(row=1,column=1,sticky="we",**pad)
        ttk.Button(f,text="Browse…",command=self._pick_out).grid(row=1,column=2,**pad)
        ttk.Label(f,text="Run name:").grid(row=2,column=0,sticky="w",**pad); ttk.Entry(f,textvariable=self.run,width=30).grid(row=2,column=1,sticky="w",**pad)
        ttk.Separator(f).grid(row=3,column=0,columnspan=3, sticky="we", padx=6, pady=4)
        ttk.Label(f,text="Mode:").grid(row=3,column=0,sticky="w",**pad)
        self.mode=tk.StringVar(value="Auto (Adaptive)")
        ttk.Combobox(f,textvariable=self.mode,values=["Auto (Adaptive)","Strict","Fast Track (heuristic)"],state="readonly").grid(row=3,column=1,sticky="w",**pad)
        btns=ttk.Frame(f); btns.grid(row=4,column=0,columnspan=3, sticky="we", padx=8, pady=4)
        self.go=ttk.Button(btns,text="Run ▶",command=self._run); self.go.pack(side="left",padx=6)
        self.cancelb=ttk.Button(btns,text="Cancel",command=lambda:setattr(self,'cancel',True),state="disabled"); self.cancelb.pack(side="left",padx=6)
        self.openb=ttk.Button(btns,text="Open output",command=self._open,state="disabled"); self.openb.pack(side="right",padx=6)
        self.pb=ttk.Progressbar(f,orient="horizontal",mode="determinate",maximum=100.0); self.pb.grid(row=5,column=0,columnspan=3, sticky="we", padx=8, pady=4)
        self.log=tk.Text(f,height=14); self.log.grid(row=6,column=0,columnspan=3, sticky="nsew", padx=8, pady=6); f.rowconfigure(6,weight=1); f.columnconfigure(1,weight=1)
    def _pick(self):
        p=filedialog.askopenfilename(title="Select Garmin .RSD", filetypes=[("Garmin RSD","*.RSD"),("All files","*.*")])
        if p: self.rsd.set(p)
    def _pick_out(self):
        d=filedialog.askdirectory(title="Select output parent folder")
        if d: self.outp.set(d)
    def _open(self):
        if self.out_dir and Path(self.out_dir).exists():
            try: os.startfile(self.out_dir)
            except Exception: import webbrowser; webbrowser.open(self.out_dir)
    def _progress(self,pct,msg): self.pb['value']=pct; self.log.insert("end", msg+"\n"); self.log.see("end")
    def _pump(self): self.after(150,self._pump)
    def _run(self):
        rsd=self.rsd.get().strip(); outp=self.outp.get().strip(); run=self.run.get().strip() or "run_adaptive"
        if not rsd or not Path(rsd).exists(): messagebox.showerror("Missing RSD","Pick a valid .RSD"); return
        Path(outp).mkdir(parents=True, exist_ok=True); out_dir=str(Path(outp)/run); Path(out_dir).mkdir(parents=True, exist_ok=True); self.out_dir=out_dir
        mode=self.mode.get(); self.go['state']='disabled'; self.cancelb['state']='normal'; self.pb['value']=0; self.log.delete("1.0","end"); self.cancel=False
        def bg():
            try:
                rows_total=0; out={}
                if mode in ("Auto (Adaptive)","Strict"):
                    core.set_progress_hook(lambda p,m: self._progress(p,m)); core.set_cancel_hook(lambda: self.cancel)
                    try:
                        s=core.build_rows_and_assets(rsd, out_dir, {"CRC_MODE":"warn"})
                        rows_total = int(s.get("rows",0))+int(s.get("rows_ss",0))+int(s.get("rows_dv",0))
                        out.update(s)
                    except Exception as e:
                        self._progress(0, f"Strict failed: {e}")
                        rows_total=0
                if mode in ("Auto (Adaptive)","Fast Track (heuristic)"):
                    if rows_total < 10:
                        self._progress(80,"Strict yielded few rows; running heuristic…")
                        rules_path=HERE/'parsing_rules.json'
                        rules=json.loads(rules_path.read_text()) if rules_path.exists() else {}
                        res=sig.parse_file(Path(rsd), Path(out_dir)/(Path(rsd).stem+"_signature"), rules)
                        rows_total=max(rows_total, int(res.get("points",0)))
                        out["heur_csv"]=res.get("csv")
                self._progress(100,"Done"); self.openb['state']='normal'
                self.log.insert("end", f"Rows/points: {rows_total}\n")
            finally:
                self.go['state']='normal'; self.cancelb['state']='disabled'
        threading.Thread(target=bg,daemon=True).start()

if __name__=="__main__":
    App().mainloop()
