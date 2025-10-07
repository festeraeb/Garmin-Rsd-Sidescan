
#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re, json, argparse

TERMS = [
    r"0x0?500", r"0x5033", r"\bSV\b", r"\bCV\b", r"Side ?Vu", r"Down ?Vu",
    r"CHIRP", r"FFT", r"decim", r"sample[_ ]?rate", r"Hann", r"Kaiser", r"GT5[46]"
]

def scan_file(p: Path, ctx=80):
    text = p.read_text(encoding="utf-8", errors="ignore")
    hits=[]
    for term in TERMS:
        for m in re.finditer(term, text, flags=re.IGNORECASE):
            j0=max(0, m.start()-ctx); j1=min(len(text), m.end()+ctx)
            hits.append({"term":term, "span":[m.start(), m.end()], "context":text[j0:j1]})
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    indir = Path(args.indir)
    out = Path(args.out)
    results = {}
    for p in sorted(indir.glob("*")):
        if p.suffix.lower() not in (".txt",".csv",".log",".hex"):
            continue
        try:
            hits = scan_file(p)
            if hits:
                results[p.name]=hits
        except Exception:
            pass
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote hints: {out}  files_with_hits={len(results)}")

if __name__ == "__main__":
    main()
