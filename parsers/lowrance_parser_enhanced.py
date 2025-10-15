#!/usr/bin/env python3
"""
Lowrance SL2/SL3 Parser Implementation
Based on PINGVerter research and SL3Reader architecture
Supports Lowrance/Navico sonar log formats
"""

import struct
import mmap
import os
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json

from .base_parser import BaseSonarParser, SonarRecord

@dataclass
class LowranceRecord(SonarRecord):
    """Lowrance-specific sonar record with additional fields"""
    channel_type: str = ""           # 'Primary', 'Secondary', 'DSI', 'SideScan'
    frequency: float = 0.0           # Frequency in kHz
    transmit_power: int = 0          # Transmit power level
    pulse_length: float = 0.0        # Pulse length in ms
    water_depth: float = 0.0         # Water depth in meters
    keelDepth: float = 0.0          # Keel depth offset
    speed_gps: float = 0.0          # GPS speed in m/s
    track: float = 0.0              # Track/heading in degrees
    altitude: float = 0.0           # GPS altitude
    salinity: int = 0               # Water salinity
    temperature: float = 0.0        # Water temperature

class LowranceParser(BaseSonarParser):
    """
    Parser for Lowrance SL2 and SL3 sonar files
    Based on Navico SLG format specification and PINGVerter implementation
    """
    
    # SL2/SL3 Magic bytes and constants
    SL2_MAGIC = b'\x03\x00\x00\x00'  # SL2 frame header
    SL3_MAGIC = b'\x04\x00\x00\x00'  # SL3 frame header
    
    # Frame types
    FRAME_TYPES = {
        0x00: 'PRIMARY_SONAR',
        0x01: 'SECONDARY_SONAR', 
        0x02: 'DSI_SONAR',
        0x03: 'LEFT_SIDESCAN',
        0x04: 'RIGHT_SIDESCAN',
        0x05: 'SIDESCAN_COMPOSITE',
        0x06: '3D_SONAR',
        0x07: 'TEMPERATURE',
        0x08: 'WATER_COLUMN',
        0x09: 'GPS_TRACK'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "lowrance_sl3" if file_path.lower().endswith('.sl3') else "lowrance_sl2"
        self.channels = []
        self._determine_channels()
        
    def _determine_channels(self):
        """Scan file to determine available channels"""
        try:
            with open(self.file_path, 'rb') as f:
                # Quick scan for channel types
                data = f.read(min(1024*1024, os.path.getsize(self.file_path)))  # First 1MB
                
                # Look for frame headers
                pos = 0
                channel_types = set()
                
                while pos < len(data) - 20:
                    if data[pos:pos+4] in [self.SL2_MAGIC, self.SL3_MAGIC]:
                        try:
                            # Parse basic frame header
                            frame_size = struct.unpack('<I', data[pos+4:pos+8])[0]
                            frame_type = data[pos+16] if pos+16 < len(data) else 0
                            
                            if frame_type in self.FRAME_TYPES:
                                channel_types.add(frame_type)
                                
                            pos += max(frame_size, 20)  # Skip to next potential frame
                        except:
                            pos += 4
                    else:
                        pos += 4
                
                self.channels = sorted(list(channel_types))
                
        except Exception as e:
            logging.warning(f"Could not determine Lowrance channels: {e}")
            self.channels = [0, 3, 4]  # Default: Primary + Left/Right sidescan

    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        info = super().get_file_info()
        info.update({
            'format_details': {
                'format_name': f'Lowrance {self.format_type.upper()}',
                'manufacturer': 'Lowrance/Navico',
                'description': 'Consumer sonar log format',
                'magic_bytes': 'SL2: 0x03000000, SL3: 0x04000000'
            },
            'channels': self.channels,
            'channel_names': [self.FRAME_TYPES.get(ch, f'Unknown_{ch}') for ch in self.channels]
        })
        
        # Try to get more detailed info
        try:
            with open(self.file_path, 'rb') as f:
                first_frame = self._read_next_frame(f)
                if first_frame:
                    info['first_timestamp'] = first_frame.time_ms
                    info['coordinate_reference'] = f"Lat: {first_frame.lat:.6f}, Lon: {first_frame.lon:.6f}"
        except:
            pass
            
        return info

    def parse_records(self, max_records: Optional[int] = None, progress_callback=None) -> Tuple[int, str, str]:
        """Parse Lowrance records and export to CSV"""
        output_csv = self.file_path.replace('.sl2', '_records.csv').replace('.sl3', '_records.csv')
        output_log = output_csv.replace('.csv', '.log')
        
        # Setup logging
        logging.basicConfig(
            filename=output_log,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )
        
        count = 0
        
        try:
            with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
                # Write CSV header
                csvfile.write("ofs,channel_id,seq,time_ms,lat,lon,depth_m,sample_cnt,sonar_ofs,sonar_size,")
                csvfile.write("beam_deg,pitch_deg,roll_deg,heave_m,tx_ofs_m,rx_ofs_m,color_id,")
                csvfile.write("frequency,transmit_power,pulse_length,water_depth,speed_gps,track,extras_json\n")
                
                with open(self.file_path, 'rb') as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        f.seek(0)
                        
                        while True:
                            if max_records and count >= max_records:
                                break
                                
                            record = self._read_next_frame(f)
                            if not record:
                                break
                                
                            # Write CSV row
                            extras = {
                                'channel_type': record.channel_type,
                                'salinity': record.salinity,
                                'temperature': record.temperature,
                                'altitude': record.altitude
                            }
                            
                            csvfile.write(f"{record.ofs},{record.channel_id},{count},{record.time_ms},")
                            csvfile.write(f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},")
                            csvfile.write(f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},")
                            csvfile.write(f"{record.pitch_deg},{record.roll_deg},{record.heave_m},")
                            csvfile.write(f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},")
                            csvfile.write(f"{record.frequency},{record.transmit_power},{record.pulse_length},")
                            csvfile.write(f"{record.water_depth},{record.speed_gps},{record.track},")
                            csvfile.write(f'"{json.dumps(extras)}"\n')
                            
                            count += 1
                            
                            if count % 1000 == 0:
                                logging.info(f"Processed {count} Lowrance records")
                                
        except Exception as e:
            logging.error(f"Error parsing Lowrance file: {e}")
            raise
            
        logging.info(f"Completed Lowrance parsing: {count} records")
        return count, output_csv, output_log

    def _read_next_frame(self, f) -> Optional[LowranceRecord]:
        """Read next Lowrance frame from file"""
        try:
            start_pos = f.tell()
            
            # Look for frame header
            header = f.read(4)
            if not header or header not in [self.SL2_MAGIC, self.SL3_MAGIC]:
                return None
                
            # Read frame header
            frame_size_data = f.read(4)
            if len(frame_size_data) < 4:
                return None
                
            frame_size = struct.unpack('<I', frame_size_data)[0]
            
            if frame_size < 20 or frame_size > 1024*1024:  # Sanity check
                return None
                
            # Read rest of frame header
            header_data = f.read(12)  # Remaining header bytes
            if len(header_data) < 12:
                return None
                
            # Parse frame header
            timestamp = struct.unpack('<I', header_data[0:4])[0]
            packet_size = struct.unpack('<H', header_data[4:6])[0]
            frame_index = struct.unpack('<H', header_data[6:8])[0]
            frame_type = header_data[8]
            
            # Skip to sonar data
            remaining_header = frame_size - 20
            if remaining_header > 0:
                extra_header = f.read(min(remaining_header, 100))  # Read some header data
                if len(extra_header) < min(remaining_header, 100):
                    return None
                    
                if remaining_header > 100:
                    f.seek(f.tell() + remaining_header - 100)
            
            # Try to extract navigation data from header
            lat, lon = 0.0, 0.0
            depth_m = 0.0
            speed_gps = 0.0
            track = 0.0
            frequency = 0.0
            
            if len(extra_header) >= 50:
                try:
                    # Common navigation offsets (approximate)
                    lat_raw = struct.unpack('<i', extra_header[8:12])[0] if len(extra_header) >= 12 else 0
                    lon_raw = struct.unpack('<i', extra_header[12:16])[0] if len(extra_header) >= 16 else 0
                    
                    if lat_raw != 0:
                        lat = lat_raw / 1e7  # Convert from degrees * 1e7
                    if lon_raw != 0:
                        lon = lon_raw / 1e7
                        
                    # Try to extract depth
                    if len(extra_header) >= 20:
                        depth_raw = struct.unpack('<H', extra_header[16:18])[0]
                        depth_m = depth_raw / 10.0  # Convert from cm to m
                        
                    # Try to extract speed/track
                    if len(extra_header) >= 30:
                        speed_raw = struct.unpack('<H', extra_header[20:22])[0]
                        speed_gps = speed_raw / 100.0  # Convert to m/s
                        
                        track_raw = struct.unpack('<H', extra_header[22:24])[0]
                        track = track_raw / 100.0  # Convert to degrees
                        
                except struct.error:
                    pass
            
            # Create record
            record = LowranceRecord(
                ofs=start_pos,
                channel_id=frame_type,
                seq=frame_index,
                time_ms=timestamp,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                sample_cnt=packet_size,
                sonar_ofs=f.tell(),
                sonar_size=packet_size,
                beam_deg=0.0,
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                tx_ofs_m=0.0,
                rx_ofs_m=0.0,
                color_id=0,
                channel_type=self.FRAME_TYPES.get(frame_type, f'Unknown_{frame_type}'),
                frequency=frequency,
                transmit_power=0,
                pulse_length=0.0,
                water_depth=depth_m,
                speed_gps=speed_gps,
                track=track,
                altitude=0.0,
                salinity=0,
                temperature=0.0
            )
            
            # Skip sonar data
            if packet_size > 0:
                f.seek(f.tell() + packet_size)
                
            return record
            
        except Exception as e:
            logging.warning(f"Error reading Lowrance frame at {f.tell()}: {e}")
            return None

    def get_enhanced_file_info(self) -> Dict[str, Any]:
        """Get enhanced Lowrance file information with channel analysis"""
        info = self.get_file_info()
        
        try:
            # Analyze channel distribution
            channel_stats = {}
            sample_size = 1000
            
            with open(self.file_path, 'rb') as f:
                count = 0
                while count < sample_size:
                    record = self._read_next_frame(f)
                    if not record:
                        break
                        
                    ch_type = record.channel_type
                    if ch_type not in channel_stats:
                        channel_stats[ch_type] = {
                            'count': 0,
                            'avg_sample_size': 0,
                            'frequency': record.frequency
                        }
                    
                    channel_stats[ch_type]['count'] += 1
                    channel_stats[ch_type]['avg_sample_size'] += record.sample_cnt
                    count += 1
                
                # Calculate averages
                for ch_type in channel_stats:
                    if channel_stats[ch_type]['count'] > 0:
                        channel_stats[ch_type]['avg_sample_size'] /= channel_stats[ch_type]['count']
                        
                info['channel_analysis'] = channel_stats
                info['sample_records_analyzed'] = count
                
        except Exception as e:
            info['analysis_error'] = str(e)
            
        return info

    def is_supported(self) -> bool:
        """Check if file is a supported Lowrance format"""
        if not super().is_supported():
            return False
            
        try:
            with open(self.file_path, 'rb') as f:
                magic = f.read(4)
                return magic in [self.SL2_MAGIC, self.SL3_MAGIC]
        except:
            return False