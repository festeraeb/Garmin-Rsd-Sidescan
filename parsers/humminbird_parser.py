#!/usr/bin/env python3
"""
Humminbird DAT/SON Parser Implementation
Based on PINGVerter research and Humminbird binary format specifications
Supports Humminbird sonar log formats
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
class HumminbirdRecord(SonarRecord):
    """Humminbird-specific sonar record with additional fields"""
    unit_type: str = ""              # Unit type/model
    software_version: str = ""       # Software version
    water_speed: float = 0.0         # Water speed in m/s
    temperature: float = 0.0         # Water temperature in C
    surface_clarity: int = 0         # Surface clarity setting
    frequency: float = 0.0           # Sonar frequency in kHz
    pulsewidth: float = 0.0         # Pulse width in microseconds
    range_setting: float = 0.0       # Range setting in meters
    gain: int = 0                   # Gain setting
    pulse_power: int = 0            # Pulse power setting
    noise_level: int = 0            # Noise level
    fish_id: int = 0                # Fish ID setting

class HumminbirdParser(BaseSonarParser):
    """
    Parser for Humminbird DAT and SON sonar files
    Based on PINGVerter hum2pingmapper implementation
    """
    
    # Humminbird format constants
    DAT_SIGNATURE = b'#HSI\x00\x01'  # Common DAT file signature
    SON_SIGNATURE = b'#HSI\x00\x02'  # Common SON file signature
    ALT_SON_SIGNATURE = b'\xc0\xde\xab\x21'  # Alternative SON signature found in real files
    
    # Record types
    RECORD_TYPES = {
        0x01: 'SONAR_DATA',
        0x02: 'GPS_DATA', 
        0x03: 'COMPASS_DATA',
        0x04: 'TEMPERATURE_DATA',
        0x05: 'SPEED_DATA',
        0x06: 'CONFIGURATION',
        0x07: 'ANNOTATION',
        0x08: 'WAYPOINT',
        0x09: 'ROUTE_DATA',
        0x0A: 'TRACK_DATA'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "humminbird_son" if file_path.lower().endswith('.son') else "humminbird_dat"
        self.channels = []
        self.file_header = None
        self._determine_channels()
        
    def _determine_channels(self):
        """Scan file to determine available sonar channels"""
        try:
            with open(self.file_path, 'rb') as f:
                # Read file header
                self.file_header = self._read_file_header(f)
                
                # Quick scan for sonar data records
                data = f.read(min(1024*1024, os.path.getsize(self.file_path)))  # First 1MB
                
                # Look for sonar data records
                pos = 0
                channel_types = set()
                
                while pos < len(data) - 20:
                    if data[pos:pos+6] in [self.DAT_SIGNATURE, self.SON_SIGNATURE] or data[pos:pos+4] == self.ALT_SON_SIGNATURE:
                        try:
                            # Parse basic record header
                            record_length = struct.unpack('<H', data[pos+6:pos+8])[0] if pos+8 <= len(data) else 0
                            record_type = data[pos+8] if pos+8 < len(data) else 0
                            
                            if record_type == 0x01:  # Sonar data
                                # Try to extract channel info
                                if pos+12 < len(data):
                                    channel_id = data[pos+10]  # Approximate channel location
                                    channel_types.add(channel_id)
                                
                            pos += max(record_length + 8, 20)  # Skip to next record
                        except:
                            pos += 1
                    else:
                        pos += 1
                
                self.channels = sorted(list(channel_types)) if channel_types else [0, 1]
                
        except Exception as e:
            logging.warning(f"Could not determine Humminbird channels: {e}")
            self.channels = [0, 1]  # Default: Dual beam

    def _read_file_header(self, f) -> Dict[str, Any]:
        """Read Humminbird file header"""
        try:
            f.seek(0)
            signature = f.read(6)
            
            if signature not in [self.DAT_SIGNATURE, self.SON_SIGNATURE]:
                return {'valid': False, 'signature': signature}
            
            # Read header fields
            header_length = struct.unpack('<H', f.read(2))[0]
            header_data = f.read(min(header_length, 1024))
            
            header = {
                'valid': True,
                'signature': signature,
                'header_length': header_length,
                'format_type': 'SON' if signature == self.SON_SIGNATURE else 'DAT'
            }
            
            # Parse header fields (simplified)
            if len(header_data) >= 20:
                try:
                    header['unit_type'] = struct.unpack('<H', header_data[0:2])[0]
                    header['software_version'] = struct.unpack('<H', header_data[2:4])[0]
                    header['creation_date'] = struct.unpack('<I', header_data[4:8])[0]
                    header['num_channels'] = struct.unpack('<H', header_data[8:10])[0]
                except struct.error:
                    pass
            
            return header
            
        except Exception as e:
            logging.warning(f"Error reading Humminbird header: {e}")
            return {'valid': False, 'error': str(e)}

    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        info = super().get_file_info()
        info.update({
            'format_details': {
                'format_name': f'Humminbird {self.format_type.upper()}',
                'manufacturer': 'Humminbird/Johnson Outdoors',
                'description': 'Consumer fishfinder log format',
                'magic_bytes': 'DAT: #HSI\\x00\\x01, SON: #HSI\\x00\\x02'
            },
            'channels': self.channels,
            'file_header': self.file_header
        })
        
        # Try to get more detailed info
        try:
            with open(self.file_path, 'rb') as f:
                first_record = self._read_next_record(f)
                if first_record:
                    info['first_timestamp'] = first_record.time_ms
                    info['coordinate_reference'] = f"Lat: {first_record.lat:.6f}, Lon: {first_record.lon:.6f}"
        except:
            pass
            
        return info

    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """Parse Humminbird records and export to CSV"""
        output_csv = self.file_path.replace('.dat', '_records.csv').replace('.son', '_records.csv')
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
                csvfile.write("frequency,temperature,water_speed,gain,pulse_power,range_setting,extras_json\n")
                
                with open(self.file_path, 'rb') as f:
                    # Skip file header
                    if self.file_header and self.file_header.get('valid', False):
                        f.seek(self.file_header.get('header_length', 0) + 8)
                    
                    while True:
                        if max_records and count >= max_records:
                            break
                            
                        record = self._read_next_record(f)
                        if not record:
                            break
                            
                        # Write CSV row
                        extras = {
                            'unit_type': record.unit_type,
                            'software_version': record.software_version,
                            'surface_clarity': record.surface_clarity,
                            'pulsewidth': record.pulsewidth,
                            'noise_level': record.noise_level,
                            'fish_id': record.fish_id
                        }
                        
                        csvfile.write(f"{record.ofs},{record.channel_id},{count},{record.time_ms},")
                        csvfile.write(f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},")
                        csvfile.write(f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},")
                        csvfile.write(f"{record.pitch_deg},{record.roll_deg},{record.heave_m},")
                        csvfile.write(f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},")
                        csvfile.write(f"{record.frequency},{record.temperature},{record.water_speed},")
                        csvfile.write(f"{record.gain},{record.pulse_power},{record.range_setting},")
                        csvfile.write(f'"{json.dumps(extras)}"\n')
                        
                        count += 1
                        
                        if count % 1000 == 0:
                            logging.info(f"Processed {count} Humminbird records")
                            
        except Exception as e:
            logging.error(f"Error parsing Humminbird file: {e}")
            raise
            
        logging.info(f"Completed Humminbird parsing: {count} records")
        return count, output_csv, output_log

    def _read_next_record(self, f) -> Optional[HumminbirdRecord]:
        """Read next Humminbird record from file"""
        try:
            start_pos = f.tell()
            
            # Look for record signature
            signature = f.read(6)
            if not signature or signature not in [self.DAT_SIGNATURE, self.SON_SIGNATURE]:
                return None
                
            # Read record header
            record_length_data = f.read(2)
            if len(record_length_data) < 2:
                return None
                
            record_length = struct.unpack('<H', record_length_data)[0]
            
            if record_length < 10 or record_length > 65536:  # Sanity check
                return None
                
            # Read record type and data
            record_data = f.read(record_length)
            if len(record_data) < record_length:
                return None
                
            record_type = record_data[0] if len(record_data) > 0 else 0
            
            # Only process sonar data records for now
            if record_type != 0x01:
                return None
            
            # Parse sonar record fields
            lat, lon = 0.0, 0.0
            depth_m = 0.0
            temperature = 0.0
            frequency = 0.0
            sample_cnt = 0
            channel_id = 0
            timestamp = 0
            
            if len(record_data) >= 50:
                try:
                    # Parse common fields (approximate offsets)
                    timestamp = struct.unpack('<I', record_data[1:5])[0]
                    channel_id = record_data[5]
                    frequency_raw = struct.unpack('<H', record_data[6:8])[0]
                    frequency = frequency_raw / 1000.0  # Convert to kHz
                    
                    # Navigation data (if present)
                    if len(record_data) >= 30:
                        lat_raw = struct.unpack('<i', record_data[10:14])[0]
                        lon_raw = struct.unpack('<i', record_data[14:18])[0]
                        
                        if lat_raw != 0:
                            lat = lat_raw / 1e7  # Convert from degrees * 1e7
                        if lon_raw != 0:
                            lon = lon_raw / 1e7
                            
                        # Depth and other fields
                        depth_raw = struct.unpack('<H', record_data[18:20])[0]
                        depth_m = depth_raw / 10.0  # Convert from cm to m
                        
                        temp_raw = struct.unpack('<H', record_data[20:22])[0]
                        temperature = temp_raw / 10.0 - 273.15  # Convert from K*10 to C
                        
                        sample_cnt = struct.unpack('<H', record_data[22:24])[0]
                        
                except struct.error:
                    pass
            
            # Create record
            record = HumminbirdRecord(
                ofs=start_pos,
                channel_id=channel_id,
                seq=0,
                time_ms=timestamp,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                sample_cnt=sample_cnt,
                sonar_ofs=start_pos + 8 + 24,  # Approximate data start
                sonar_size=record_length - 24,
                beam_deg=0.0,
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                tx_ofs_m=0.0,
                rx_ofs_m=0.0,
                color_id=0,
                unit_type="Unknown",
                software_version="Unknown",
                water_speed=0.0,
                temperature=temperature,
                surface_clarity=0,
                frequency=frequency,
                pulsewidth=0.0,
                range_setting=0.0,
                gain=0,
                pulse_power=0,
                noise_level=0,
                fish_id=0
            )
            
            return record
            
        except Exception as e:
            logging.warning(f"Error reading Humminbird record at {f.tell()}: {e}")
            return None

    def get_enhanced_file_info(self) -> Dict[str, Any]:
        """Get enhanced Humminbird file information with channel analysis"""
        info = self.get_file_info()
        
        try:
            # Analyze channel distribution
            channel_stats = {}
            sample_size = 500
            
            with open(self.file_path, 'rb') as f:
                # Skip header
                if self.file_header and self.file_header.get('valid', False):
                    f.seek(self.file_header.get('header_length', 0) + 8)
                
                count = 0
                while count < sample_size:
                    record = self._read_next_record(f)
                    if not record:
                        break
                        
                    ch_id = record.channel_id
                    if ch_id not in channel_stats:
                        channel_stats[ch_id] = {
                            'count': 0,
                            'avg_sample_size': 0,
                            'avg_frequency': 0.0,
                            'avg_depth': 0.0
                        }
                    
                    channel_stats[ch_id]['count'] += 1
                    channel_stats[ch_id]['avg_sample_size'] += record.sample_cnt
                    channel_stats[ch_id]['avg_frequency'] += record.frequency
                    channel_stats[ch_id]['avg_depth'] += record.depth_m
                    count += 1
                
                # Calculate averages
                for ch_id in channel_stats:
                    if channel_stats[ch_id]['count'] > 0:
                        channel_stats[ch_id]['avg_sample_size'] /= channel_stats[ch_id]['count']
                        channel_stats[ch_id]['avg_frequency'] /= channel_stats[ch_id]['count']
                        channel_stats[ch_id]['avg_depth'] /= channel_stats[ch_id]['count']
                        
                info['channel_analysis'] = channel_stats
                info['sample_records_analyzed'] = count
                
        except Exception as e:
            info['analysis_error'] = str(e)
            
        return info

    def is_supported(self) -> bool:
        """Check if file is a supported Humminbird format"""
        if not os.path.exists(self.file_path):
            return False
            
        # Check file size - very small files are likely logs, not sonar data
        if os.path.getsize(self.file_path) < 1000:  # Less than 1KB is probably a log
            return False
            
        try:
            with open(self.file_path, 'rb') as f:
                # First check if it's a text file (log file)
                first_100 = f.read(100)
                if first_100.startswith(b'20') and b'-' in first_100 and b':' in first_100:
                    # Looks like a timestamp/log file
                    return False
                
                f.seek(0)
                signature = f.read(6)
                # Check for standard signatures
                if signature in [self.DAT_SIGNATURE, self.SON_SIGNATURE]:
                    return True
                    
                # Check for alternative SON signature
                f.seek(0)
                alt_sig = f.read(4)
                if alt_sig == self.ALT_SON_SIGNATURE:
                    return True
                    
                # For .DAT and .SON files, be more lenient - check if it's binary data
                if self.file_path.lower().endswith(('.dat', '.son')):
                    f.seek(0)
                    header = f.read(512)
                    # Count binary bytes (non-printable)
                    binary_bytes = sum(1 for b in header if b < 32 or b > 126)
                    if binary_bytes > len(header) * 0.3:  # If >30% binary, probably sonar data
                        return True
                        
                return False
        except:
            return False