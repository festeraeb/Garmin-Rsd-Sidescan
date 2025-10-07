#!/usr/bin/env python3
"""Glue to run parse engines and write CSV rows.

This simplified glue supports calling run_engine(engine, rsd_path, out_dir, ...)
and provides a small CLI wrapper for testing.
"""
import argparse
import os
import sys
from typing import Tuple


def _run_one(engine_name: str, inp: str, out_dir: str, max_records=None, progress_every=2000, 
           progress_seconds=2.0, verbose=False, scan_type="auto", channel="all") -> Tuple[int,str,str]:
    # Import engine module dynamically
    if verbose:
        print(f"[engine_glue] Starting {engine_name} parser on {inp}")
        
    if engine_name == 'classic':
        from engine_classic_varstruct import parse_rsd as engine_parse
    elif engine_name == 'nextgen':
        from engine_nextgen_syncfirst import parse_rsd as engine_parse
    else:
        raise ValueError('Unknown engine')

    os.makedirs(out_dir, exist_ok=True)
    
    # First parse the RSD file
    if verbose:
        print(f"[engine_glue] Parsing {inp}...")
        
    n, csv_path, log_path = engine_parse(inp, out_dir, max_records=max_records)
    
    # Now generate PNGs from sonar data
    if verbose:
        print(f"[engine_glue] Generating images from {csv_path}...")
    
    try:
        from render_accel import process_record_images
        img_dir = os.path.join(out_dir, 'images')
        os.makedirs(img_dir, exist_ok=True)
        process_record_images(csv_path, img_dir, scan_type=scan_type, channel=channel)
    except Exception as e:
        print(f"[engine_glue] Warning: Image generation failed: {str(e)}")
    
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
    ap.add_argument("--verbose", action="store_true", help="Enable verbose debug output")
    ap.add_argument("--scan-type", default="auto", choices=["auto", "sidescan", "downscan", "chirp"],
                   help="Type of scan data to parse")
    ap.add_argument("--channel", default="all", help="Channel ID to parse (all, auto, or specific ID)")
    args = ap.parse_args()

    inp = args.input
    out_dir = args.out
    prefer = args.prefer
    scan_type = args.scan_type
    channel = args.channel

    if prefer == "auto-nextgen-then-classic":
        # Try nextgen first, fall back to classic if it fails
        try:
            if args.verbose:
                print("[engine_glue] Trying nextgen parser first...")
            n, p, l = _run_one("nextgen", inp, out_dir, args.max, verbose=args.verbose)
            total = n; paths = [p]; logs = [l]
            if args.verbose:
                print(f"[engine_glue] Nextgen parser succeeded with {n} records")
        except Exception as e:
            if args.verbose:
                print(f"[engine_glue] Nextgen parser failed: {str(e)}")
                print("[engine_glue] Falling back to classic parser...")
            n, p, l = _run_one("classic", inp, out_dir, args.max, verbose=args.verbose)
            total = n; paths = [p]; logs = [l]
    elif prefer in ("classic", "nextgen"):
        if args.verbose:
            print(f"[engine_glue] Using {prefer} parser as specified")
        n, p, l = _run_one(prefer, inp, out_dir, args.max, verbose=args.verbose)
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
