#!/usr/bin/env python3
from __future__ import annotations
from typing import Sequence, Optional
import numpy as np
from pathlib import Path

LEFT_TOKENS  = ("_l","-l"," left","left_","ch0","ss-l","port")
RIGHT_TOKENS = ("_r","-r"," right","right_","ch1","ss-r","starboard")

def is_left_name(name: str) -> bool:  return any(t in name.lower() for t in LEFT_TOKENS)
def is_right_name(name: str) -> bool: return any(t in name.lower() for t in RIGHT_TOKENS)

def xcorr_shift(a: np.ndarray, b: np.ndarray, max_shift: int) -> int:
    a1 = a.astype(np.float32); b1 = b.astype(np.float32)
    if a1.ndim==3: a1 = a1.mean(axis=2)
    if b1.ndim==3: b1 = b1.mean(axis=2)
    a1 = (a1 - a1.mean())/(a1.std()+1e-6); b1 = (b1 - b1.mean())/(b1.std()+1e-6)
    sa = a1.mean(axis=0); sb = b1.mean(axis=0)
    best_s, best_v = 0, -1e9
    for s in range(-int(max_shift), int(max_shift)+1):
        if s>=0: aa, bb = sa[s:], sb[:len(sa)-s]
        else:    aa, bb = sa[:s], sb[-s:]
        m = len(aa)
        if m < max(8, int(0.05*len(sa))): continue
        v = float((aa*bb).sum() / ((aa@aa)**0.5 * (bb@bb)**0.5 + 1e-6))
        if v > best_v: best_v, best_s = v, s
    return int(best_s)

def apply_shift(img: np.ndarray, shift: int) -> np.ndarray:
    h, w = img.shape[:2]
    if shift == 0: return img
    if shift > 0:
        out = np.zeros((h, w+shift) + (() if img.ndim==2 else (img.shape[2],)), dtype=img.dtype)
        out[:, shift:shift+w] = img; return out[:, :w]
    out = np.zeros((h, w+(-shift)) + (() if img.ndim==2 else (img.shape[2],)), dtype=img.dtype)
    out[:, :w] = img; return out[:, -shift:]

def compose_lr(L: np.ndarray, R: np.ndarray, flip_right: bool, do_align: bool, max_shift: int, swap_lr: bool) -> np.ndarray:
    if flip_right: R = np.flip(R, axis=1)
    if swap_lr: L, R = R, L
    if do_align:
        s = xcorr_shift(L, R, max_shift=max_shift)
        R = apply_shift(R, s)
    h = min(L.shape[0], R.shape[0]); L = L[:h]; R = R[:h]
    return np.hstack([L, R])

def find_lr_indices(names: Sequence[str]) -> Optional[tuple[int,int]]:
    left  = [i for i,n in enumerate(names) if is_left_name(n)]
    right = [i for i,n in enumerate(names) if is_right_name(n)]
    if left and right: return left[-1], right[-1]
    return None