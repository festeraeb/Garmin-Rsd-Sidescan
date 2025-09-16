#!/usr/bin/env python3
"""
rsd_varuint_probe_safe.py
-------------------------
Windows/OneDrive friendly variant: NO mmap, reads only the bytes needed.
Probes LEB128-style VarUInt sequences at given offsets and (optionally) scans
forward for chained varuints in a small window.

Usage:
  python rsd_varuint_probe_safe.py "C:\\path\\to\\Sonar000.RSD" --offsets 0x60,96,112,160 -o varuint_probes.csv --window 64

Tips on Windows:
  - If your RSD is in OneDrive, right-click it → "Always keep on this device", or
    copy it to a local folder like C:\\Temp before running.
  - Close any app that might have the file open (viewer, editor, etc.).
"""

import argparse
import csv
from pathlib import Path

def read_varuint_le(buf: bytes, off: int, limit: int = 10):
    """
    Decode a LEB128-style VarUInt from 'buf' starting at 'off' (relative to buf).
    Returns (value, length) or (None, 0) if invalid/incomplete.
    """
    val = 0
    shift = 0
    i = off
    for _ in range(limit):
        if i >= len(buf):
            return (None, 0)
        b = buf[i]
        val |= ((b & 0x7F) << shift)
        i += 1
        if (b & 0x80) == 0:  # last byte
            return (val, i - off)
        shift += 7
    return (None, 0)

def main():
    ap = argparse.ArgumentParser(description="Probe VarUInt at specific offsets (no mmap).")
    ap.add_argument("input", help="Path to SonarXXX.RSD")
    ap.add_argument("-o", "--output", default="varuint_probes.csv", help="CSV output path")
    ap.add_argument("--offsets", required=True,
                    help="Comma-separated hex/dec offsets, e.g. 0x60,96,112,160")
    ap.add_argument("--window", type=int, default=64,
                    help="Bytes to scan forward for chained varuints (default 64)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        raise SystemExit(f"Input not found: {src}")

    # Parse offsets list
    offs = []
    for tok in args.offsets.split(","):
        tok = tok.strip()
        try:
            offs.append(int(tok, 0))
        except Exception:
            print(f"Skipping invalid offset token: {tok!r}")

    # Open file normally (no mmap)
    size = src.stat().st_size
    rows = []

    with src.open("rb") as f:
        for off in offs:
            if off < 0 or off >= size:
                rows.append((f"{off:#x}", "", 0, "offset_out_of_range"))
                continue

            # Read just enough bytes for the primary varuint and the forward window
            f.seek(off)
            # read window + 10 extra to allow a longer varuint at the edge
            chunk = f.read(max(10, args.window + 10))

            # Primary probe at 'off' (relative index 0 in chunk)
            val, ln = read_varuint_le(chunk, 0)
            ok = (val is not None and ln > 0)
            rows.append((f"{off:#x}", str(val) if ok else "", ln if ok else 0, "primary"))
            # Now scan forward for chained varuints within window
            if ok:
                p = ln
                limit = min(len(chunk), args.window)
                while p < limit:
                    v2, ln2 = read_varuint_le(chunk, p)
                    if v2 is None or ln2 == 0:
                        break
                    rows.append((f"{off+p:#x}", str(v2), ln2, "chain"))
                    p += ln2

    out = src.with_name(args.output)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["offset_hex", "value", "length_bytes", "kind"])
        w.writerows(rows)

    print(f"Wrote {out} ({len(rows)} rows).")

if __name__ == "__main__":
    main()

