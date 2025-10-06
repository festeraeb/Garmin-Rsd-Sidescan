#!/usr/bin/env python3
"""Next-gen engine - tolerant CRC checking with heuristic resync.

This implementation is more to            # Parse body if heade            # Parse body if header got decoded
        try:
            body_sz = body_start - pos_magic + data_sz
            if body_start + data_sz > limit:
                log_file.write(f'Body would exceed limit at 0x{pos_magic:X}\n')
                break
            try:
                body, _ = _parse_varstruct(mm, body_start, body_start + data_sz, crc_mode='warn')
                if not body:
                    raise ValueError('Empty body struct')
            except Exception as be:
                log_file.write(f'Body parse failed at 0x{body_start:X}: {str(be)}\n')
                pos = body_start + data_sz
                continueecoded
        try:
            body_sz = body_start - pos_magic + data_sz
            if body_start + data_sz > limit:
                log_file.write(f'Body would exceed limit at 0x{pos_magic:X}\n')
                break
            # Pre-validate the body field count
            n, next_pos = 0, body_start
            try:
                n, next_pos = _read_varuint_from(mm, body_start, body_start + data_sz)
            except ValueError as ve:
                log_file.write(f'Pre-validation of body failed at 0x{body_start:X}: {str(ve)}\n')
                _emit((pos/limit)*100.0, f"Invalid body field count @ 0x{body_start:X}")
                raise
            if n < 0 or n > 50:  # Conservative max field count
                raise ValueError(f'Unreasonable field count in body: {n}')
            # Continue with full varstruct parse  
            body, _ = _parse_varstruct(mm, body_start, body_start + data_sz, crc_mode='warn')of malformed records and missing CRCs.
It synchronizes on record headers, extracts content, then resumes scanning.
"""
import os
import mmap
import struct
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple, Dict, Any
from core_shared import (
    MAGIC_REC_HDR, MAGIC_REC_TRL,
    _parse_varstruct, _mapunit_to_deg, _read_varint_from,
    find_magic, _emit, _decode_body_fields, _read_varuint_from
)
@dataclass
class RSDRecord:
    """Record data from a Garmin RSD file."""
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
def parse_rsd(rsd_path: str, out_dir: str, max_records: Optional[int] = None) -> Tuple[int, str, str]:
    """Parse RSD file and write records to CSV.
    Returns (record_count, csv_path, log_path).
    """
    # Setup output paths
    csv_path = os.path.join(out_dir, os.path.basename(rsd_path) + '.csv')
    log_path = os.path.join(out_dir, os.path.basename(rsd_path) + '.log')
    
    # Open input file and log
    count = 0
    with open(rsd_path, 'rb') as f, \
         open(csv_path, 'w') as csv_f, \
         open(log_path, 'w') as log_f:
        
        # Memory map the RSD file
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        
        # Write CSV header
        fields = ['ofs', 'channel_id', 'seq', 'time_ms', 'data_size', 'lat', 'lon', 'depth_m',
                 'sample_cnt', 'sonar_ofs', 'sonar_size', 'beam_deg', 'pitch_deg', 'roll_deg',
                 'heave_m', 'tx_ofs_m', 'rx_ofs_m', 'color_id', 'extras']
        csv_f.write(','.join(fields) + '\n')
        
        # Parse and write records
        try:
            for rec in _iter_records(mm, 0, mm.size(), log_f, max_records):
                count += 1
                values = [str(getattr(rec, f, '')) for f in fields]
                csv_f.write(','.join(values) + '\n')
                
                if count % 250 == 0:
                    _emit(count, f"Parsed {count} records")
        except Exception as e:
            log_f.write(f"Error during parsing: {str(e)}\n")
            raise
            
    return count, csv_path, log_path

def _iter_records(mm: mmap.mmap, start: int, limit: int, log_file, limit_records: Optional[int]=None) -> Iterator[RSDRecord]:
    """Iterator for tolerant record parsing (skip failed records)."""
    count = 0
    pos = start
    while pos < limit:
        # Find next record header magic
        pos_magic = find_magic(mm, struct.pack('<I', MAGIC_REC_HDR), pos, limit)
        if pos_magic < 0:
            log_file.write(f'No more header magic found after 0x{pos:X}\n')
            break
        
        # Parse the rest of the header
        pos = pos_magic + 4
        try:
            # Check next magic in case this was a false positive
            next_magic = mm[pos:pos+4]
            if len(next_magic) == 4 and struct.unpack('<I', next_magic)[0] == MAGIC_REC_HDR:
                log_file.write(f'Skipping false header at 0x{pos_magic:X}\n')
                continue
        except:
            # If we can't read the next magic, just continue with parsing
            pass

        # Parse header (skip if CRC error)
        try:
            log_file.write(f'Found header magic at 0x{pos_magic:X}, parsing varstruct...\n')
            # Skip magic bytes before parsing fields
            field_pos = pos_magic + 4
            try:
                n, next_pos = _read_varuint_from(mm, field_pos, limit)
            except ValueError as ve:
                log_file.write(f'Pre-validation failed at 0x{pos_magic:X}: {str(ve)}\n')
                _emit((pos/limit)*100.0, f"Invalid field count @ 0x{pos_magic:X}")
                raise
            if n < 0 or n > 50:  # Conservative max field count
                raise ValueError(f'Unreasonable field count in header: {n}')
            # Continue with full varstruct parse - be tolerant of CRC issues
            try:
                hdr, body_start = _parse_varstruct(mm, pos_magic, limit, crc_mode='warn')
            except ValueError as ve:
                log_file.write(f'Header parse failed at 0x{pos_magic:X}: {str(ve)}\n')
                pos = pos_magic + 4  # Skip magic and try next record
                continue
            if not hdr or struct.unpack('<I', hdr.get(0,b'\x00'*4)[:4])[0] != MAGIC_REC_HDR:
                log_file.write(f'Header has wrong magic at 0x{pos_magic:X}\n')
                _emit((pos/limit)*100.0, f"Advancing after bad header @ 0x{pos_magic:X}")
                continue
            # Extract required header fields with defaults
            seq = struct.unpack('<I', hdr.get(2,b'\x00'*4)[:4])[0]
            time_ms = struct.unpack('<I', hdr.get(5,b'\x00'*4)[:4])[0]
            # Data size must be present and reasonable
            raw_size = hdr.get(4,b'\x00\x00')[:2]
            if not raw_size:
                raise ValueError('Missing data size')
            data_sz = struct.unpack('<H', raw_size)[0]
            if data_sz < 32 or data_sz > 65535:
                raise ValueError(f'Invalid data size: {data_sz}')
            log_file.write(f'Header OK at 0x{pos_magic:X} (seq={seq}, time={time_ms}, size={data_sz})\n')
        except Exception as e:
            log_file.write(f'Header parse failed at 0x{pos_magic:X}: {str(e)}\n')
            _emit((pos/limit)*100.0, f"Advancing after header parse error @ 0x{pos_magic:X}")
            continue

        # Parse body if header got decoded
        try:
            body_sz = body_start - pos_magic + data_sz
            if body_start + data_sz > limit:
                log_file.write(f'Body would exceed limit at 0x{pos_magic:X}\n')
                break
            body, _ = _parse_varstruct(mm, body_start, body_start + data_sz, crc_mode='warn')
            if not body:
                log_file.write(f'Body parse failed at 0x{body_start:X}\n')
                _emit((pos/limit)*100.0, f"Skipping bad body @ 0x{body_start:X}")
                pos = body_start + data_sz
                continue
            # Extract known fields
            lat = struct.unpack('<f', body.get(6,b'\x00'*4)[:4])[0]
            lon = struct.unpack('<f', body.get(7,b'\x00'*4)[:4])[0]
            depth_m = struct.unpack('<f', body.get(8,b'\x00'*4)[:4])[0]
            beam_deg = struct.unpack('<f', body.get(9,b'\x00'*4)[:4])[0]
            pitch_deg = struct.unpack('<f', body.get(10,b'\x00'*4)[:4])[0]
            roll_deg = struct.unpack('<f', body.get(11,b'\x00'*4)[:4])[0]
            heave_m = struct.unpack('<f', body.get(12,b'\x00'*4)[:4])[0]
            tx_ofs_m = struct.unpack('<f', body.get(13,b'\x00'*4)[:4])[0]
            rx_ofs_m = struct.unpack('<f', body.get(14,b'\x00'*4)[:4])[0]
            channel_id = struct.unpack('<H', body.get(15,b'\x00\x00')[:2])[0]
            color_id = struct.unpack('<H', body.get(16,b'\x00\x00')[:2])[0]
            sample_cnt = struct.unpack('<H', body.get(17,b'\x00\x00')[:2])[0]
            sonar_ofs = body_start + data_sz - sample_cnt*2
            sonar_size = sample_cnt*2
            # Add heuristic extras decoding
            extras = _decode_body_fields(body)
            count += 1
            if limit_records and count > limit_records:
                break

            yield RSDRecord(
                ofs=pos_magic,
                channel_id=channel_id,
                seq=seq,
                time_ms=time_ms,
                data_size=data_sz,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                sample_cnt=sample_cnt,
                sonar_ofs=sonar_ofs,
                sonar_size=sonar_size,
                beam_deg=beam_deg,
                pitch_deg=pitch_deg,
                roll_deg=roll_deg,
                heave_m=heave_m,
                tx_ofs_m=tx_ofs_m,
                rx_ofs_m=rx_ofs_m,
                color_id=color_id,
                extras=extras)
            _emit((pos/limit)*100.0, f"Record {count}")
            pos = body_start + data_sz
        except Exception as e:
            log_file.write(f'Body decode failed at 0x{body_start:X}: {str(e)}\n')
            _emit((pos/limit)*100.0, f"Advancing after body decode error @ 0x{body_start:X}")
            pos = body_start + data_sz
            continue
