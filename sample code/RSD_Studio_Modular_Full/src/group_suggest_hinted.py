
# group_suggest_hinted.py — suggest channel pairs with firmware hints influence
from __future__ import annotations
from pathlib import Path
import csv, json
from collections import defaultdict

PRIORITY_TERMS = ["SideVu","SV","DownVu","CV","GT54","GT56","CHIRP"]

def _read_meta(csv_path: Path, limit:int=150000):
    by_ch = defaultdict(list)
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        r = csv.DictReader(fp)
        for i,row in enumerate(r):
            if i>=limit: break
            try:
                ch = int(float(row.get("channel_id") or 0))
                seq = int(float(row.get("seq") or i))
                sc  = int(float(row.get("sample_cnt") or 0))
                sz  = int(float(row.get("sonar_size") or 0))
            except: continue
            by_ch[ch].append((seq, sc, sz))
    for ch in by_ch: by_ch[ch].sort(key=lambda t:t[0])
    return by_ch

def _co_occurrence_score(a, b):
    sa = {t[0] for t in a}; sb = {t[0] for t in b}
    inter = len(sa & sb)
    if not a or not b: return 0.0
    ma = sorted(t[1] for t in a)[len(a)//2] if a else 0
    mb = sorted(t[1] for t in b)[len(b)//2] if b else 0
    sim = 1.0/(1.0+abs(ma-mb))
    return inter * sim

def _estimate_offset(a, b, max_shift:int=20):
    if not a or not b: return 0
    da = {t[0]:t[2] for t in a}
    db = {t[0]:t[2] for t in b}
    common = sorted(set(da)&set(db))
    if len(common)<10: return 0
    xs = [da[s] for s in common]; ys = [db[s] for s in common]
    ax = sum(xs)/len(xs); ay = sum(ys)/len(ys)
    xs = [x-ax for x in xs]; ys = [y-ay for y in ys]
    best_k, best = 0, -1e18
    for k in range(-max_shift, max_shift+1):
        num=denx=deny=0.0
        for i in range(len(common)):
            j=i+k
            if j<0 or j>=len(common): continue
            x=xs[i]; y=ys[j]
            num+=x*y; denx+=x*x; deny+=y*y
        if denx>0 and deny>0:
            corr = num/((denx**0.5)*(deny**0.5))
            if corr>best:
                best, best_k = corr, k
    return best_k

def _hint_boost(hints: dict) -> float:
    if not hints: return 1.0
    # crude: any priority term present boosts score
    txt = json.dumps(hints).lower()
    boost = 1.0
    for term in PRIORITY_TERMS:
        if term.lower() in txt: boost += 0.25
    return boost

def suggest(csv_path: str, hints_json: str|None=None):
    p = Path(csv_path)
    hints = None
    if hints_json and Path(hints_json).exists():
        try:
            hints = json.loads(Path(hints_json).read_text(encoding="utf-8"))
        except Exception:
            hints = None
    by_ch = _read_meta(p)
    chans = sorted(by_ch.keys())
    pairs = []
    boost = _hint_boost(hints)
    for i,c1 in enumerate(chans):
        for c2 in chans[i+1:]:
            score = _co_occurrence_score(by_ch[c1], by_ch[c2]) * boost
            if score<=0: continue
            off = _estimate_offset(by_ch[c1], by_ch[c2])
            pairs.append({"channels":[c1,c2],"score":score,"offset":off})
    pairs.sort(key=lambda d:d["score"], reverse=True)
    default = pairs[0] if pairs else None
    return {"channels":chans, "pairs":pairs, "default":default, "boost":boost}
