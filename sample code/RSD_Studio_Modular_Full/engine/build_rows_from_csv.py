
#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, csv, json
from PIL import Image

def _i(v, d=0):
    try: return int(float(v))
    except: return d

def _f(v, d=None):
    try: return float(v)
    except: return d

def _payload(rsd, row):
    o = _i(row.get("sonar_ofs")); s = _i(row.get("sonar_size"))
    if s <= 0: return b""
    rsd.seek(o); return rsd.read(s)

def _strip_to_png(payload: bytes, width: int, out_png: Path):
    if width <= 0: width = 256
    if not payload: payload = b"\x00" * width
    if len(payload) < width:
        k = (width // max(1, len(payload))) + 1; payload = (payload * k)[:width]
    elif len(payload) > width: payload = payload[:width]
    Image.frombytes("L", (width, 1), payload).save(out_png)

def build(csv_path: Path, rsd_path: Path, out_root: Path, channels=None, limit=0, progress=None):
    out_root.mkdir(parents=True, exist_ok=True)
    n=0
    with open(rsd_path, "rb") as rsd:
        with csv_path.open("r", encoding="utf-8", newline="") as fp:
            r = csv.DictReader(fp)
            for row in r:
                ch = _i(row.get("channel_id"), -1)
                if ch < 0: continue
                if channels and ch not in channels: continue
                w  = _i(row.get("sample_cnt")) or min(4096, max(32, _i(row.get("sonar_size"), 256)))
                key = f"{_i(row.get('seq')):06d}-ofs{_i(row.get('ofs'))}"
                ch_dir = out_root / f"ch{ch:02d}"; ch_dir.mkdir(parents=True, exist_ok=True)
                png = ch_dir / f"{key}.png"
                meta = {
                    "ofs": _i(row.get("ofs")), "seq": _i(row.get("seq")), "time_ms": _i(row.get("time_ms")),
                    "channel_id": ch, "lat": _f(row.get("lat")), "lon": _f(row.get("lon")),
                    "depth_m": _f(row.get("depth_m")), "sample_cnt": _i(row.get("sample_cnt")),
                    "sonar_ofs": _i(row.get("sonar_ofs")), "sonar_size": _i(row.get("sonar_size")),
                    "width": w, "png": str(png)
                }
                _strip_to_png(_payload(rsd, row), w, png)
                (ch_dir / f"{key}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                n+=1
                if progress and n % 250 == 0: progress(None, f"rows built: {n}")
                if limit and n>=limit: break
    if progress: progress(None, f"rows built total: {n}")
    print(f"Built {n} row strips to {out_root}")
    return n

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--rsd", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--channels", default=""); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    chans=None
    if a.channels.strip():
        try: chans={int(x) for x in a.channels.split(",")}
        except: chans=None
    build(Path(a.csv), Path(a.rsd), Path(a.out), channels=chans, limit=a.limit)

if __name__ == "__main__":
    main()
