#!/usr/bin/env python3
# rsd_core_signature.py — tolerant heuristic extractor
from pathlib import Path
from typing import Dict
import mmap, struct

MAGIC_REC_HDR_LE = b"\x86\xDA\xE9\xB7"

def set_progress_hook(fn): pass
def set_cancel_hook(fn): pass

def _mapunit_to_deg(x:int)->float: return x*(360.0/float(1<<32))

def parse_file(input_path: Path, outbase: Path, rules: dict | None = None) -> Dict:
    input_path = Path(input_path); outbase = Path(outbase)
    outdir = outbase.parent; outdir.mkdir(parents=True, exist_ok=True)
    pts = 0
    with open(input_path,'rb') as f:
        mm = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
        try:
            data = mm[:]
        finally:
            mm.close()
    offs=[]; i=0
    while True:
        j=data.find(MAGIC_REC_HDR_LE, i)
        if j==-1: break
        offs.append(j); i=j+1
    coords=[]
    for h in offs:
        a=h+64; b=min(len(data), h+512); i=a
        while i+8<=b:
            lat_i=struct.unpack_from("<i", data, i)[0]
            lon_i=struct.unpack_from("<i", data, i+4)[0]
            lat=_mapunit_to_deg(lat_i); lon=_mapunit_to_deg(lon_i)
            if 30.0<=lat<=60.0 and -110.0<=lon<=-50.0:
                coords.append((lat,lon)); pts+=1; break
            i+=4
    csv_path = outdir / (outbase.stem + "_signature.csv")
    with open(csv_path,"w",encoding="utf-8") as fp:
        fp.write("lat_deg,lon_deg\n")
        for lat,lon in coords: fp.write(f"{lat:.8f},{lon:.8f}\n")
    return {"points": pts, "csv": str(csv_path)}
