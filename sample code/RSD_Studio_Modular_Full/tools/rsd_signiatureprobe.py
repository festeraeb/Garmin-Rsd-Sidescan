#!/usr/bin/env python3
import argparse, os, json, mmap, struct, collections
from datetime import datetime

def human(n):
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024.0: return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def scan_file(path, max_scan_mb=256, align=16, step=4, min_count=200, endian="auto"):
    size = os.path.getsize(path)
    scan_bytes = min(size, max_scan_mb * 1024 * 1024)
    with open(path, "rb") as f, mmap.mmap(f.fileno(), length=scan_bytes, access=mmap.ACCESS_READ) as mm:
        counts_be = collections.Counter(); counts_le = collections.Counter()
        start = 0
        if align > 1:
            start = (start + (align - (start % align))) % align
        for off in range(start, scan_bytes - 4, step):
            word = mm[off:off+4]
            if len(word) < 4: break
            counts_be[struct.unpack(">I", word)[0]] += 1
            counts_le[struct.unpack("<I", word)[0]] += 1
    counters = [("be", counts_be), ("le", counts_le)] if endian=="auto" else ( [("be", counts_be)] if endian=="be" else [("le", counts_le)] )
    candidates = []
    for tag, cnt in counters:
        for word, c in cnt.most_common():
            if c < min_count: break
            candidates.append((tag, word, c))
    results = []
    with open(path, "rb") as f, mmap.mmap(f.fileno(), length=scan_bytes, access=mmap.ACCESS_READ) as mm:
        for tag, word, c in candidates:
            positions = []
            start = 0
            if align > 1:
                start = (start + (align - (start % align))) % align
            for off in range(start, scan_bytes - 4, step):
                v = struct.unpack(">I" if tag=="be" else "<I", mm[off:off+4])[0]
                if v == word:
                    positions.append(off)
            if len(positions) < 3: continue
            spans = [b - a for a, b in zip(positions, positions[1:]) if b > a]
            if not spans: continue
            hist = collections.Counter(spans)
            mode_span, _ = max(hist.items(), key=lambda kv: kv[1])
            results.append({
                "endianness": tag,
                "signature_uint32": word,
                "signature_hex": f"0x{word:08X}",
                "count_in_sample": len(positions),
                "typical_record_span": int(mode_span),
                "span_min": int(min(spans)),
                "span_max": int(max(spans)),
                "align_bytes": align,
                "step_bytes": step,
            })
    return size, scan_bytes, results

def save_artifacts(path, results, out_dir):
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{base}_signature_probe.csv")
    json_path = os.path.join(out_dir, f"{base}_signature_probe.json")
    import csv
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["signature_hex","endianness","count_in_sample","typical_record_span","span_min","span_max","align_bytes","step_bytes"])
        for r in results:
            w.writerow([r["signature_hex"], r["endianness"], r["count_in_sample"], r["typical_record_span"], r["span_min"], r["span_max"], r["align_bytes"], r["step_bytes"]])
    with open(json_path, "w") as f:
        json.dump({"source_file": os.path.basename(path), "generated_utc": datetime.utcnow().isoformat()+"Z", "items": results}, f, indent=2)
    return csv_path, json_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rsd_path")
    ap.add_argument("--out-dir", default="probe_out")
    ap.add_argument("--max-scan-mb", type=int, default=256)
    ap.add_argument("--align", type=int, default=16)
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--min-count", type=int, default=200)
    ap.add_argument("--endian", choices=["auto","be","le"], default="auto")
    args = ap.parse_args()
    size, scanned, results = scan_file(args.rsd_path, args.max_scan_mb, args.align, args.step, args.min_count, args.endian)
    print(f"File size: {human(size)}; scanned: {human(scanned)}")
    print(f"Candidates: {len(results)}")
    for r in results[:12]:
        print(f"- {r['signature_hex']} [{r['endianness']}] span={r['typical_record_span']} min={r['span_min']} max={r['span_max']} count={r['count_in_sample']}")
    csv_path, json_path = save_artifacts(args.rsd_path, results, args.out_dir)
    print("Wrote:", csv_path); print("Wrote:", json_path)

if __name__ == "__main__":
    main()
