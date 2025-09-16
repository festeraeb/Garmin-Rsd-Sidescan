
#!/usr/bin/env python3
"""
RSD Pattern Lab
---------------
Investigate recurring byte patterns in Garmin RSD files and how they relate
to record headers/trailers. This helps decide whether patterns are padding,
sentinels, or part of a field.

What it does:
  - Finds all record headers (0xB7E9DA86 in either endianness) and trailers (0xF98EACBC).
  - Scans for:
      * A1/B2 alternators: 0xB2A1B2A1 and 0xA1B2A1B2
      * Zero words: 0x00000001, 0x00000002, 0x00000003
      * Float signatures: 0x42480000 (50.0f), 0x3F19999A (~0.6f)  (little-endian)
  - For each hit, records:
      * offset, pattern, alignment (mod 4/8/16),
      * nearest header offsets and distances,
      * alternation run length for A1/B2,
      * small hex context (48 bytes window).
  - Exports CSV + a human-readable TXT summary with histograms by distance/alignment.

Usage:
  python rsd_pattern_lab.py Sonar000.RSD -o Sonar000_lab

Outputs:
  Sonar000_lab.pattern_hits.csv
  Sonar000_lab.report.txt
"""
import argparse
import mmap
from pathlib import Path
import csv
from collections import Counter, defaultdict

HDR_BE = b"\xB7\xE9\xDA\x86"
HDR_LE = b"\x86\xDA\xE9\xB7"
TRL    = b"\xF9\x8E\xAC\xBC"

P_B2A1B2A1 = b"\xB2\xA1\xB2\xA1"
P_A1B2A1B2 = b"\xA1\xB2\xA1\xB2"
P_00000001 = b"\x00\x00\x00\x01"
P_00000002 = b"\x00\x00\x00\x02"
P_00000003 = b"\x00\x00\x00\x03"
# Little-endian float bit patterns:
P_FLOAT_50 = b"\x00\x00\x48\x42"   # 50.0f  (0x42480000 LE)
P_FLOAT_06 = b"\x9A\x99\x19\x3F"   # 0.6f   (0x3F19999A LE)

DEFAULT_START = 0x0   # detect everything

def find_all(data: bytes, token: bytes, start: int = 0):
    pos = start
    while True:
        i = data.find(token, pos)
        if i == -1:
            break
        yield i
        pos = i + 1

def nearest(sorted_list, x):
    """Return (prev, next) neighbors around x from a sorted list."""
    if not sorted_list:
        return (None, None)
    # binary search
    import bisect
    i = bisect.bisect_left(sorted_list, x)
    prev = sorted_list[i-1] if i-1 >= 0 and i-1 < len(sorted_list) else None
    nxt  = sorted_list[i]   if i < len(sorted_list) else None
    return (prev, nxt)

def alt_runlen(data: bytes, off: int):
    """If bytes alternate B2/A1 or A1/B2 starting at off, measure run length (in bytes)."""
    if off >= len(data):
        return 0
    first = data[off]
    if first not in (0xB2, 0xA1):
        return 0
    want = 0xA1 if first == 0xB2 else 0xB2
    n = 1
    i = off + 1
    while i < len(data):
        if data[i] != want:
            break
        n += 1
        want = 0xA1 if want == 0xB2 else 0xB2
        i += 1
    return n

def hexdump_slice(data: bytes, off: int, width: int = 48):
    a = max(0, off - width//2)
    b = min(len(data), off + width//2)
    chunk = data[a:b]
    # simple grouped hex
    hexpairs = " ".join(f"{x:02X}" for x in chunk)
    rel = off - a
    return f"@0x{off:08X}  [{a:#x}:{b:#x}]  rel={rel}\n{hexpairs}\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to .RSD")
    ap.add_argument("-o", "--outbase", default="rsd_lab", help="Output base path (no extension)")
    ap.add_argument("--start", type=lambda x: int(x, 0), default=DEFAULT_START, help="Start offset to scan (default 0x0)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        raise SystemExit(f"Input not found: {src}")

    with src.open("rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        data = mm[:]
        mm.close()

    # Collect headers & trailers
    hdrs = sorted(set(list(find_all(data, HDR_BE, args.start)) + list(find_all(data, HDR_LE, args.start))))
    trls = sorted(set(find_all(data, TRL, args.start)))

    patterns = [
        ("B2A1B2A1", P_B2A1B2A1),
        ("A1B2A1B2", P_A1B2A1B2),
        ("00000001", P_00000001),
        ("00000002", P_00000002),
        ("00000003", P_00000003),
        ("float_50.0", P_FLOAT_50),
        ("float_0.6", P_FLOAT_06),
    ]

    hits = []
    for name, tok in patterns:
        for off in find_all(data, tok, args.start):
            prev_hdr, next_hdr = nearest(hdrs, off)
            prev_trl, next_trl = nearest(trls, off)
            align4 = off % 4
            align8 = off % 8
            align16 = off % 16
            altlen = alt_runlen(data, off) if name in ("B2A1B2A1", "A1B2A1B2") else 0
            hits.append({
                "pattern": name,
                "offset": off,
                "offset_hex": f"0x{off:X}",
                "align4": align4,
                "align8": align8,
                "align16": align16,
                "prev_hdr": prev_hdr if prev_hdr is not None else -1,
                "next_hdr": next_hdr if next_hdr is not None else -1,
                "d_prev_hdr": (off - prev_hdr) if prev_hdr is not None else -1,
                "d_next_hdr": (next_hdr - off) if next_hdr is not None else -1,
                "prev_trl": prev_trl if prev_trl is not None else -1,
                "next_trl": next_trl if next_trl is not None else -1,
                "d_prev_trl": (off - prev_trl) if prev_trl is not None else -1,
                "d_next_trl": (next_trl - off) if next_trl is not None else -1,
                "alt_runlen": altlen,
            })

    outbase = Path(args.outbase)
    csv_path = src.with_name(outbase.name + ".pattern_hits.csv")
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hits[0].keys()) if hits else
                           ["pattern","offset","offset_hex","align4","align8","align16",
                            "prev_hdr","next_hdr","d_prev_hdr","d_next_hdr",
                            "prev_trl","next_trl","d_prev_trl","d_next_trl","alt_runlen"])
        w.writeheader()
        for row in hits:
            w.writerow(row)

    # Build report
    rep = []
    rep.append(f"File: {src.name}")
    rep.append(f"Headers found: {len(hdrs)}   Trailers found: {len(trls)}")
    rep.append(f"Total pattern hits: {len(hits)}")
    # Histograms by pattern & alignment and distance from prev header
    by_pat = defaultdict(list)
    for h in hits:
        by_pat[h["pattern"]].append(h)

    for pname, arr in by_pat.items():
        rep.append("")
        rep.append(f"== Pattern: {pname} ==")
        rep.append(f"Hits: {len(arr)}")
        # Alignment histograms
        rep.append("align4 histogram: " + str(Counter([a['align4'] for a in arr])))
        # Distance-from-prev-header histo (bucket by 16 bytes)
        dists = [a["d_prev_hdr"] for a in arr if a["d_prev_hdr"] >= 0]
        if dists:
            buckets = Counter([(d//16)*16 for d in dists])
            top = buckets.most_common(8)
            rep.append("d_prev_hdr bucket (16B) top bins: " + ", ".join(f"{k}:{v}" for k,v in top))
        # Alternation runs for A1/B2
        if pname in ("B2A1B2A1", "A1B2A1B2"):
            runs = Counter([a["alt_runlen"] for a in arr if a["alt_runlen"]])
            rep.append("alternation run-lengths (bytes) top: " + str(runs.most_common(8)))

        # Add up to 6 context hex snippets
        rep.append("-- Context samples --")
        for s in arr[:6]:
            rep.append(hexdump_slice(data, s["offset"], width=64))

    txt_path = src.with_name(outbase.name + ".report.txt")
    txt_path.write_text("\n".join(rep), encoding="utf-8")

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {txt_path}")

if __name__ == "__main__":
    main()
