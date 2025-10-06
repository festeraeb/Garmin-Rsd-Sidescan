#!/usr/bin/env python3
"""Classic engine - strict CRC checking and conservative failure handling.

This parser uses strict CRC checking and fails early on malformed records.
See engine_nextgen_syncfirst.py for a more tolerant implementation.
"""
import os
import mmap
import struct
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple, Dict, Any

from core_shared import (
    MAGIC_REC_HDR, MAGIC_REC_TRL,
    _parse_varstruct, _mapunit_to_deg, _read_varint_from,
    find_magic, _emit
)

@dataclass
class RSDRecord:
    ofs: int
    channel_id: Optional[int]
    seq: int
    time_ms: int
    data_size: int
    lat: Optional[float]
    lon: Optional[float]
    depth_m: Optional[float]
    sample_cnt: Optional[int]
    sonar_ofs: Optional[int]
    sonar_size: Optional[int]
    beam_deg: Optional[float]
    pitch_deg: Optional[float]
    roll_deg: Optional[float]
    heave_m: Optional[float]
    tx_ofs_m: Optional[float]
    rx_ofs_m: Optional[float]
    color_id: Optional[int]
    extras: Dict[str,Any]


def _iter_records(mm: mmap.mmap, start: int, limit: int, log_file, limit_records: Optional[int]=None) -> Iterator[RSDRecord]:
    """Iterator for strict record parsing (requires valid CRC)."""
    count = 0
    pos = start
    while pos < limit:
        # Find next record header magic
        pos_magic = mm.find(struct.pack('<I', MAGIC_REC_HDR), pos, limit)
        if pos_magic < 0: 
            log_file.write(f'No more header magic found after 0x{pos:X}\n')
            break
        pos = pos_magic + 4

        # Parse header (strict CRC)
        hdr_block = None
        try:
            log_file.write(f'Found header magic at 0x{pos_magic:X}, parsing varstruct...\n')
            hdr, body_start = _parse_varstruct(mm, pos_magic, limit, crc_mode='strict')
            if struct.unpack('<I', hdr.get(0,b'\x00'*4)[:4])[0] == MAGIC_REC_HDR:
                hdr_block = (hdr, pos_magic, body_start)
                log_file.write(f'Header parsed OK at 0x{pos_magic:X}\n')
            else:
                log_file.write(f'Header has wrong magic at 0x{pos_magic:X}\n')
        except Exception as e:
            log_file.write(f'Failed to parse header at 0x{pos_magic:X}: {e}\n')
        
        if not hdr_block:
            _emit((pos/limit)*100.0, f"Advancing after header parse fail @ 0x{pos_magic:X}")
            continue

        hdr, hdr_start, body_start = hdr_block
        seq = struct.unpack('<I', hdr.get(2,b'\x00'*4)[:4])[0]
        time_ms = struct.unpack('<I', hdr.get(5,b'\x00'*4)[:4])[0]
        data_sz = struct.unpack('<H', (hdr.get(4,b'\x00\x00')[:2] or b'\x00\x00'))[0]

        lat=lon=depth=None; sample=None; ch=None; used=0
        beam=pitch=roll=heave=txo=rxo=None; color=None; extras={}

        try:
            body, body_end = _parse_varstruct(mm, body_start, limit, crc_mode='strict')
            used = max(0, body_end-body_start)

            if 0 in body: ch = int.from_bytes(body[0][:4].ljust(4,b'\x00'),'little')
            if 9 in body and len(body[9])>=4: lat = _mapunit_to_deg(int.from_bytes(body[9][:4],'little',signed=True))
            if 10 in body and len(body[10])>=4: lon = _mapunit_to_deg(int.from_bytes(body[10][:4],'little',signed=True))
            if 1 in body:
                try:
                    v,_ = _read_varint_from(mm[body_start:body_start+len(body[1])],0,len(body[1]))
                    depth = v/1000.0
                except Exception:
                    pass
            if 7 in body: sample = int.from_bytes(body[7][:4].ljust(4,b'\x00'),'little')

            # Heuristic decodes for additional telemetry (IDs subject to change per firmware variants)
            if 11 in body and len(body[11])>=2:
                try: beam = int.from_bytes(body[11][:2], 'little', signed=True) / 1000.0
                except Exception: pass
            if 12 in body and len(body[12])>=2:
                try: pitch = int.from_bytes(body[12][:2], 'little', signed=True) / 1000.0
                except Exception: pass
            if 13 in body and len(body[13])>=2:
                try: roll = int.from_bytes(body[13][:2], 'little', signed=True) / 1000.0
                except Exception: pass
            if 14 in body and len(body[14])>=2:
                try: heave = int.from_bytes(body[14][:2], 'little', signed=True) / 1000.0
                except Exception: pass
            if 15 in body and len(body[15])>=4:
                txo = _try_read_float32(body[15])
            if 16 in body and len(body[16])>=4:
                rxo = _try_read_float32(body[16])
            if 17 in body and len(body[17])>=1:
                color = int.from_bytes(body[17][:1], 'little')
            extras = _decode_body_fields(body)

        except Exception:
            pos = pos_magic + 4
            _emit((pos/limit)*100.0, f"Advancing after body parse fail @ 0x{pos_magic:X}")
            continue

        sonar_ofs = body_start + used
        sonar_len = max(0, data_sz - used) if data_sz > 0 else 0

        trailer_pos = body_start + data_sz
        if trailer_pos + 12 > limit:
            break

        tr_magic, chunk_size, tr_crc = struct.unpack('<III', mm[trailer_pos:trailer_pos+12])
        if tr_magic != MAGIC_REC_TRL or chunk_size <= 0:
            pos = pos_magic + 4
            _emit((pos/limit)*100.0, f"Advancing after trailer mismatch @ 0x{trailer_pos:X}")
            continue

        yield RSDRecord(
            hdr_start, ch, seq, time_ms, data_sz,
            lat, lon, depth, sample,
            sonar_ofs if sonar_len>0 else None,
            sonar_len if sonar_len>0 else None,
            beam, pitch, roll, heave, txo, rxo, color, extras
        )
        count += 1
        if count % 250 == 0:
            _emit((trailer_pos/limit)*100.0, f"Records: {count}")
        if limit_records and count >= limit_records:
            break

        pos = hdr_start + chunk_size

    _emit(100.0, f"Done (classic). Records: {count}")
    mm.close()


def _try_read_float32(data: bytes) -> Optional[float]:
    """Try to read a 32-bit float, return None if invalid."""
    try:
        if len(data) >= 4:
            return struct.unpack('<f', data[:4])[0]
    except Exception:
        pass
    return None


def _decode_body_fields(body: Dict[int,bytes]) -> Dict[str,Any]:
    """Convert unknown body fields to hex strings or numbers."""
    extras = {}
    for k,v in body.items():
        if k in (0,1,7,9,10,11,12,13,14,15,16,17):
            continue  # skip known fields
        if len(v) <= 4:
            extras[f'field_{k}'] = int.from_bytes(v, 'little')
        else:
            extras[f'field_{k}_hex'] = v.hex()
    return extras


def parse_rsd(path: str, out_dir: str, max_records: Optional[int]=None) -> Tuple[int,str,str]:
    """Parse an RSD file into CSV rows.
    
    Returns: (n_rows, csv_path, log_path)
    """
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(path)
    csv_out = os.path.join(out_dir, base + '.rows.csv')
    log_out = os.path.join(out_dir, base + '.log')

    with open(path, 'rb') as f, open(csv_out, 'w', newline='') as outf, open(log_out, 'w') as lg:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        limit = len(mm)

        import csv
        w = csv.writer(outf)
        w.writerow(['idx', 'channel_id', 'seq', 'time_ms', 'data_size',
                   'lat', 'lon', 'depth_m', 'sample_cnt',
                   'sonar_ofs', 'sonar_size',
                   'beam_deg', 'pitch_deg', 'roll_deg', 'heave_m',
                   'tx_ofs_m', 'rx_ofs_m', 'color_id', 'extras_json'])

        n = 0
        for rec in _iter_records(mm, 0, limit, lg, max_records):
            w.writerow([
                rec.ofs, rec.channel_id, rec.seq, rec.time_ms, rec.data_size,
                rec.lat, rec.lon, rec.depth_m, rec.sample_cnt,
                rec.sonar_ofs, rec.sonar_size,
                rec.beam_deg, rec.pitch_deg, rec.roll_deg, rec.heave_m,
                rec.tx_ofs_m, rec.rx_ofs_m, rec.color_id,
                str(rec.extras) if rec.extras else ''
            ])
            n += 1
        lg.write(f'Parsed {n} records\n')
        return n, csv_out, log_out


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('rsd_path')
    ap.add_argument('out_dir')
    ap.add_argument('--max', type=int, help='Optional record limit')
    args = ap.parse_args()
    n, p, l = parse_rsd(args.rsd_path, args.out_dir, args.max)
    print(f'Wrote {n} records -> {p}')
