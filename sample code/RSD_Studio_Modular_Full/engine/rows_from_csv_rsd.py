#!/usr/bin/env python3
from __future__ import annotations
import csv, sys, shutil
from pathlib import Path
from typing import Optional, Callable
import numpy as np
from PIL import Image, UnidentifiedImageError

# ---------- IO helpers ----------
def _is_good_file(p: Path) -> bool:
    try:
        if not p.is_file() or p.stat().st_size == 0:
            return False
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:
        return False

def _safe_open_gray(p: Path):
    try:
        with Image.open(p) as im:
            return np.array(im.convert("L"))
    except Exception:
        return None

def _discover_images(rows_dir: Path):
    pats = ("*.png","*.PNG","*.jpg","*.JPG","*.jpeg","*.JPEG")
    imgs=[]
    for pat in pats:
        imgs.extend(rows_dir.rglob(pat))
    imgs = [p for p in imgs if _is_good_file(p)]
    imgs.sort()
    return imgs

# ---------- math helpers ----------
def _to8(a: np.ndarray)->np.ndarray:
    if a is None:
        return None
    if a.dtype==np.uint8: return a
    f=a.astype(np.float32); mn,mx=np.nanmin(f),np.nanmax(f)
    if not np.isfinite(mn) or not np.isfinite(mx) or mx<=mn: f=np.clip(f,0,1)
    else: f=np.clip((f-mn)/(mx-mn),0,1)
    return (f*255+0.5).astype(np.uint8)

def _pad_width(img: np.ndarray, width:int)->np.ndarray:
    h,w=img.shape[:2]
    if w==width: return img
    if w>width:  return img[:,:width] if img.ndim==2 else img[:,:width,:]
    out=np.zeros((h,width),img.dtype) if img.ndim==2 else np.zeros((h,width,img.shape[2]),img.dtype)
    out[:,:w]=img; return out

def _phase_corr_shift(L: np.ndarray, R: np.ndarray, max_shift:int=128) -> int:
    try:
        if L is None or R is None: return 0
        if L.size==0 or R.size==0: return 0
        h=min(L.shape[0],R.shape[0]); wL=L.shape[1]; wR=R.shape[1]
        if h<8 or wL<8 or wR<8: return 0
        band=slice(max(0,h//3),min(h,2*h//3))
        A=L[band, -min(128,wL):].astype(np.float32)
        B=R[band,  :min(128,wR)].astype(np.float32)
        if A.size==0 or B.size==0: return 0
        A-=A.mean() if A.size else 0; B-=B.mean() if B.size else 0
        W=1<<int(np.ceil(np.log2(max(A.shape[1],B.shape[1])*2))) if max(A.shape[1],B.shape[1])>0 else 0
        if W<=0: return 0
        def fpad(X): out=np.zeros((X.shape[0],W),np.float32); out[:,:X.shape[1]]=X; return out
        FA=np.fft.rfft(fpad(A),axis=1); FB=np.fft.rfft(fpad(B),axis=1)
        # fix typo: compute FB correctly        FB=np.fft.rfft(fpad(B),axis=1)
        pc=np.fft.irfft((FA*np.conj(FB))/(np.abs(FA*np.conj(FB))+1e-6),axis=1)
        prof=pc.mean(axis=0); peak=int(np.nanargmax(prof))
        if peak>prof.size//2: peak-=prof.size
        return int(np.clip(peak,-max_shift,max_shift))
    except Exception:
        return 0

def _stitch_pair(L: np.ndarray, R: np.ndarray, shift:int, water_px:int=2, flip_right:bool=True, swap_lr:bool=False)->np.ndarray:
    if L is None or R is None:
        return None
    h=min(L.shape[0],R.shape[0]); L=L[:h]; R=R[:h]
    if swap_lr: L, R = R, L
    if flip_right: R=np.fliplr(R)
    if shift>0:  L=np.hstack([np.zeros((h,shift),L.dtype), L[:,:-shift]])
    elif shift<0: R=np.hstack([np.zeros((h,-shift),R.dtype), R[:,:shift]])
    W=max(L.shape[1],R.shape[1]); L=_pad_width(L,W); R=_pad_width(R,W)
    if L.ndim==2: L=np.stack([L]*3,2)
    if R.ndim==2: R=np.stack([R]*3,2)
    seam=np.full((h, max(0,water_px), 3), 255, np.uint8) if water_px>0 else np.zeros((h,0,3),np.uint8)
    return np.hstack([L,seam,R])

def stitch_from_csv(rows_dir: str, csv_path: str, out_dir: str,
                    key_every:int=50, max_shift:int=128,
                    flip_right:bool=True, swap_lr:bool=False, water_px:int=2,
                    log: Optional[Callable[[str],None]]=None):
    log = log or (lambda m: None)
    rows = Path(rows_dir); csvp = Path(csv_path); outp = Path(out_dir)
    if not rows.is_dir(): raise FileNotFoundError(f"Rows not found: {rows}")
    if not csvp.exists(): raise FileNotFoundError(f"CSV not found: {csvp}")
    imgs=_discover_images(rows)
    if not imgs: raise RuntimeError(f"No image rows found in {rows}")

    # Build channel lists by CSV order, pairing images by index
    chL=[]; chR=[]; seqL=[]; seqR=[]
    with csvp.open() as f:
        R=csv.DictReader(f)
        for i,row in enumerate(R):
            if i>=len(imgs): break
            ch=(row.get("channel_id","") or "").strip()
            seq=(row.get("seq","") or row.get("sequence","") or "")
            if ch=="4": chL.append(imgs[i]); seqL.append(int(seq) if str(seq).isdigit() else i)
            elif ch=="5": chR.append(imgs[i]); seqR.append(int(seq) if str(seq).isdigit() else i)

    n=min(len(chL),len(chR))
    if n==0: raise RuntimeError("Could not build ch4/ch5 lists (CSV/images out of sync?)")
    outp.mkdir(parents=True, exist_ok=True)
    log(f"Found ch4={len(chL)} ch5={len(chR)} -> pairing {n} rows")

    last_shift=0
    for i in range(n):
        L=_to8(_safe_open_gray(chL[i])); R=_to8(_safe_open_gray(chR[i]))
        if L is None or R is None:
            log(f"skip i={i}: unreadable image(s)")
            continue
        if (i % max(1,key_every)) == 0:
            last_shift=_phase_corr_shift(L,R,max_shift)
            log(f"keyframe {i}: shift={last_shift:+d}px")
        comp=_stitch_pair(L,R,last_shift, water_px=water_px, flip_right=flip_right, swap_lr=swap_lr)
        if comp is None:
            log(f"skip i={i}: failed compose")
            continue
        Image.fromarray(comp).save(outp/f"row_{i:06d}.png")
        if i and (i%500)==0: log(f"{i}/{n} stitched; shift={last_shift:+d}px")
    log(f"Done. Wrote stitched rows to {outp}")

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(description="Stitch per-channel (ch4+ch5) rows by CSV order.")
    ap.add_argument("--rows", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--key-every", type=int, default=50)
    ap.add_argument("--max-shift", type=int, default=128)
    ap.add_argument("--flip-right", type=int, default=1)
    ap.add_argument("--swap-lr", type=int, default=0)
    ap.add_argument("--water", type=int, default=2)
    a=ap.parse_args()
    stitch_from_csv(a.rows, a.csv, a.out,
                    key_every=a.key_every, max_shift=a.max_shift,
                    flip_right=bool(a.flip_right), swap_lr=bool(a.swap_lr), water_px=a.water,
                    log=print)


