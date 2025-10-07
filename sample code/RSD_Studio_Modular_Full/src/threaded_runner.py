
from __future__ import annotations
from pathlib import Path
import os, sys, threading, subprocess, queue, csv

def start_parse_and_rows(root, log_func, input_path: str, out_dir: str,
                         prefer: str="auto", limit_rows: int=0,
                         preview_channels: list[int] | None = None,
                         preview_only: bool = True):
    runner = _ThreadedRunner(root, log_func, Path(input_path), Path(out_dir),
                             prefer, limit_rows, preview_channels or [])
    runner.start(preview_only=preview_only)
    return runner

class _ThreadedRunner:
    def __init__(self, root, log, input_path: Path, out_dir: Path,
                 prefer: str, limit_rows: int, preview_channels: list[int]):
        self.root = root; self.log = log
        self.input = input_path; self.out = out_dir
        self.prefer = prefer; self.limit = int(limit_rows or 0)
        self.q = queue.Queue(); self._polling = False
        here = Path(__file__).resolve().parent
        self.src_dir = here
        self.engine_dir = (here.parent / "engine").resolve()
        self.glue = (self.src_dir / "engine_glue.py").resolve()
        self.rows_builder = (self.engine_dir / "build_rows_from_csv.py").resolve()
        self.stitcher = (self.engine_dir / "rows_from_csv_rsd.py").resolve()
        self.make_video = (self.engine_dir / "make_video_from_stitch.py").resolve()
        self.build_kml  = (self.engine_dir / "build_kml_from_csv.py").resolve()
        self.preview_channels = preview_channels
        self.detected_channels=[]

    def start(self, preview_only: bool=True):
        self.out.mkdir(parents=True, exist_ok=True)
        self._log(f"[thread] Engine dir = {self.engine_dir}")
        threading.Thread(target=self._run_pipeline, kwargs={"preview_only": preview_only}, daemon=True).start()
        if not self._polling:
            self._polling = True
            self._poll_queue()

    def _log(self, line: str): self.q.put(line)

    def _poll_queue(self):
        while not self.q.empty():
            try: self.log(self.q.get_nowait())
            except queue.Empty: break
        try: self.root.after(100, self._poll_queue)
        except Exception: threading.Timer(0.1, self._poll_queue).start()

    def _run_pipeline(self, preview_only: bool):
        if not self._run_parse(): return
        if not self._run_build_rows(): return
        self._run_stitch_preview()
        if not preview_only:
            self._run_render_video_and_kml()

    def _run_parse(self) -> bool:
        csv_out = (self.out / f"{self.input.stem}_records.csv")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.engine_dir) + os.pathsep + env.get("PYTHONPATH","")
        cmd = [sys.executable, str(self.glue), "--input", str(self.input), "--out", str(self.out), "--prefer", self.prefer]
        if self.limit: cmd += ["--limit", str(self.limit)]
        self._log("[parse] " + " ".join(map(str, cmd)))
        try:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1) as proc:
                for line in proc.stdout: self._log(line.rstrip("\n"))
                rc = proc.wait()
            if rc != 0: self._log(f"[parse] ERROR exit {rc}"); return False
        except Exception as e:
            self._log(f"[parse] exception: {e!r}"); return False
        if not csv_out.exists():
            self._log(f"[parse] finished but CSV missing: {csv_out}"); return False
        # report channels
        try:
            chans=set()
            with csv_out.open("r", encoding="utf-8", newline="") as fp:
                r = csv.DictReader(fp)
                for row in r:
                    ch=row.get("channel_id")
                    try: chans.add(int(float(ch)))
                    except: pass
            if chans: self._log("[parse] channels present: " + ", ".join(f"ch{c:02d}" for c in sorted(chans)))
            self.detected_channels = sorted(chans)
        except Exception:
            self.detected_channels = []
        return True

    def _run_build_rows(self) -> bool:
        csv_path  = (self.out / f"{self.input.stem}_records.csv")
        rows_root = (self.out / f"{self.input.stem}_rows")
        rows_root.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.engine_dir) + os.pathsep + env.get("PYTHONPATH","")
        chans = self.preview_channels or self.detected_channels
        chan_arg = ",".join(str(c) for c in chans) if chans else ""
        cmd = [sys.executable, str(self.rows_builder), "--csv", str(csv_path), "--rsd", str(self.input), "--out", str(rows_root)]
        if chan_arg: cmd += ["--channels", chan_arg]
        self._log("[rows] " + " ".join(map(str, cmd)))
        try:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1) as proc:
                for line in proc.stdout: self._log(line.rstrip("\n"))
                rc = proc.wait()
            if rc != 0: self._log(f"[rows] ERROR exit {rc}"); return False
        except Exception as e:
            self._log(f"[rows] exception: {e!r}"); return False
        return True

    def _run_stitch_preview(self):
        csv_path  = (self.out / f"{self.input.stem}_records.csv")
        rows_root = (self.out / f"{self.input.stem}_rows")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.engine_dir) + os.pathsep + env.get("PYTHONPATH","")
        chans = self.preview_channels or self.detected_channels or []
        if not chans:
            self._log("[stitch] no channels selected/detected; skipping.")
            return
        for ch in chans:
            ch_dir = rows_root / f"ch{ch:02d}"
            out_st = self.out / f"{self.input.stem}_stitch_ch{ch:02d}"
            out_st.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(self.stitcher), "--rows", str(ch_dir), "--csv", str(csv_path), "--out", str(out_st)]
            self._log("[stitch] " + " ".join(map(str, cmd)))
            try:
                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1) as proc:
                    for line in proc.stdout: self._log(line.rstrip("\n"))
                    rc = proc.wait()
                self._log(f"[stitch] ch{ch:02d} exit {rc}")
            except Exception as e:
                self._log(f"[stitch] exception for ch{ch:02d}: {e!r}")

    def _run_render_video_and_kml(self):
        csv_path  = (self.out / f"{self.input.stem}_records.csv")
        chans = self.preview_channels or getattr(self, "detected_channels", []) or []
        if not chans:
            self._log("[render] no channels; skip video/KML")
            return
        ch = chans[0]
        stitched = self.out / f"{self.input.stem}_stitch_ch{ch:02d}"
        video_out  = self.out / f"{self.input.stem}_ch{ch:02d}.mp4"
        kml_out    = self.out / f"{self.input.stem}.kml"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.engine_dir) + os.pathsep + env.get("PYTHONPATH","")

        # Video
        cmd_v = [sys.executable, str(self.make_video), "--frames", str(stitched), "--out", str(video_out), "--fps", "30"]
        self._log("[video] " + " ".join(map(str, cmd_v)))
        try:
            with subprocess.Popen(cmd_v, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1) as proc:
                for line in proc.stdout: self._log(line.rstrip("\n"))
                rc = proc.wait()
            self._log(f"[video] exit {rc}")
        except Exception as e:
            self._log(f"[video] exception: {e!r}")

        # KML
        cmd_k = [sys.executable, str(self.build_kml), "--csv", str(csv_path), "--out", str(kml_out)]
        self._log("[kml] " + " ".join(map(str, cmd_k)))
        try:
            with subprocess.Popen(cmd_k, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1) as proc:
                for line in proc.stdout: self._log(line.rstrip("\n"))
                rc = proc.wait()
            self._log(f"[kml] exit {rc}")
        except Exception as e:
            self._log(f"[kml] exception: {e!r}")
