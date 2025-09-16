#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
import importlib.util
from multiprocessing import Process, Queue

HERE=Path(__file__).resolve().parent

def _import(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

core = _import(HERE/'rsd_core_crc_plus.py', 'strict_core')
sig  = _import(HERE/'rsd_core_signature.py', 'sig_core')

def _run_strict_worker(rsd: str, out_dir: str, cfg: dict, q: Queue):
    try:
        core.set_progress_hook(lambda p,m: None); core.set_cancel_hook(lambda: False)
        s = core.build_rows_and_assets(rsd, out_dir, cfg)
        q.put({"ok": True, "summary": s})
    except Exception as e:
        q.put({"ok": False, "err": str(e)})

def run_strict_with_timeout(rsd: Path, out_dir: Path, cfg: dict, timeout_s: int = 90):
    q = Queue()
    p = Process(target=_run_strict_worker, args=(str(rsd), str(out_dir), cfg, q))
    p.start(); p.join(timeout_s)
    if p.is_alive():
        p.terminate()
        try: p.join(5)
        except Exception: pass
        return {"ok": False, "timeout": True}
    return q.get() if not q.empty() else {"ok": False, "err": "no result"}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("rsd")
    ap.add_argument("--force-heuristic", action="store_true")
    ap.add_argument("--timeout", type=int, default=90)
    args=ap.parse_args()

    rsd=Path(args.rsd).resolve()
    out_dir=rsd.parent/(rsd.stem+"_out"); out_dir.mkdir(parents=True, exist_ok=True)

    rows_total=0; strict_summary={}

    if not args.force_heuristic:
        cfg=dict(CRC_MODE='warn')
        res=run_strict_with_timeout(rsd, out_dir, cfg, timeout_s=args.timeout)
        if res.get("ok"):
            strict_summary=res["summary"]
            rows_total = int(strict_summary.get("rows",0)) + int(strict_summary.get("rows_ss",0)) + int(strict_summary.get("rows_dv",0))
        else:
            print("[one_test] strict failed/timed out; using heuristic…", file=sys.stderr)

    if args.force_heuristic or rows_total < 10:
        rules_path=HERE/'parsing_rules.json'
        rules=json.loads(rules_path.read_text()) if rules_path.exists() else {}
        res=sig.parse_file(rsd, out_dir/(rsd.stem+"_signature"), rules)
        rows_total=max(rows_total, int(res.get("points",0)))

    (out_dir/"one_test_summary.json").write_text(json.dumps({"rows_total": rows_total, "strict": strict_summary}, indent=2), encoding="utf-8")
    print(f"[one_test] Done. rows_total={rows_total} → {out_dir}")

if __name__ == "__main__":
    main()
