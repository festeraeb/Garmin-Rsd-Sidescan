
#!/usr/bin/env python3
import argparse, mmap, csv
from pathlib import Path

def read_varuint_le(data: bytes, off: int, limit: int = 10):
    val = 0
    shift = 0
    i = off
    for _ in range(limit):
        if i >= len(data):
            return (None, 0)
        b = data[i]
        val |= ((b & 0x7F) << shift)
        i += 1
        if (b & 0x80) == 0:
            return (val, i - off)
        shift += 7
    return (None, 0)

def main():
    ap = argparse.ArgumentParser(description="Probe VarUInt sequences at given offsets.")
    ap.add_argument("input", help="Path to SonarXXX.RSD")
    ap.add_argument("-o", "--output", default="varuint_probes.csv")
    ap.add_argument("--offsets", help="Comma-separated hex/dec offsets (e.g. 0x60,96,112,160)")
    ap.add_argument("--window", type=int, default=64)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        raise SystemExit(f"Input not found: {src}")

    offs = []
    if args.offsets:
        for tok in args.offsets.split(","):
            tok = tok.strip()
            try:
                offs.append(int(tok, 0))
            except Exception:
                pass

    with src.open("rb") as f:
        mm = mmap.mmap(f.fileno(), 0)
        data = mm[:]
        mm.close()

    rows = []
    for off in offs:
        val, ln = read_varuint_le(data, off)
        ok = (val is not None and ln > 0)
        rows.append((f"{off:#x}", val if ok else "", ln if ok else 0))
        if ok:
            p = off + ln
            end = min(len(data), off + args.window)
            while p < end:
                v2, ln2 = read_varuint_le(data, p)
                if v2 is None or ln2 == 0:
                    break
                rows.append((f"{p:#x}", v2, ln2))
                p += ln2

    out = src.with_name(args.output)
    with out.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["offset_hex","value","length_bytes"]); w.writerows(rows)
    print(f"Wrote {out} ({len(rows)} rows).")

if __name__ == "__main__":
    main()
