#!/usr/bin/env python3
# rsd_core_crc_plus.py — strict core (scanner/parsers fixed to skip magic & padding, JSON rules)
import mmap, struct, logging, json
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List
from pathlib import Path

logging.getLogger().setLevel(logging.INFO)

_progress_hook = None
_cancel_hook = None
def set_progress_hook(fn): 
    global _progress_hook; _progress_hook = fn
def set_cancel_hook(fn):
    global _cancel_hook; _cancel_hook = fn
def _progress(pct, msg):
    if _progress_hook:
        try: _progress_hook(float(pct), str(msg))
        except Exception: pass
def _cancelled():
    return bool(_cancel_hook and _cancel_hook())

# ------------- Rules (parsing_rules.json) -------------
PAD_SKIP_DEFAULT = True
SCAN_STEP_DEFAULT = 1
MAGIC_REC_HDR_DEFAULT = 0xB7E9DA86
MAGIC_REC_TRL_DEFAULT = 0xF98EACBC

PAD_SKIP = PAD_SKIP_DEFAULT
SCAN_STEP = SCAN_STEP_DEFAULT
MAGIC_REC_HDR = MAGIC_REC_HDR_DEFAULT
MAGIC_REC_TRL = MAGIC_REC_TRL_DEFAULT

try:
    _rules_path = Path(__file__).with_name("parsing_rules.json")
    if _rules_path.exists():
        _RULES = json.loads(_rules_path.read_text(encoding="utf-8"))
        h = _RULES.get("heuristics", {})
        PAD_SKIP = bool(h.get("pad_skip", _RULES.get("pad_skip", PAD_SKIP_DEFAULT)))
        SCAN_STEP = int(h.get("scan_step", _RULES.get("scan_step", SCAN_STEP_DEFAULT)))
        m = _RULES.get("magic", {})
        rh = m.get("record_header", None)
        rt = m.get("record_trailer", None)
        if rh is not None:
            MAGIC_REC_HDR = int(rh, 0) if isinstance(rh, str) else int(rh)
        if rt is not None:
            MAGIC_REC_TRL = int(rt, 0) if isinstance(rt, str) else int(rt)
except Exception:
    pass

MAGIC_REC_HDR_LE = MAGIC_REC_HDR.to_bytes(4, "little", signed=False)
MAGIC_REC_TRL_LE = MAGIC_REC_TRL.to_bytes(4, "little", signed=False)

# ------------- CRC & Varint helpers -------------
def _crc32_custom(data: bytes) -> int:
    poly=0x04C11DB7; crc=0
    for b in data:
        crc ^= (int(b)<<24) & 0xFFFFFFFF
        for _ in range(8):
            crc = ((crc<<1)^poly)&0xFFFFFFFF if (crc & 0x80000000) else (crc<<1)&0xFFFFFFFF
    rev=0; tmp=crc
    for _ in range(32): rev=(rev<<1)|(tmp&1); tmp>>=1
    return (rev ^ 0xFFFFFFFF) & 0xFFFFFFFF

def _read_varuint_from(mv, pos, limit) -> Tuple[int,int]:
    res=0; shift=0
    while pos<limit:
        b=mv[pos]; pos+=1; res |= (b & 0x7F) << shift
        if not (b & 0x80): return res, pos
        shift += 7
        if shift > 35: break
    raise ValueError("VarUInt overflow")

def _zigzag_to_int32(u:int)->int: return (u>>1) ^ (-(u & 1))
def _read_varint_from(mv,pos,limit)->Tuple[int,int]:
    u,pos=_read_varuint_from(mv,pos,limit); return _zigzag_to_int32(u),pos

# Safe unpackers
def _u32(b: bytes) -> int: return struct.unpack("<I", b[:4])[0] if len(b)>=4 else 0
def _u16(b: bytes) -> int: return struct.unpack("<H", b[:2])[0] if len(b)>=2 else 0
def _i32(b: bytes) -> int: return struct.unpack("<i", b[:4])[0] if len(b)>=4 else 0

def _parse_varstruct(mv, pos, limit, crc_mode="warn") -> Tuple[Dict[int,bytes], int]:
    start=pos
    n,pos=_read_varuint_from(mv,pos,limit)
    if n<0 or n>20000: raise ValueError(f"Unreasonable field count: {n}")
    fields={}
    for _ in range(n):
        key,pos=_read_varuint_from(mv,pos,limit)
        fn=key>>3; lc=key&7
        if lc==7:
            vlen,pos=_read_varuint_from(mv,pos,limit)
            if vlen<0 or pos+vlen>limit: raise ValueError("Value exceeds buffer")
        else:
            vlen=lc
            if pos+vlen>limit: raise ValueError("Fixed-length value overruns buffer")
        endv=pos+vlen
        fields[fn]=bytes(mv[pos:endv]); pos=endv
    if pos+4>limit: raise ValueError("Truncated before CRC")
    crc_read=struct.unpack_from("<I", mv, pos)[0]; data=bytes(mv[start:pos]); pos+=4
    if crc_mode=="strict" and _crc32_custom(data)!=crc_read:
        raise ValueError("CRC mismatch")
    return fields,pos

def _mapunit_to_deg(x:int)->float: return x*(360.0/float(1<<32))

@dataclass
class RSDRecord:
    ofs:int; seq:int; time_ms:int; data_size:int
    lat:Optional[float]; lon:Optional[float]; depth_m:Optional[float]

def build_rows_and_assets(input_path: str, out_dir: str, cfg: Dict) -> Dict:
    CRC_MODE=str(cfg.get("CRC_MODE","warn")).lower()
    src=Path(input_path); out_p=Path(out_dir); out_p.mkdir(parents=True, exist_ok=True)
    size=src.stat().st_size
    recs: List[RSDRecord]=[]
    with src.open("rb") as f:
        mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ); mv=memoryview(mm)
        try:
            i=0; end=size-4; last=-1
            while i<=end:
                if _cancelled(): break
                pct=int((i/max(1,size))*100)
                if pct!=last: _progress(pct, f"Scan @ 0x{i:08X}"); last=pct

                if mv[i:i+4]!=MAGIC_REC_HDR_LE:
                    i += SCAN_STEP; continue

                rec_start=i; pos=i+4  # skip 4-byte magic
                try:
                    hdr,pos=_parse_varstruct(mv,pos,size,CRC_MODE)
                    seq=_u32(hdr.get(2,b"")); t_ms=_u32(hdr.get(5,b"")); data_size=_u16(hdr.get(4,b""))

                    body_start=pos
                    try:
                        body,pos=_parse_varstruct(mv,pos,size,CRC_MODE)
                    except Exception:
                        body={}; pos=body_start+max(0,data_size)

                    lat=lon=None; depth=None
                    if 9 in body: lat=_mapunit_to_deg(_i32(body[9]))
                    if 10 in body: lon=_mapunit_to_deg(_i32(body[10]))
                    if 1 in body and len(body[1])>0:
                        try:
                            v,_=_read_varint_from(memoryview(body[1]),0,len(body[1])); depth=v/1000.0
                        except Exception: pass

                    recs.append(RSDRecord(rec_start, seq, t_ms, data_size, lat, lon, depth))

                    pos_end=body_start+max(0,data_size)
                    if pos_end+4<=size and mv[pos_end:pos_end+4]==MAGIC_REC_TRL_LE:
                        pos_end+=4
                    if PAD_SKIP:
                        while pos_end+1<size:
                            b0=mv[pos_end]; b1=mv[pos_end+1]
                            if (b0==0xA1 and b1==0xB2) or (b0==0xB2 and b1==0xA1):
                                pos_end+=2
                            else: break
                    i=pos_end
                    continue
                except Exception as e:
                    logging.warning(f"Record parse error at 0x{rec_start:08X}: {e}")
                    i += SCAN_STEP
                    continue
        finally:
            try: mv.release()
            except Exception: pass
            mm.close()

    csv_path=out_p/(src.stem+"_strict_track.csv")
    with csv_path.open("w",encoding="utf-8") as fp:
        fp.write("ofs_hex,seq,time_ms,data_size,lat_deg,lon_deg,depth_m\n")
        for r in recs:
            fp.write(f"0x{r.ofs:08X},{r.seq},{r.time_ms},{r.data_size},"
                     f"{'' if r.lat is None else f'{r.lat:.8f}'},"
                     f"{'' if r.lon is None else f'{r.lon:.8f}'},"
                     f"{'' if r.depth_m is None else f'{r.depth_m:.3f}'}\n")
    logging.info(f"[strict] Done. Records={len(recs)} CSV={csv_path.name}")
    return {"rows": len(recs), "rows_ss": 0, "rows_dv": 0, "csv": str(csv_path), "out_dir": str(out_p)}
