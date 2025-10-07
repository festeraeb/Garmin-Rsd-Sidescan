#!/usr/bin/env python3
# engine_glue.py — glue that imports parsers from ../engine and writes CSV

from pathlib import Path
import json, csv, sys, importlib, traceback

HERE = Path(__file__).resolve().parent
ENGINE_DIR = (HERE.parent / "engine").resolve()

# --- Make ../engine importable for core_shared, rows_from_csv_rsd, etc. ---
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

def _rows_to_csv_stream(rows_iter, csv_path: Path, progress=None):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    c = 0
    with csv_path.open("w", newline='', encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["ofs","channel_id","seq","time_ms","lat","lon","depth_m","sample_cnt","sonar_ofs","sonar_size"])
        for r in rows_iter:
            w.writerow([
                getattr(r, "ofs", ""),
                getattr(r, "channel_id", ""),
                getattr(r, "seq", ""),
                getattr(r, "time_ms", ""),
                "" if getattr(r, "lat", None) is None else f"{r.lat:.8f}",
                "" if getattr(r, "lon", None) is None else f"{r.lon:.8f}",
                "" if getattr(r, "depth_m", None) is None else f"{r.depth_m:.3f}",
                getattr(r, "sample_cnt", "") or "",
                getattr(r, "sonar_ofs", "") or "",
                getattr(r, "sonar_size", "") or ""
            ])
            c += 1
            if progress and c % 250 == 0:
                progress(None, f"CSV rows written: {c}")
    if progress: progress(None, f"CSV rows written: {c}")
    return c

def run_engine(engine, rsd_path, csv_out, limit_rows=0, progress=None):
    out = Path(csv_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    def hook(pct, msg):
        if progress:
            progress(pct, msg)

    # Import engines AFTER sys.path tweak so their internal imports (core_shared, etc.) work.
    try:
        classic = importlib.import_module("engine_classic_varstruct")
        parse_classic = getattr(classic, "parse_rsd_records_classic")
        classic_src = Path(classic.__file__).resolve()
    except Exception as e:
        parse_classic = None
        classic_src = f"(load failed: {e})"

    try:
        nextgen = importlib.import_module("engine_nextgen_syncfirst")
        parse_nextgen = getattr(nextgen, "parse_rsd_records_nextgen")
        nextgen_src = Path(nextgen.__file__).resolve()
    except Exception as e:
        parse_nextgen = None
        nextgen_src = f"(load failed: {e})"

    e = str(engine).lower()
    if e == "classic":
        if not parse_classic:
            raise ImportError(f"Classic engine not available: {classic_src}")
        if progress: progress(None, f"Using Classic engine @ {classic_src}")
        rows = parse_classic(rsd_path, limit_rows or 0, progress=hook)
        _rows_to_csv_stream(rows, out, progress=hook)
        return str(out)

    if e in ("nextgen","next-gen"):
        if not parse_nextgen:
            raise ImportError(f"Next-Gen engine not available: {nextgen_src}")
        if progress: progress(None, f"Using Next-Gen engine @ {nextgen_src}")
        rows = parse_nextgen(rsd_path, limit_rows or 0, progress=hook)
        _rows_to_csv_stream(rows, out, progress=hook)
        return str(out)

    if e == "both":
        a = run_engine("classic", rsd_path, out.with_name(out.stem+"_classic.csv"), limit_rows, progress)
        b = run_engine("nextgen", rsd_path, out.with_name(out.stem+"_nextgen.csv"), limit_rows, progress)
        return json.dumps({"classic":a, "nextgen":b})

    raise ValueError("engine must be Classic / Next-Gen / Both")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Run Garmin RSD parser and stream rows to CSV")
    ap.add_argument("--input", required=True, help="Input .RSD (or zip)")
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--prefer", choices=["auto","classic","nextgen","both"], default="auto",
                    help="Engine preference: auto (NextGen→Classic), classic, nextgen, or both")
    ap.add_argument("--limit", type=int, default=0, help="Optional row limit for quick tests")
    args = ap.parse_args()

    inpath = args.input
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{Path(inpath).stem}_records.csv"

    def log(pct, msg):
        pct_txt = "" if pct is None else f"{pct*100:5.1f}% "
        print(pct_txt + msg, flush=True)

    try:
        if args.prefer == "classic":
            res = run_engine("classic", inpath, out, limit_rows=args.limit, progress=log)
            print(f"CSV written: {res}", flush=True)
        elif args.prefer in ("nextgen","next-gen"):
            res = run_engine("nextgen", inpath, out, limit_rows=args.limit, progress=log)
            print(f"CSV written: {res}", flush=True)
        elif args.prefer == "both":
            res = run_engine("both", inpath, out, limit_rows=args.limit, progress=log)
            print(f"CSV written (both): {res}", flush=True)
        else:
            print(f"Engine dir = {ENGINE_DIR}", flush=True)
            print("Auto: trying Next-Gen first…", flush=True)
            try:
                res = run_engine("nextgen", inpath, out, limit_rows=args.limit, progress=log)
                print(f"CSV written (nextgen): {res}", flush=True)
            except Exception as e:
                print(f"Next-Gen failed ({e}); trying Classic…", flush=True)
                res = run_engine("classic", inpath, out, limit_rows=args.limit, progress=log)
                print(f"CSV written (classic): {res}", flush=True)
    except Exception:
        print("ERROR running engine_glue.py:", flush=True)
        traceback.print_exc()
        sys.exit(1)
