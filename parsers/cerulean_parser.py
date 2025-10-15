#!/usr/bin/env python3
"""
Cerulean SVLOG Parser Implementation
Based on PINGVerter research and Cerulean Sonar documentation
Supports Cerulean Omniscan sonar log formats
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
class CeruleanRecord(SonarRecord):
    """Cerulean-specific sonar record with additional fields"""
    device_id: int = 0               # Device ID
    device_type: int = 0             # Device type
    device_model: str = ""           # Device model string
    firmware_version: str = ""       # Firmware version
    gain_setting: int = 0            # Gain setting
    range_setting: float = 0.0       # Range setting in meters
    frequency: float = 0.0           # Operating frequency in kHz
    pulse_duration: float = 0.0      # Pulse duration in microseconds
    ping_interval: float = 0.0       # Ping interval in ms
    speed_of_sound: float = 0.0      # Speed of sound in m/s
    auto_range: bool = False         # Auto range enabled
    auto_gain: bool = False          # Auto gain enabled
    scan_start: float = 0.0          # Scan start in meters
    scan_length: float = 0.0         # Scan length in meters

class CeruleanParser(BaseSonarParser):
    """
    Parser for Cerulean SVLOG sonar files
    Based on Cerulean Omniscan format and Blue Robotics Ping Protocol
    """
    
    # Cerulean/Blue Robotics packet constants
    PING_PROTOCOL_HEADER = b'BR'     # Blue Robotics packet header
    SVLOG_MAGIC = b'SVLG'            # SVLOG file magic
    
    # Message types (based on Ping Protocol)
    MESSAGE_TYPES = {
        1000: 'PING_1D_GENERAL_INFO',
        1001: 'PING_1D_DISTANCE',
        1002: 'PING_1D_DISTANCE_SIMPLE',
        1003: 'PING_1D_VOLTAGE_5',
        1004: 'PING_1D_SPEED_OF_SOUND',
        1005: 'PING_1D_RANGE',
        1006: 'PING_1D_MODE_AUTO',
        1007: 'PING_1D_PING_INTERVAL',
        1008: 'PING_1D_GAIN_SETTING',
        1009: 'PING_1D_TRANSMIT_DURATION',
        1010: 'PING_1D_PROFILE',
        2000: 'PING_360_DEVICE_INFO',
        2001: 'PING_360_DEVICE_DATA',
        2002: 'PING_360_MOTOR_OFF',
        2003: 'PING_360_MOTOR_ON',
        2004: 'PING_360_TRANSDUCER'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "cerulean_svlog"
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
                data = f.read(min(1024*1024, os.path.getsize(self.file_path)))  # First 1MB
                
                # Look for ping protocol messages
                pos = 0
                device_ids = set()
                msg_types = set()
                
                while pos < len(data) - 8:
                    if data[pos:pos+2] == self.PING_PROTOCOL_HEADER:
                        try:
                            # Parse ping protocol header
                            payload_length = struct.unpack('<H', data[pos+2:pos+4])[0]
                            msg_id = struct.unpack('<H', data[pos+4:pos+6])[0]
                            src_device_id = data[pos+6]
                            dst_device_id = data[pos+7]
                            
                            device_ids.add(src_device_id)
                            msg_types.add(msg_id)
                            
                            pos += 8 + payload_length + 2  # Header + payload + checksum
                        except:
                            pos += 2
                    else:
                        pos += 1
                
                self.channels = sorted(list(device_ids)) if device_ids else [0]
                self.message_types_found = msg_types
                
        except Exception as e:
            logging.warning(f"Could not determine Cerulean channels: {e}")
            self.channels = [0]  # Default single device

    def _read_file_header(self, f) -> Dict[str, Any]:
        """Read Cerulean SVLOG file header"""
        try:
            f.seek(0)
            
            # Check for SVLOG magic
            magic = f.read(4)
            if magic != self.SVLOG_MAGIC:
                # Try Blue Robotics format (starts with packets)
                f.seek(0)
                packet_header = f.read(2)
                if packet_header == self.PING_PROTOCOL_HEADER:
                    return {
                        'valid': True,
                        'format': 'ping_protocol',
                        'magic': packet_header
                    }
                else:
                    return {'valid': False, 'magic': magic}
            
            # Read SVLOG header fields
            version = struct.unpack('<H', f.read(2))[0]
            timestamp = struct.unpack('<I', f.read(4))[0]
            device_count = struct.unpack('<H', f.read(2))[0]
            
            return {
                'valid': True,
                'format': 'svlog',
                'magic': magic,
                'version': version,
                'timestamp': timestamp,
                'device_count': device_count
            }
            
        except Exception as e:
            logging.warning(f"Error reading Cerulean header: {e}")
            return {'valid': False, 'error': str(e)}

    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        info = super().get_file_info()
        info.update({
            'format_details': {
                'format_name': 'Cerulean SVLOG',
                'manufacturer': 'Cerulean Sonar',
                'description': 'Cerulean Omniscan sonar log format',
                'magic_bytes': 'SVLG or BR packet headers'
            },
            'channels': self.channels,
            'message_types_found': getattr(self, 'message_types_found', set()),
            'file_header': self.file_header
        })
        
        # Try to get more detailed info
        try:
            with open(self.file_path, 'rb') as f:
                first_record = self._read_next_packet(f)
                if first_record:
                    info['first_timestamp'] = first_record.time_ms
                    info['coordinate_reference'] = f"Lat: {first_record.lat:.6f}, Lon: {first_record.lon:.6f}"
        except:
            pass
            
        return info

    def parse_records(self, max_records: Optional[int] = None, progress_callback=None) -> Tuple[int, str, str]:
        """Parse Cerulean records and export to CSV"""
        output_csv = self.file_path.replace('.svlog', '_records.csv')
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
                csvfile.write("device_id,message_type,frequency,range_setting,gain_setting,")
                csvfile.write("pulse_duration,speed_of_sound,scan_start,scan_length,extras_json\n")
                
                with open(self.file_path, 'rb') as f:
                    # Skip SVLOG header if present
                    if self.file_header and self.file_header.get('format') == 'svlog':
                        f.seek(12)  # Skip SVLOG header
                    
                    while True:
                        if max_records and count >= max_records:
                            break
                            
                        record = self._read_next_packet(f)
                        if not record:
                            break
                            
                        # Write CSV row
                        extras = {
                            'device_model': record.device_model,
                            'firmware_version': record.firmware_version,
                            'auto_range': record.auto_range,
                            'auto_gain': record.auto_gain,
                            'ping_interval': record.ping_interval
                        }
                        
                        csvfile.write(f"{record.ofs},{record.channel_id},{count},{record.time_ms},")
                        csvfile.write(f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},")
                        csvfile.write(f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},")
                        csvfile.write(f"{record.pitch_deg},{record.roll_deg},{record.heave_m},")
                        csvfile.write(f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},")
                        csvfile.write(f"{record.device_id},{record.device_type},{record.frequency},")
                        csvfile.write(f"{record.range_setting},{record.gain_setting},{record.pulse_duration},")
                        csvfile.write(f"{record.speed_of_sound},{record.scan_start},{record.scan_length},")
                        csvfile.write(f'"{json.dumps(extras)}"\n')
                        
                        count += 1
                        
                        if count % 1000 == 0:
                            logging.info(f"Processed {count} Cerulean records")
                            
        except Exception as e:
            logging.error(f"Error parsing Cerulean file: {e}")
            raise
            
        logging.info(f"Completed Cerulean parsing: {count} records")
        return count, output_csv, output_log

    def _read_next_packet(self, f) -> Optional[CeruleanRecord]:
        """Read next Cerulean ping protocol packet from file"""
        try:
            start_pos = f.tell()
            
            # Look for ping protocol header
            header = f.read(2)
            if not header or header != self.PING_PROTOCOL_HEADER:
                return None
                
            # Read packet header
            header_data = f.read(6)
            if len(header_data) < 6:
                return None
                
            payload_length = struct.unpack('<H', header_data[0:2])[0]
            msg_id = struct.unpack('<H', header_data[2:4])[0]
            src_device_id = header_data[4]
            dst_device_id = header_data[5]
            
            # Sanity check payload length
            if payload_length > 64*1024:  # 64KB max
                return None
            
            # Read payload
            if payload_length > 0:
                payload = f.read(payload_length)
                if len(payload) < payload_length:
                    return None
            else:
                payload = b''
            
            # Read checksum
            checksum_data = f.read(2)
            if len(checksum_data) < 2:
                return None
                
            checksum = struct.unpack('<H', checksum_data)[0]
            
            # Parse specific message types
            lat, lon = 0.0, 0.0
            depth_m = 0.0
            sample_cnt = 0
            frequency = 0.0
            range_setting = 0.0
            gain_setting = 0
            
            if msg_id == 1010 and len(payload) >= 20:  # PING_1D_PROFILE
                try:
                    # Parse profile data
                    distance = struct.unpack('<I', payload[0:4])[0] / 1000.0  # Convert mm to m
                    confidence = payload[4]
                    transmit_duration = struct.unpack('<H', payload[5:7])[0]
                    ping_number = struct.unpack('<I', payload[7:11])[0]
                    scan_start = struct.unpack('<I', payload[11:15])[0] / 1000.0
                    scan_length = struct.unpack('<I', payload[15:19])[0] / 1000.0
                    gain_setting = struct.unpack('<I', payload[19:23])[0] if len(payload) >= 23 else 0
                    
                    depth_m = distance
                    sample_cnt = len(payload) - 23 if len(payload) > 23 else 0
                    
                except struct.error:
                    pass
                    
            elif msg_id == 1001 and len(payload) >= 8:  # PING_1D_DISTANCE
                try:
                    distance = struct.unpack('<I', payload[0:4])[0] / 1000.0
                    confidence = payload[4]
                    depth_m = distance
                except struct.error:
                    pass
            
            # Extract timestamp (use current time as approximation)
            import time
            timestamp = int(time.time() * 1000)
            
            # Create record
            record = CeruleanRecord(
                ofs=start_pos,
                channel_id=src_device_id,
                seq=0,
                time_ms=timestamp,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                sample_cnt=sample_cnt,
                sonar_ofs=start_pos + 8 + 20,  # Approximate data start
                sonar_size=max(0, payload_length - 20),
                beam_deg=0.0,
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                tx_ofs_m=0.0,
                rx_ofs_m=0.0,
                color_id=0,
                device_id=src_device_id,
                device_type=msg_id,
                device_model="Omniscan",
                firmware_version="Unknown",
                gain_setting=gain_setting,
                range_setting=range_setting,
                frequency=frequency,
                pulse_duration=0.0,
                ping_interval=0.0,
                speed_of_sound=1500.0,  # Default
                auto_range=False,
                auto_gain=False,
                scan_start=0.0,
                scan_length=0.0
            )
            
            return record
            
        except Exception as e:
            logging.warning(f"Error reading Cerulean packet at {f.tell()}: {e}")
            return None

    def get_enhanced_file_info(self) -> Dict[str, Any]:
        """Get enhanced Cerulean file information with device analysis"""
        info = self.get_file_info()
        
        try:
            # Analyze device and message distribution
            device_stats = {}
            message_stats = {}
            sample_size = 500
            
            with open(self.file_path, 'rb') as f:
                # Skip SVLOG header if present
                if self.file_header and self.file_header.get('format') == 'svlog':
                    f.seek(12)
                
                count = 0
                while count < sample_size:
                    record = self._read_next_packet(f)
                    if not record:
                        break
                        
                    device_id = record.device_id
                    msg_type = record.device_type
                    msg_name = self.MESSAGE_TYPES.get(msg_type, f'Unknown_{msg_type}')
                    
                    # Device stats
                    if device_id not in device_stats:
                        device_stats[device_id] = {
                            'count': 0,
                            'avg_depth': 0.0,
                            'message_types': set()
                        }
                    
                    device_stats[device_id]['count'] += 1
                    device_stats[device_id]['avg_depth'] += record.depth_m
                    device_stats[device_id]['message_types'].add(msg_name)
                    
                    # Message stats
                    if msg_name not in message_stats:
                        message_stats[msg_name] = {
                            'count': 0,
                            'msg_id': msg_type
                        }
                    message_stats[msg_name]['count'] += 1
                    
                    count += 1
                
                # Calculate averages
                for device_id in device_stats:
                    if device_stats[device_id]['count'] > 0:
                        device_stats[device_id]['avg_depth'] /= device_stats[device_id]['count']
                        device_stats[device_id]['message_types'] = list(device_stats[device_id]['message_types'])
                        
                info['device_analysis'] = device_stats
                info['message_analysis'] = message_stats
                info['sample_records_analyzed'] = count
                
        except Exception as e:
            info['analysis_error'] = str(e)
            
        return info

    def is_supported(self) -> bool:
        """Check if file is a supported Cerulean format"""
        if not super().is_supported():
            return False
            
        try:
            with open(self.file_path, 'rb') as f:
                magic = f.read(4)
                if magic == self.SVLOG_MAGIC:
                    return True
                    
                # Check for ping protocol
                f.seek(0)
                header = f.read(2)
                return header == self.PING_PROTOCOL_HEADER
        except:
            return False