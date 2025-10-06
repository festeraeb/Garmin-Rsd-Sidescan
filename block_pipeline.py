
import csv
from dataclasses import dataclass
from typing import List, Tuple, Iterator, Optional
import numpy as np

@dataclass
class Record:
    idx: int
    channel: int
    seq: int
    lat: float
    lon: float
    depth: float
    samples: int

def read_records(csv_path: str) -> List[Record]:
    """Read a simple CSV with columns: idx,channel,seq,lat,lon,depth,samples"""
    recs: List[Record] = []
    with open(csv_path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            recs.append(Record(
                idx=int(row["idx"]),
                channel=int(row["channel"]),
                seq=int(row["seq"]),
                lat=float(row.get("lat", "0") or 0),
                lon=float(row.get("lon", "0") or 0),
                depth=float(row.get("depth", "0") or 0),
                samples=int(row.get("samples","512") or 512),
            ))
    return recs

def split_channels(recs: List[Record]) -> Tuple[List[Record], List[Record]]:
    ch4 = [r for r in recs if r.channel == 4]
    ch5 = [r for r in recs if r.channel == 5]
    ch4.sort(key=lambda r: r.seq)
    ch5.sort(key=lambda r: r.seq)
    return ch4, ch5

def pair_blocks(ch4: List[Record], ch5: List[Record], block_size: int, start: int=0) -> Iterator[Tuple[List[Record], List[Record]]]:
    """Yield blocks of ch4/ch5, keeping order by seq. Uses min available for each side."""
    i = start
    while i < min(len(ch4), len(ch5)):
        yield ch4[i:i+block_size], ch5[i:i+block_size]
        i += block_size

# --- Simulated rendering and alignment (placeholder) ---
def render_row(record: Record, width: int=1024, height: int=48) -> np.ndarray:
    """Simulate a sidescan-like grayscale row for the record."""
    # Gradient + sine bands; different per-channel so alignment can do something
    x = np.linspace(0, 1, width, dtype=np.float32)
    base = (np.sin((x*10 + (0.1 if record.channel==4 else 0.12))*np.pi)*0.5 + 0.5)
    # Add a wedge based on seq for visual motion
    wedge = np.clip((x - (record.seq % 100)/100.0), 0, 1)
    img = (0.3*base + 0.7*wedge).astype(np.float32)
    row = (img * 255).astype(np.uint8)[None, :]  # 1 x W
    row = np.repeat(row, height, axis=0)         # H x W
    return row

def compose_block(ch4_block: List[Record], ch5_block: List[Record], width: int=1024, row_h: int=48, gap: int=4, shift: int=0) -> np.ndarray:
    """Compose a stitched strip for the two blocks, with optional horizontal shift on ch5."""
    # Render rows
    left_rows = [render_row(r, width=width, height=row_h) for r in ch4_block]
    right_rows = [render_row(r, width=width, height=row_h) for r in ch5_block]
    # Apply shift to right side (positive shift moves content right -> pad left)
    if shift > 0:
        right_rows = [np.hstack([np.zeros((row_h, shift), dtype=np.uint8), rr[:, :width-shift]]) for rr in right_rows]
    elif shift < 0:
        s = -shift
        right_rows = [np.hstack([rr[:, s:], np.zeros((row_h, s), dtype=np.uint8)]) for rr in right_rows]
    # Stack vertically (interleave left|gap|right per ping)
    strip_rows = []
    for l, r in zip(left_rows, right_rows):
        gap_arr = np.zeros((row_h, gap), dtype=np.uint8)
        strip_rows.append(np.hstack([l, gap_arr, r]))
    strip = np.vstack(strip_rows)  # (row_h*block, width*2+gap) after we mirror right -> already rendered same width
    return strip

def estimate_shift(ch4_block: List[Record], ch5_block: List[Record], width: int=1024, row_h: int=48, search: int=40) -> int:
    """Very simple correlation-based shift estimator on synthetic rows."""
    import numpy as np
    # Use middle row
    mid = min(len(ch4_block), len(ch5_block)) // 2
    l = render_row(ch4_block[mid], width, row_h)[row_h//2]
    r = render_row(ch5_block[mid], width, row_h)[row_h//2]
    # Try shifts in [-search, search]
    best_s, best_sc = 0, -1e9
    for s in range(-search, search+1):
        if s >= 0:
            lseg = l[:, :width-s]
            rseg = r[:, s:]
        else:
            s2 = -s
            lseg = l[:, s2:]
            rseg = r[:, :width-s2]
        # score = dot(l,r)
        sc = float((lseg * rseg).sum())
        if sc > best_sc:
            best_sc, best_s = sc, s
    return int(best_s)
