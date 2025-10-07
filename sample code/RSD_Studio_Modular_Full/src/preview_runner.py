
from __future__ import annotations
from pathlib import Path
import csv, json, threading, time
from PIL import Image
import numpy as np
import sys
import os
from typing import List, Dict, Any, Tuple, Optional

# Add engine directory to path for imports
HERE = Path(__file__).resolve().parent
ENGINE_DIR = (HERE.parent / "engine").resolve()
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

try:
    from block_pipeline import BlockProcessor, get_suggested_channel_pairs, get_transducer_info
except ImportError:
    # Fallback if block_pipeline not available
    BlockProcessor = None

def _int(v, d=0):
    try: return int(float(v))
    except: return d

def _load_rows(csv_path: Path, channels, seq_start, window):
    by_ch = {ch:[] for ch in channels}
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        r = csv.DictReader(fp)
        for row in r:
            try:
                ch = _int(row.get("channel_id"))
                if ch not in by_ch: continue
                seq = _int(row.get("seq"))
                if seq < seq_start or seq >= seq_start+window: continue
                by_ch[ch].append(row)
            except: continue
    for ch in by_ch: by_ch[ch].sort(key=lambda rr:_int(rr.get("seq")))
    return by_ch

def _payload(rsd, row):
    sofs = _int(row.get("sonar_ofs")); ssize = _int(row.get("sonar_size"))
    if ssize<=0: return b""
    rsd.seek(sofs); return rsd.read(ssize)

def _strip(payload: bytes, width: int):
    if width<=0: width=256
    if not payload: payload = b"\x00"*width
    if len(payload)<width:
        times = (width//max(1,len(payload)))+1
        payload = (payload*times)[:width]
    elif len(payload)>width:
        payload = payload[:width]
    return payload

def _median_sample_cnt(rows):
    sc=[_int(r.get("sample_cnt")) for r in rows if _int(r.get("sample_cnt"))>0]
    sc.sort()
    return sc[len(sc)//2] if sc else 256

def compose_preview(csv_path: Path, rsd_path: Path, chX:int, chY:int,
                    seq_start:int, window:int, offset:int=0,
                    flipX:bool=False, flipY:bool=False, swapXY:bool=False,
                    out_png: Path=None):
    """Legacy preview function - kept for compatibility"""
    out_png = out_png or csv_path.with_name(csv_path.stem+"_preview.png")
    by_ch = _load_rows(csv_path, [chX, chY], seq_start, window)
    if swapXY: chX, chY = chY, chX
    rowsX = by_ch.get(chX,[]); rowsY = by_ch.get(chY,[])
    H = max(len(rowsX), len(rowsY))
    if H==0: raise RuntimeError("No rows in selected window.")
    wx = _median_sample_cnt(rowsX); wy = _median_sample_cnt(rowsY)
    W = max(wx, wy)
    img = Image.new("RGB", (W, H), (0,0,0)); px = img.load()
    with open(rsd_path, "rb") as rsd:
        for i in range(H):
            if 0<=i<len(rowsX):
                bx = _payload(rsd, rowsX[i]); bx = bx[::-1] if flipX else bx
                sx = _strip(bx, wx)
                for x,v in enumerate(sx):
                    px[x,i]=(v,0,0)   # X = red
            j = i + offset
            if 0<=j<len(rowsY):
                by = _payload(rsd, rowsY[j]); by = by[::-1] if flipY else by
                sy = _strip(by, wy)
                for x,v in enumerate(sy):
                    r,g,b = px[x,i]; g2=min(255,g+v); b2=min(255,b+v)
                    px[x,i]=(r,g2,b2)  # Y = cyan
    img.save(out_png)
    meta={"channels":[chX,chY],"seq_start":seq_start,"window":window,"offset":offset,
          "flipX":flipX,"flipY":flipY,"swapXY":swapXY,"png":str(out_png)}
    out_png.with_suffix(".json").write_text(json.dumps(meta,indent=2), encoding="utf-8")
    return meta

class LivePreviewRunner:
    """Enhanced preview runner with block-based processing and live updates"""
    
    def __init__(self, csv_path: str, rsd_path: str, update_callback=None):
        self.csv_path = Path(csv_path)
        self.rsd_path = Path(rsd_path)
        self.update_callback = update_callback
        self.processor = None
        self.is_running = False
        self.current_block = 0
        self.total_blocks = 0
        
        # Initialize block processor if available
        if BlockProcessor:
            try:
                self.processor = BlockProcessor(str(csv_path), str(rsd_path))
                self.available_channels = self.processor.get_available_channels()
                self.transducer_info = self.processor.config
            except Exception as e:
                print(f"Warning: Could not initialize block processor: {e}")
                self.processor = None
                self.available_channels = []
                self.transducer_info = {}
        else:
            self.available_channels = []
            self.transducer_info = {}
    
    def get_channel_info(self):
        """Get information about available channels and suggested pairs"""
        if self.processor:
            return {
                'channels': self.available_channels,
                'suggested_pairs': self.transducer_info.get('suggested_pairs', []),
                'scan_type': self.transducer_info.get('scan_type', 'unknown'),
                'transducer_serial': self.transducer_info.get('transducer_serial')
            }
        else:
            # Fallback: read channels from CSV
            channels = set()
            try:
                with open(self.csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('channel_id'):
                            channels.add(int(row['channel_id']))
            except:
                pass
            
            channel_list = sorted(list(channels))
            suggested_pairs = []
            if len(channel_list) >= 2:
                suggested_pairs = [(channel_list[0], channel_list[1])]
            
            return {
                'channels': channel_list,
                'suggested_pairs': suggested_pairs,
                'scan_type': 'unknown',
                'transducer_serial': None
            }
    
    def start_live_preview(self, left_channel: int, right_channel: int,
                          auto_align: bool = True, manual_shift: int = 0,
                          flip_left: bool = False, flip_right: bool = False,
                          swap_channels: bool = False):
        """Start live preview with block-based processing"""
        if self.is_running:
            return False
        
        if swap_channels:
            left_channel, right_channel = right_channel, left_channel
        
        self.is_running = True
        threading.Thread(target=self._preview_worker, 
                        args=(left_channel, right_channel, auto_align, manual_shift,
                             flip_left, flip_right), daemon=True).start()
        return True
    
    def stop_live_preview(self):
        """Stop live preview"""
        self.is_running = False
    
    def _preview_worker(self, left_channel: int, right_channel: int,
                       auto_align: bool, manual_shift: int,
                       flip_left: bool, flip_right: bool):
        """Worker thread for live preview generation"""
        if not self.processor:
            if self.update_callback:
                self.update_callback("Error: Block processor not available", None)
            return
        
        try:
            blocks = list(self.processor.process_channel_pair(
                left_channel, right_channel, auto_align, manual_shift,
                flip_left, flip_right))
            
            self.total_blocks = len(blocks)
            
            for i, result in enumerate(blocks):
                if not self.is_running:
                    break
                
                self.current_block = i
                
                # Convert numpy array to PIL Image for display
                if result['image'] is not None:
                    preview_img = Image.fromarray(result['image'], mode='L')
                    
                    # Create metadata for display
                    meta = {
                        'block_index': result['block_index'],
                        'shift': result['shift'],
                        'confidence': result['confidence'],
                        'left_records': result['left_records'],
                        'right_records': result['right_records'],
                        'channels': f"Ch{left_channel:02d} / Ch{right_channel:02d}",
                        'progress': f"{i+1}/{self.total_blocks}"
                    }
                    
                    if self.update_callback:
                        self.update_callback(meta, preview_img)
                
                # Small delay to allow GUI updates
                time.sleep(0.1)
                
        except Exception as e:
            if self.update_callback:
                self.update_callback(f"Preview error: {str(e)}", None)
        finally:
            self.is_running = False
    
    def export_preview_sequence(self, output_dir: str, left_channel: int, right_channel: int,
                               **kwargs) -> List[str]:
        """Export complete preview sequence as images"""
        if not self.processor:
            raise RuntimeError("Block processor not available")
        
        return self.processor.export_block_results(
            output_dir, left_channel, right_channel, **kwargs)
    
    def generate_quick_preview(self, left_channel: int, right_channel: int,
                              block_index: int = 0, **kwargs) -> Image.Image:
        """Generate a single preview image for specified block"""
        if not self.processor:
            raise RuntimeError("Block processor not available")
        
        blocks = list(self.processor.process_channel_pair(
            left_channel, right_channel, **kwargs))
        
        if block_index >= len(blocks):
            raise IndexError(f"Block index {block_index} out of range (0-{len(blocks)-1})")
        
        result = blocks[block_index]
        if result['image'] is not None:
            return Image.fromarray(result['image'], mode='L')
        else:
            raise RuntimeError("Failed to generate preview image")

# Utility functions for GUI integration
def get_preview_channels(csv_path: str):
    """Get suggested channel pairs for preview"""
    try:
        if BlockProcessor:
            return get_suggested_channel_pairs(csv_path)
        else:
            # Fallback
            channels = set()
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('channel_id'):
                        channels.add(int(row['channel_id']))
            
            channel_list = sorted(list(channels))
            if len(channel_list) >= 2:
                return [(channel_list[0], channel_list[1])]
            return []
    except:
        return []

def get_scan_info(csv_path: str):
    """Get scan type and transducer information"""
    try:
        if BlockProcessor:
            return get_transducer_info(csv_path)
        else:
            return {'scan_type': 'unknown', 'transducer_serial': None}
    except:
        return {'scan_type': 'unknown', 'transducer_serial': None}
