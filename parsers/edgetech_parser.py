#!/usr/bin/env python3
"""
EdgeTech JSF Parser Implementation
Based on EdgeTech JSF format specification and PINGVerter research
Supports EdgeTech side-scan sonar formats
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
class EdgeTechRecord(SonarRecord):
    """EdgeTech-specific sonar record with additional fields"""
    message_type: int = 0            # JSF message type
    subsystem: int = 0               # Subsystem number
    channel: int = 0                 # Channel number within subsystem
    start_frequency: float = 0.0     # Start frequency in Hz
    end_frequency: float = 0.0       # End frequency in Hz
    pulse_length: float = 0.0        # Pulse length in seconds
    absorption: float = 0.0          # Absorption coefficient
    projector_type: int = 0          # Projector type
    projector_beam_width: float = 0.0 # Projector beam width in degrees
    hydrophone_beam_width: float = 0.0 # Hydrophone beam width in degrees
    range_scale: float = 0.0         # Range scale in meters
    tow_cable_out: float = 0.0       # Tow cable out in meters
    layback: float = 0.0             # Layback distance in meters
    cable_tension: float = 0.0       # Cable tension
    sensor_depth: float = 0.0        # Sensor depth in meters

class EdgeTechParser(BaseSonarParser):
    """
    Parser for EdgeTech JSF (Sub-bottom and Side-scan) sonar files
    Based on EdgeTech JSF format specification
    """
    
    # JSF Magic number and constants
    JSF_MAGIC = 0x1601              # JSF file magic number
    
    # JSF Message types
    MESSAGE_TYPES = {
        80: 'SONAR_DATA',
        82: 'BATHYMETRY',
        102: 'SIDE_SCAN',
        2002: 'COMMENT',
        2020: 'POSITION',
        2080: 'RAW_SERIAL_DATA',
        2090: 'ECHOSOUNDER',
        2091: 'GYRO',
        2092: 'WATER_COLUMN',
        2100: 'RESON_7125',
        2101: 'RESON_SNIPPET',
        2102: 'DVL',
        2103: 'SYSTEM_STATE'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "edgetech_jsf"
        self.channels = []
        self.file_header = None
        self._determine_channels()
        
    def _determine_channels(self):
        """Scan file to determine available sonar channels"""
        try:
            with open(self.file_path, 'rb') as f:
                # Read file header
                self.file_header = self._read_file_header(f)
                
                # Quick scan for sonar data messages
                data = f.read(min(2*1024*1024, os.path.getsize(self.file_path)))  # First 2MB
                
                # Look for JSF message headers
                pos = 0
                channel_types = set()
                subsystems = set()
                
                while pos < len(data) - 16:
                    if pos + 16 <= len(data):
                        try:
                            # Check for JSF magic number
                            magic = struct.unpack('<H', data[pos:pos+2])[0]
                            if magic == self.JSF_MAGIC:
                                # Parse message header
                                msg_type = struct.unpack('<H', data[pos+2:pos+4])[0]
                                msg_size = struct.unpack('<I', data[pos+8:pos+12])[0]
                                subsystem = struct.unpack('<B', data[pos+12:pos+13])[0]
                                channel = struct.unpack('<B', data[pos+13:pos+14])[0]
                                
                                if msg_type in [80, 82, 102]:  # Sonar data types
                                    channel_types.add(channel)
                                    subsystems.add(subsystem)
                                
                                pos += 16 + msg_size
                            else:
                                pos += 2
                        except struct.error:
                            pos += 2
                    else:
                        break
                
                self.channels = sorted(list(channel_types)) if channel_types else [0, 1]
                self.subsystems = sorted(list(subsystems)) if subsystems else [0]
                
        except Exception as e:
            logging.warning(f"Could not determine EdgeTech channels: {e}")
            self.channels = [0, 1]  # Default: Port/Starboard
            self.subsystems = [0]

    def _read_file_header(self, f) -> Dict[str, Any]:
        """Read EdgeTech JSF file header"""
        try:
            f.seek(0)
            
            # JSF files start with message headers, no global file header
            # Try to read first message to validate format
            magic = struct.unpack('<H', f.read(2))[0]
            
            if magic != self.JSF_MAGIC:
                return {'valid': False, 'magic': magic}
            
            # Read first message header
            msg_type = struct.unpack('<H', f.read(2))[0]
            timestamp = struct.unpack('<I', f.read(4))[0]
            msg_size = struct.unpack('<I', f.read(4))[0]
            subsystem = struct.unpack('<B', f.read(1))[0]
            channel = struct.unpack('<B', f.read(1))[0]
            
            # Skip back to start
            f.seek(0)
            
            return {
                'valid': True,
                'magic': magic,
                'first_message_type': msg_type,
                'first_timestamp': timestamp,
                'first_subsystem': subsystem,
                'first_channel': channel
            }
            
        except Exception as e:
            logging.warning(f"Error reading EdgeTech header: {e}")
            return {'valid': False, 'error': str(e)}

    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        info = super().get_file_info()
        info.update({
            'format_details': {
                'format_name': 'EdgeTech JSF',
                'manufacturer': 'EdgeTech',
                'description': 'Sub-bottom and side-scan sonar format',
                'magic_bytes': '0x1601'
            },
            'channels': self.channels,
            'subsystems': getattr(self, 'subsystems', [0]),
            'file_header': self.file_header
        })
        
        # Try to get more detailed info
        try:
            with open(self.file_path, 'rb') as f:
                first_record = self._read_next_message(f)
                if first_record:
                    info['first_timestamp'] = first_record.time_ms
                    info['coordinate_reference'] = f"Lat: {first_record.lat:.6f}, Lon: {first_record.lon:.6f}"
        except:
            pass
            
        return info

    def get_channels(self) -> List[int]:
        """
        Get available sonar channels
        
        Returns:
            List of channel IDs
        """
        return self.channels

    def parse_records(self, max_records: Optional[int] = None, progress_callback=None) -> Tuple[int, str, str]:
        """Parse EdgeTech records and export to CSV"""
        output_csv = self.file_path.replace('.jsf', '_records.csv')
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
                csvfile.write("message_type,subsystem,start_freq,end_freq,pulse_length,range_scale,")
                csvfile.write("tow_cable_out,layback,sensor_depth,extras_json\n")
                
                with open(self.file_path, 'rb') as f:
                    
                    while True:
                        if max_records and count >= max_records:
                            break
                            
                        record = self._read_next_message(f)
                        if not record:
                            break
                            
                        # Only process sonar data messages
                        if record.message_type not in [80, 82, 102]:
                            continue
                            
                        # Write CSV row
                        extras = {
                            'message_type_name': self.MESSAGE_TYPES.get(record.message_type, 'Unknown'),
                            'projector_type': record.projector_type,
                            'projector_beam_width': record.projector_beam_width,
                            'hydrophone_beam_width': record.hydrophone_beam_width,
                            'absorption': record.absorption,
                            'cable_tension': record.cable_tension
                        }
                        
                        csvfile.write(f"{record.ofs},{record.channel_id},{count},{record.time_ms},")
                        csvfile.write(f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},")
                        csvfile.write(f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},")
                        csvfile.write(f"{record.pitch_deg},{record.roll_deg},{record.heave_m},")
                        csvfile.write(f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},")
                        csvfile.write(f"{record.message_type},{record.subsystem},{record.start_frequency},")
                        csvfile.write(f"{record.end_frequency},{record.pulse_length},{record.range_scale},")
                        csvfile.write(f"{record.tow_cable_out},{record.layback},{record.sensor_depth},")
                        csvfile.write(f'"{json.dumps(extras)}"\n')
                        
                        count += 1
                        
                        if count % 1000 == 0:
                            logging.info(f"Processed {count} EdgeTech records")
                            
        except Exception as e:
            logging.error(f"Error parsing EdgeTech file: {e}")
            raise
            
        logging.info(f"Completed EdgeTech parsing: {count} records")
        return count, output_csv, output_log

    def _read_next_message(self, f) -> Optional[EdgeTechRecord]:
        """Read next EdgeTech JSF message from file"""
        try:
            start_pos = f.tell()
            
            # Read message header (16 bytes)
            header_data = f.read(16)
            if len(header_data) < 16:
                return None
                
            # Parse message header
            magic = struct.unpack('<H', header_data[0:2])[0]
            if magic != self.JSF_MAGIC:
                return None
                
            msg_type = struct.unpack('<H', header_data[2:4])[0]
            timestamp = struct.unpack('<I', header_data[4:8])[0]
            msg_size = struct.unpack('<I', header_data[8:12])[0]
            subsystem = struct.unpack('<B', header_data[12:13])[0]
            channel = struct.unpack('<B', header_data[13:14])[0]
            sequence = struct.unpack('<B', header_data[14:15])[0]
            
            # Sanity check message size
            if msg_size > 10*1024*1024:  # 10MB max
                return None
            
            # Read message data
            if msg_size > 0:
                msg_data = f.read(msg_size)
                if len(msg_data) < msg_size:
                    return None
            else:
                msg_data = b''
            
            # Parse specific message types
            lat, lon = 0.0, 0.0
            depth_m = 0.0
            sample_cnt = 0
            start_freq = 0.0
            end_freq = 0.0
            pulse_length = 0.0
            range_scale = 0.0
            
            if msg_type in [80, 82, 102] and len(msg_data) >= 100:  # Sonar data
                try:
                    # Parse sonar message header (approximate offsets)
                    ping_time = struct.unpack('<I', msg_data[0:4])[0]
                    start_freq = struct.unpack('<I', msg_data[4:8])[0]
                    end_freq = struct.unpack('<I', msg_data[8:12])[0]
                    sample_cnt = struct.unpack('<H', msg_data[12:14])[0]
                    range_scale = struct.unpack('<f', msg_data[20:24])[0]
                    
                    # Navigation data (if present)
                    if len(msg_data) >= 80:
                        lat_raw = struct.unpack('<i', msg_data[40:44])[0]
                        lon_raw = struct.unpack('<i', msg_data[44:48])[0]
                        
                        if lat_raw != 0:
                            lat = lat_raw / 1e7  # Convert from degrees * 1e7
                        if lon_raw != 0:
                            lon = lon_raw / 1e7
                            
                        # Depth and other sensor data
                        if len(msg_data) >= 100:
                            depth_raw = struct.unpack('<i', msg_data[48:52])[0]
                            depth_m = depth_raw / 1000.0  # Convert from mm to m
                            
                            pulse_length = struct.unpack('<f', msg_data[60:64])[0]
                            
                except struct.error:
                    pass
            
            # Create record
            record = EdgeTechRecord(
                ofs=start_pos,
                channel_id=channel,
                seq=sequence,
                time_ms=timestamp,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                sample_cnt=sample_cnt,
                sonar_ofs=start_pos + 16 + 100,  # Approximate data start
                sonar_size=max(0, msg_size - 100),
                beam_deg=0.0,
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                tx_ofs_m=0.0,
                rx_ofs_m=0.0,
                color_id=0,
                message_type=msg_type,
                subsystem=subsystem,
                channel=channel,
                start_frequency=start_freq,
                end_frequency=end_freq,
                pulse_length=pulse_length,
                absorption=0.0,
                projector_type=0,
                projector_beam_width=0.0,
                hydrophone_beam_width=0.0,
                range_scale=range_scale,
                tow_cable_out=0.0,
                layback=0.0,
                cable_tension=0.0,
                sensor_depth=depth_m
            )
            
            return record
            
        except Exception as e:
            logging.warning(f"Error reading EdgeTech message at {f.tell()}: {e}")
            return None

    def get_enhanced_file_info(self) -> Dict[str, Any]:
        """Get enhanced EdgeTech file information with message analysis"""
        info = self.get_file_info()
        
        try:
            # Analyze message distribution
            message_stats = {}
            sample_size = 1000
            
            with open(self.file_path, 'rb') as f:
                count = 0
                while count < sample_size:
                    record = self._read_next_message(f)
                    if not record:
                        break
                        
                    msg_type = record.message_type
                    msg_name = self.MESSAGE_TYPES.get(msg_type, f'Unknown_{msg_type}')
                    
                    if msg_name not in message_stats:
                        message_stats[msg_name] = {
                            'count': 0,
                            'avg_sample_size': 0,
                            'msg_type': msg_type,
                            'avg_frequency': 0.0
                        }
                    
                    message_stats[msg_name]['count'] += 1
                    message_stats[msg_name]['avg_sample_size'] += record.sample_cnt
                    message_stats[msg_name]['avg_frequency'] += record.start_frequency
                    count += 1
                
                # Calculate averages
                for msg_name in message_stats:
                    if message_stats[msg_name]['count'] > 0:
                        message_stats[msg_name]['avg_sample_size'] /= message_stats[msg_name]['count']
                        message_stats[msg_name]['avg_frequency'] /= message_stats[msg_name]['count']
                        
                info['message_analysis'] = message_stats
                info['sample_records_analyzed'] = count
                
        except Exception as e:
            info['analysis_error'] = str(e)
            
        return info

    def is_supported(self) -> bool:
        """Check if file is a supported EdgeTech JSF format"""
        if not super().is_supported():
            return False
            
        try:
            with open(self.file_path, 'rb') as f:
                magic = struct.unpack('<H', f.read(2))[0]
                return magic == self.JSF_MAGIC
        except:
            return False