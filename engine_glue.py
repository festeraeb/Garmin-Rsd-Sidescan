#!/usr/bin/env python3
"""Glue to run parse engines and write CSV rows.

This simplified glue supports calling run_engine(engine, rsd_path, out_dir, ...)
and provides a small CLI wrapper for testing.
"""
import argparse
import os
import sys
from typing import Tuple


def _run_one(engine_name: str, inp: str, out_dir: str, max_records=None, progress_every=2000, progress_seconds=2.0) -> Tuple[int,str,str]:
    # Import engine module dynamically
    if engine_name == 'classic':
        from engine_classic_varstruct import parse_rsd as engine_parse
    elif engine_name == 'nextgen':
        from engine_nextgen_syncfirst import parse_rsd as engine_parse
    else:
        raise ValueError('Unknown engine')

    os.makedirs(out_dir, exist_ok=True)
    n, csv_path, log_path = engine_parse(inp, out_dir, max_records=max_records)
    return n, csv_path, log_path


def run_engine(engine: str, rsd_path: str, out_dir: str, limit_rows: int | None = None) -> Tuple[int,str,str]:
    return _run_one(engine, rsd_path, out_dir, max_records=limit_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="RSD file or sample CSV")
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--prefer", default="auto-nextgen-then-classic", 
                   choices=["auto-nextgen-then-classic","classic","nextgen","both"],
                   help="Parser preference")
    ap.add_argument("--max", type=int, default=None, help="Optional cap for fast tests")
    args = ap.parse_args()

    inp = args.input
    out_dir = args.out
    prefer = args.prefer

    if prefer == "auto-nextgen-then-classic":
        # Try nextgen first, fall back to classic if it fails
        try:
            n, p, l = _run_one("nextgen", inp, out_dir, args.max)
            total = n; paths = [p]; logs = [l]
        except Exception as e:
            print(f"Nextgen parser failed: {str(e)}, trying classic...")
            n, p, l = _run_one("classic", inp, out_dir, args.max)
            total = n; paths = [p]; logs = [l]
    elif prefer in ("classic", "nextgen"):
        n, p, l = _run_one(prefer, inp, out_dir, args.max)
        total = n; paths = [p]; logs = [l]
    elif prefer == "both":
        n1, p1, l1 = _run_one("classic", inp, os.path.join(out_dir, "classic"), args.max)
        n2, p2, l2 = _run_one("nextgen", inp, os.path.join(out_dir, "nextgen"), args.max)
        total = n1 + n2; paths = [p1,p2]; logs = [l1,l2]
    else:
        n2, p2, l2 = _run_one("nextgen", inp, out_dir, args.max)
        if n2 == 0:
            n1, p1, l1 = _run_one("classic", inp, out_dir, args.max)
            total = n1; paths = [p1]; logs = [l1]
        else:
            total = n2; paths = [p2]; logs = [l2]

    if total == 0:
        print("[engine_glue] ERROR: parsed 0 records. See log:", " | ".join(logs))
        sys.exit(2)

    print(f"[engine_glue] OK: wrote {total} records -> {', '.join(paths)}")
    sys.exit(0)


if __name__ == '__main__':
    main()
