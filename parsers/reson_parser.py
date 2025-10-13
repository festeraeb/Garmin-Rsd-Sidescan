#!/usr/bin/env python3
"""
Reson SeaBat 7K Series Format Parser Implementation
Industry standard for commercial and scientific multibeam sonar systems

Based on Reson 7K Data Format Definition for SeaBat 7K series multibeam systems
Supports T20-P, T50-P, T50-R, 7125, 7150, 7160, and other 7K series systems
"""

import struct
import mmap
import os
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json
from pathlib import Path
from datetime import datetime
import math

# Import base classes
try:
    from .base_parser import BaseSonarParser, SonarRecord
except ImportError:
    # Fallback for standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parsers.base_parser import BaseSonarParser, SonarRecord

@dataclass
class ResonRecord(SonarRecord):
    """Reson 7K-specific sonar record with additional fields"""
    record_type_id: int = 0              # 7K record type identifier
    device_id: int = 0                   # Device identifier
    system_enumerator: int = 0           # System enumerator
    reserved_field: int = 0              # Reserved field
    size: int = 0                        # Record size
    offset: int = 0                      # Data record offset
    sync_counter: int = 0                # Synchronization counter
    flags: int = 0                       # Record flags
    reserved_2: int = 0                  # Second reserved field
    total_records: int = 0               # Total number of records
    size_2: int = 0                      # Second size field
    
    # Sonar-specific fields
    sonar_id: int = 0                    # Sonar identifier
    ping_number: int = 0                 # Ping number
    multi_ping: int = 0                  # Multi-ping flag
    number_beams: int = 0                # Number of beams
    reserved_3: int = 0                  # Third reserved field
    number_samples: int = 0              # Number of samples per beam
    sector_number: int = 0               # Sector number
    geodetic_datum: int = 0              # Geodetic datum
    ellipsoid: int = 0                   # Ellipsoid
    datum_identifier: int = 0            # Datum identifier
    coordinate_units: int = 0            # Coordinate units
    coordinate_transformation: int = 0    # Coordinate transformation
    horizontal_datum: int = 0            # Horizontal datum
    projection_type: int = 0             # Projection type
    projection_identifier: str = ""      # Projection identifier
    
    # Positioning and navigation
    vessel_latitude: float = 0.0         # Vessel latitude
    vessel_longitude: float = 0.0        # Vessel longitude
    vessel_height: float = 0.0           # Vessel height
    vessel_heading: float = 0.0          # Vessel heading
    vessel_heave: float = 0.0            # Vessel heave
    vessel_pitch: float = 0.0            # Vessel pitch
    vessel_roll: float = 0.0             # Vessel roll
    vessel_course: float = 0.0           # Vessel course
    vessel_speed: float = 0.0            # Vessel speed
    
    # Sonar system parameters
    frequency: float = 0.0               # Sonar frequency
    sample_rate: float = 0.0             # Sample rate
    receiver_bandwidth: float = 0.0      # Receiver bandwidth
    transmit_power: float = 0.0          # Transmit power
    pulse_width: float = 0.0             # Pulse width
    beam_angle_along: float = 0.0        # Beam angle along track
    beam_angle_across: float = 0.0       # Beam angle across track
    bottom_range: float = 0.0            # Bottom range
    maximum_range: float = 0.0           # Maximum range
    depth_mode: int = 0                  # Depth mode
    deep_mode: int = 0                   # Deep mode
    two_way_travel_time: float = 0.0     # Two-way travel time
    sound_speed: float = 0.0             # Sound speed
    maximum_bottom_depth: float = 0.0    # Maximum bottom depth
    minimum_bottom_depth: float = 0.0    # Minimum bottom depth
    compression_flag: int = 0            # Compression flag
    
    # Beam data arrays (simplified for CSV export)
    beam_descriptors: List = None        # Individual beam information
    detection_data: List = None          # Detection data per beam
    bathymetry_data: List = None         # Bathymetry data per beam

    def __post_init__(self):
        if self.beam_descriptors is None:
            self.beam_descriptors = []
        if self.detection_data is None:
            self.detection_data = []
        if self.bathymetry_data is None:
            self.bathymetry_data = []

class ResonParser(BaseSonarParser):
    """
    Parser for Reson SeaBat 7K series multibeam sonar files
    Industry standard for commercial and scientific applications
    
    Supports:
    - SeaBat T20-P portable multibeam
    - SeaBat T50-P/R high-resolution multibeam
    - SeaBat 7125 deep water multibeam
    - SeaBat 7150 compact multibeam
    - SeaBat 7160 ultra-high resolution multibeam
    - Bathymetry, backscatter, and water column data
    """
    
    # 7K Format constants
    S7K_SYNC_PATTERN = 0x0000FFFF          # Sync pattern for 7K records
    S7K_DRF_IDENTIFIER = b'7KDR'           # Data Record Frame identifier
    
    # 7K Record Type IDs (major record types)
    RECORD_TYPES = {
        1000: 'REFERENCE_POINT',             # Reference point information
        1001: 'SENSOR_UNCALIBRATED_OFFSET',  # Sensor uncalibrated offset
        1002: 'SENSOR_CALIBRATED_OFFSET',    # Sensor calibrated offset
        1003: 'POSITION',                    # Position
        1004: 'CUSTOM_ATTITUDE',             # Custom attitude
        1005: 'TIDE',                        # Tide
        1006: 'ALTITUDE',                    # Altitude
        1007: 'MOTION_OVER_GROUND',          # Motion over ground
        1008: 'DEPTH',                       # Depth
        1009: 'SOUND_VELOCITY_PROFILE',      # Sound velocity profile
        1010: 'CTD',                         # CTD data
        1011: 'GEODESY',                     # Geodesy
        1012: 'ROLL_PITCH_HEAVE',           # Roll pitch heave
        1013: 'HEADING',                     # Heading
        1014: 'SURVEY_LINE',                 # Survey line information
        1015: 'NAVIGATION',                  # Navigation
        1016: 'ATTITUDE',                    # Attitude
        
        7000: 'SONAR_SETTINGS',              # Sonar settings
        7001: 'CONFIGURATION',               # Configuration
        7002: 'MATCH_FILTER',                # Match filter
        7003: 'FIRMWARE_HARDWARE_CONFIG',    # Firmware and hardware configuration
        7004: 'BEAM_GEOMETRY',               # Beam geometry
        7005: 'CALIBRATION',                 # Calibration
        7006: 'BATHYMETRY',                  # Bathymetry data
        7007: 'SIDESCAN',                    # Sidescan data
        7008: 'GENERIC_WATER_COLUMN',        # Generic water column
        7009: 'TVG',                         # TVG data
        7010: 'IMAGE',                       # Image data
        7011: 'PING_MOTION',                 # Ping motion data
        7012: 'ADAPTIVE_GATE',               # Adaptive gate
        7013: 'DETECTION_DATA_SETUP',        # Detection data setup
        7014: 'BEAMFORMED_DATA',             # Beamformed magnitude and phase data
        7015: 'VER2_DETECTION_SETUP',        # Version 2 detection setup
        7016: 'VER2_BEAMFORMED_DATA',        # Version 2 beamformed data
        7017: 'VER2_DETECTION_DATA',         # Version 2 detection data
        7018: 'VER2_BATHYMETRY',             # Version 2 bathymetry
        7019: 'VER2_SIDESCAN',               # Version 2 sidescan
        7020: 'VER2_WATER_COLUMN',           # Version 2 water column
        7021: 'VER2_TVG',                    # Version 2 TVG
        7022: 'VER2_IMAGE',                  # Version 2 image
        7023: 'VER2_PING_MOTION',            # Version 2 ping motion
        7024: 'VER2_ADAPTIVE_GATE',          # Version 2 adaptive gate
        7025: 'VER2_BEAM_GEOMETRY',          # Version 2 beam geometry
        7026: 'VER2_CALIBRATION',            # Version 2 calibration
        7027: 'VER2_SONAR_SETTINGS',         # Version 2 sonar settings
        7028: 'VER2_CONFIGURATION',          # Version 2 configuration
        7029: 'VER2_MATCH_FILTER',           # Version 2 match filter
        7030: 'VER2_FIRMWARE_HARDWARE',      # Version 2 firmware/hardware
        
        7200: 'FILE_HEADER',                 # File header
        7300: 'FILE_CATALOG',                # File catalog
        7400: 'TIME_MESSAGE',                # Time message
        7500: 'REMOTE_CONTROL',              # Remote control
        7501: 'REMOTE_CONTROL_ACKNOWLEDGE',  # Remote control acknowledge
        7502: 'REMOTE_CONTROL_NOT_ACKNOWLEDGE', # Remote control not acknowledge
        7503: 'REMOTE_CONTROL_SONAR_SETTINGS', # Remote control sonar settings
        7504: 'COMMON_SYSTEM_SETTINGS',      # Common system settings
        7505: 'SVP_MESSAGE',                 # SVP message
        7506: 'SENSOR_SETUP',                # Sensor setup
        7507: 'CONFIGURATION_2',             # Configuration 2
        7508: 'MATCH_FILTER_2',              # Match filter 2
        7509: 'FIRMWARE_HARDWARE_2',         # Firmware hardware 2
        7510: 'BEAM_GEOMETRY_2',             # Beam geometry 2
        7511: 'CALIBRATION_2',               # Calibration 2
        7600: 'INSTALLATION',                # Installation parameters
        7610: 'BITE_SUMMARY',                # BITE summary
    }
    
    # SeaBat system identification
    SEABAT_MODELS = {
        1: 'SeaBat 7101',
        2: 'SeaBat 7111',
        3: 'SeaBat 7125',
        4: 'SeaBat 7150',
        5: 'SeaBat 7160',
        6: 'SeaBat T20-P',
        7: 'SeaBat T50-P',
        8: 'SeaBat T50-R'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "s7k"
        self.channels = []
        self.file_header = None
        self.sonar_settings = None
        self.system_info = {}
        self._parse_file_header()
        self._determine_channels()
        
    def _parse_file_header(self):
        """Parse Reson 7K file header and initial records"""
        try:
            with open(self.file_path, 'rb') as f:
                # Check for 7K signature
                header = f.read(100)
                
                # Look for DRF identifier or sync pattern
                if b'7KDR' not in header and not self._find_sync_pattern(header):
                    return False
                
                f.seek(0)
                
                # Parse first few records for system information
                record_count = 0
                while record_count < 10:  # Scan first 10 records
                    record = self._read_record_header(f)
                    if not record:
                        break
                    
                    record_type = record.get('record_type_id', 0)
                    
                    # Parse important system records
                    if record_type == 7200:  # File header
                        self._parse_file_header_record(f, record)
                    elif record_type == 7000:  # Sonar settings
                        self._parse_sonar_settings_record(f, record)
                    elif record_type == 1011:  # Geodesy
                        self._parse_geodesy_record(f, record)
                    else:
                        # Skip record data
                        record_size = record.get('size', 0)
                        if record_size > 64:  # Skip header size
                            f.seek(f.tell() + (record_size - 64))
                    
                    record_count += 1
                
                return True
                
        except Exception as e:
            logging.error(f"Failed to parse 7K file header: {e}")
            return False
    
    def _find_sync_pattern(self, data: bytes) -> bool:
        """Look for 7K sync pattern in data"""
        for i in range(len(data) - 4):
            if struct.unpack('<I', data[i:i+4])[0] == self.S7K_SYNC_PATTERN:
                return True
        return False
    
    def _read_record_header(self, f) -> Optional[Dict]:
        """Read 7K record header (64 bytes)"""
        try:
            header_data = f.read(64)
            if len(header_data) < 64:
                return None
            
            # Parse 7K record header
            sync_pattern = struct.unpack('<I', header_data[0:4])[0]
            size = struct.unpack('<I', header_data[4:8])[0]
            offset = struct.unpack('<I', header_data[8:12])[0]
            sync_counter = struct.unpack('<I', header_data[12:16])[0]
            timestamp = struct.unpack('<Q', header_data[16:24])[0]  # 8-byte timestamp
            record_type_id = struct.unpack('<I', header_data[24:28])[0]
            device_id = struct.unpack('<I', header_data[28:32])[0]
            system_enumerator = struct.unpack('<H', header_data[32:34])[0]
            reserved = struct.unpack('<H', header_data[34:36])[0]
            flags = struct.unpack('<H', header_data[36:38])[0]
            reserved_2 = struct.unpack('<H', header_data[38:40])[0]
            total_records = struct.unpack('<I', header_data[40:44])[0]
            size_2 = struct.unpack('<I', header_data[44:48])[0]
            
            return {
                'sync_pattern': sync_pattern,
                'size': size,
                'offset': offset,
                'sync_counter': sync_counter,
                'timestamp': timestamp,
                'record_type_id': record_type_id,
                'device_id': device_id,
                'system_enumerator': system_enumerator,
                'reserved': reserved,
                'flags': flags,
                'reserved_2': reserved_2,
                'total_records': total_records,
                'size_2': size_2
            }
            
        except Exception as e:
            logging.error(f"Failed to read 7K record header: {e}")
            return None
    
    def _parse_file_header_record(self, f, record: Dict):
        """Parse file header record (type 7200)"""
        try:
            data_size = record['size'] - 64  # Subtract header size
            if data_size <= 0:
                return
                
            data = f.read(data_size)
            if len(data) >= 16:
                # Parse basic file header info
                self.file_header = {
                    'file_identifier': data[0:16].decode('ascii', errors='ignore').rstrip('\x00'),
                    'version_number': struct.unpack('<H', data[16:18])[0] if len(data) > 18 else 0,
                    'reserved': struct.unpack('<H', data[18:20])[0] if len(data) > 20 else 0,
                    'session_identifier': data[20:84].decode('ascii', errors='ignore').rstrip('\x00') if len(data) > 84 else '',
                    'record_data_size': struct.unpack('<I', data[84:88])[0] if len(data) > 88 else 0,
                    'number_devices': struct.unpack('<I', data[88:92])[0] if len(data) > 92 else 0
                }
                
                logging.info(f"7K File: {self.file_header.get('file_identifier', 'Unknown')}")
                
        except Exception as e:
            logging.error(f"Failed to parse file header record: {e}")
    
    def _parse_sonar_settings_record(self, f, record: Dict):
        """Parse sonar settings record (type 7000)"""
        try:
            data_size = record['size'] - 64
            if data_size <= 0:
                return
                
            data = f.read(data_size)
            if len(data) >= 40:
                self.sonar_settings = {
                    'sonar_id': struct.unpack('<Q', data[0:8])[0],
                    'ping_number': struct.unpack('<I', data[8:12])[0],
                    'multi_ping': struct.unpack('<H', data[12:14])[0],
                    'frequency': struct.unpack('<f', data[14:18])[0],
                    'sample_rate': struct.unpack('<f', data[18:22])[0],
                    'receiver_bandwidth': struct.unpack('<f', data[22:26])[0],
                    'transmit_power': struct.unpack('<f', data[26:30])[0],
                    'pulse_width': struct.unpack('<f', data[30:34])[0],
                    'beam_angle_along': struct.unpack('<f', data[34:38])[0],
                    'beam_angle_across': struct.unpack('<f', data[38:42])[0] if len(data) > 42 else 0.0
                }
                
                # Determine system model from frequency or other parameters
                freq = self.sonar_settings.get('frequency', 0)
                if freq > 0:
                    if freq < 50000:
                        self.system_info['model'] = 'SeaBat 7125 (12 kHz)'
                    elif freq < 150000:
                        self.system_info['model'] = 'SeaBat 7150 (95 kHz)'
                    elif freq < 300000:
                        self.system_info['model'] = 'SeaBat 7160 (200 kHz)'
                    elif freq < 500000:
                        self.system_info['model'] = 'SeaBat T50 (400 kHz)'
                    else:
                        self.system_info['model'] = 'SeaBat T20 (900 kHz)'
                
                logging.info(f"7K Sonar: {self.system_info.get('model', 'Unknown')} at {freq/1000:.1f} kHz")
                
        except Exception as e:
            logging.error(f"Failed to parse sonar settings: {e}")
    
    def _parse_geodesy_record(self, f, record: Dict):
        """Parse geodesy record (type 1011)"""
        try:
            data_size = record['size'] - 64
            if data_size <= 0:
                return
                
            data = f.read(data_size)
            if len(data) >= 32:
                geodesy_info = {
                    'spheroid': data[0:32].decode('ascii', errors='ignore').rstrip('\x00'),
                    'datum_identifier': struct.unpack('<I', data[32:36])[0] if len(data) > 36 else 0,
                    'coordinate_units': struct.unpack('<I', data[36:40])[0] if len(data) > 40 else 0,
                    'coordinate_transformation': struct.unpack('<I', data[40:44])[0] if len(data) > 44 else 0
                }
                
                self.system_info.update(geodesy_info)
                
        except Exception as e:
            logging.error(f"Failed to parse geodesy record: {e}")
    
    def _determine_channels(self):
        """Determine channels from 7K multibeam system"""
        # Reson 7K systems typically have a single multibeam channel
        # with multiple beams within that channel
        self.channels = [0]  # Single multibeam channel
        
        # Could be expanded for systems with multiple transducers
    
    def is_supported(self) -> bool:
        """Check if file is a valid Reson 7K format"""
        try:
            with open(self.file_path, 'rb') as f:
                header = f.read(100)
                
                # Check for 7K signatures
                if b'7KDR' in header:
                    return True
                if self._find_sync_pattern(header):
                    return True
                    
                # Check for binary patterns typical of 7K files
                if header[:8] == b'\x53\x37\x4B\x00\x00\x00\x00\x01':
                    return True
                    
                return False
                
        except Exception:
            return False
    
    def get_channels(self) -> List[int]:
        """Get available channel IDs"""
        return self.channels
    
    def get_record_count(self) -> int:
        """Get total number of bathymetry/sonar records"""
        if not self.is_supported():
            return 0
            
        try:
            record_count = 0
            with open(self.file_path, 'rb') as f:
                while True:
                    record = self._read_record_header(f)
                    if not record:
                        break
                    
                    record_type = record.get('record_type_id', 0)
                    
                    # Count bathymetry and sonar data records
                    if record_type in [7006, 7007, 7018, 7019]:  # Bathymetry, sidescan, v2 versions
                        record_count += 1
                    
                    # Skip record data
                    record_size = record.get('size', 0)
                    if record_size > 64:
                        f.seek(f.tell() + (record_size - 64))
                        
            return record_count
            
        except Exception as e:
            logging.error(f"Failed to count 7K records: {e}")
            return 0
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        base_info = super().get_file_info()
        
        info_updates = {}
        
        if self.file_header:
            info_updates.update({
                'file_identifier': self.file_header.get('file_identifier', ''),
                'version_number': self.file_header.get('version_number', 0),
                'session_identifier': self.file_header.get('session_identifier', ''),
                'number_devices': self.file_header.get('number_devices', 0)
            })
        
        if self.sonar_settings:
            info_updates.update({
                'sonar_frequency': self.sonar_settings.get('frequency', 0.0),
                'sample_rate': self.sonar_settings.get('sample_rate', 0.0),
                'transmit_power': self.sonar_settings.get('transmit_power', 0.0),
                'pulse_width': self.sonar_settings.get('pulse_width', 0.0)
            })
        
        if self.system_info:
            info_updates.update({
                'system_model': self.system_info.get('model', 'Unknown'),
                'spheroid': self.system_info.get('spheroid', ''),
                'coordinate_units': self.system_info.get('coordinate_units', 0)
            })
        
        base_info.update(info_updates)
        return base_info
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse Reson 7K records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        if not self.is_supported():
            raise ValueError("Not a valid Reson 7K file")
        
        # Setup output paths
        base_name = Path(self.file_path).stem
        output_dir = Path(self.file_path).parent
        csv_path = output_dir / f"{base_name}_s7k_records.csv"
        log_path = output_dir / f"{base_name}_s7k_records.log"
        
        # Setup logging
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )
        
        record_count = 0
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write CSV header
                csvfile.write("ofs,channel_id,seq,time_ms,lat,lon,depth_m,sample_cnt,sonar_ofs,sonar_size,"
                            "beam_deg,pitch_deg,roll_deg,heave_m,tx_ofs_m,rx_ofs_m,color_id,extras_json\n")
                
                with open(self.file_path, 'rb') as f:
                    while max_records is None or record_count < max_records:
                        record_start = f.tell()
                        record_header = self._read_record_header(f)
                        
                        if not record_header:
                            break
                        
                        record = self._parse_record_data(f, record_header, record_start)
                        
                        if record:
                            # Write to CSV
                            extras = {
                                'record_type_id': record.record_type_id,
                                'device_id': record.device_id,
                                'ping_number': record.ping_number,
                                'number_beams': record.number_beams,
                                'frequency': record.frequency,
                                'sample_rate': record.sample_rate,
                                'transmit_power': record.transmit_power,
                                'pulse_width': record.pulse_width,
                                'sound_speed': record.sound_speed,
                                'bottom_range': record.bottom_range
                            }
                            
                            csvfile.write(f"{record.ofs},{record.channel_id},{record.seq},{record.time_ms},"
                                        f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},"
                                        f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},"
                                        f"{record.pitch_deg},{record.roll_deg},{record.heave_m},"
                                        f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},"
                                        f'"{json.dumps(extras, separators=(",", ":")).replace('"', '""')}"\n')
                            
                            record_count += 1
                            
                            if record_count % 25 == 0:
                                logging.info(f"Processed {record_count} 7K records")
                        else:
                            # Skip record data
                            record_size = record_header.get('size', 0)
                            if record_size > 64:
                                f.seek(f.tell() + (record_size - 64))
        
        except Exception as e:
            logging.error(f"Error parsing 7K records: {e}")
            raise
        
        logging.info(f"7K parsing completed: {record_count} records processed")
        return record_count, str(csv_path), str(log_path)
    
    def _parse_record_data(self, f, record_header: Dict, record_start: int) -> Optional[ResonRecord]:
        """Parse individual 7K record data"""
        try:
            record_type = record_header.get('record_type_id', 0)
            
            # Only process sonar/bathymetry records
            if record_type not in [7006, 7007, 7018, 7019]:  # Bathymetry, sidescan, v2 versions
                return None
            
            data_size = record_header.get('size', 0) - 64
            if data_size <= 0:
                return None
            
            data = f.read(data_size)
            if len(data) < 20:
                return None
            
            # Parse common fields
            timestamp = record_header.get('timestamp', 0)
            device_id = record_header.get('device_id', 0)
            
            # Convert timestamp to milliseconds (7K uses microseconds since Jan 1, 1900)
            # Simplified conversion
            time_ms = int((timestamp / 1000) % (24 * 3600 * 1000))
            
            # Parse record-specific data
            if record_type == 7006:  # Bathymetry
                record = self._parse_bathymetry_record(data, record_header, record_start, time_ms)
            elif record_type == 7007:  # Sidescan
                record = self._parse_sidescan_record(data, record_header, record_start, time_ms)
            elif record_type == 7018:  # V2 Bathymetry
                record = self._parse_v2_bathymetry_record(data, record_header, record_start, time_ms)
            elif record_type == 7019:  # V2 Sidescan
                record = self._parse_v2_sidescan_record(data, record_header, record_start, time_ms)
            else:
                return None
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing 7K record at offset {record_start}: {e}")
            return None
    
    def _parse_bathymetry_record(self, data: bytes, header: Dict, record_start: int, time_ms: int) -> Optional[ResonRecord]:
        """Parse bathymetry record (type 7006)"""
        try:
            if len(data) < 40:
                return None
            
            # Parse bathymetry header
            sonar_id = struct.unpack('<Q', data[0:8])[0]
            ping_number = struct.unpack('<I', data[8:12])[0]
            multi_ping = struct.unpack('<H', data[12:14])[0]
            number_beams = struct.unpack('<I', data[14:18])[0]
            reserved = struct.unpack('<B', data[18:19])[0]
            number_samples = struct.unpack('<I', data[19:23])[0]
            
            # Get sonar parameters from cached settings
            frequency = self.sonar_settings.get('frequency', 0.0) if self.sonar_settings else 0.0
            sample_rate = self.sonar_settings.get('sample_rate', 0.0) if self.sonar_settings else 0.0
            
            # Create basic bathymetry record
            record = ResonRecord(
                ofs=record_start,
                channel_id=0,  # Multibeam channel
                seq=ping_number,
                time_ms=time_ms,
                lat=0.0,  # Would need position record
                lon=0.0,  # Would need position record
                depth_m=0.0,  # Will be calculated from beam data
                sample_cnt=number_samples,
                sonar_ofs=record_start + 64,
                sonar_size=len(data),
                beam_deg=0.0,  # Would need attitude record
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                record_type_id=7006,
                device_id=header.get('device_id', 0),
                ping_number=ping_number,
                number_beams=number_beams,
                number_samples=number_samples,
                frequency=frequency,
                sample_rate=sample_rate
            )
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing bathymetry record: {e}")
            return None
    
    def _parse_sidescan_record(self, data: bytes, header: Dict, record_start: int, time_ms: int) -> Optional[ResonRecord]:
        """Parse sidescan record (type 7007)"""
        try:
            if len(data) < 32:
                return None
            
            # Parse sidescan header
            sonar_id = struct.unpack('<Q', data[0:8])[0]
            ping_number = struct.unpack('<I', data[8:12])[0]
            multi_ping = struct.unpack('<H', data[12:14])[0]
            beam_position = struct.unpack('<f', data[14:18])[0]
            control_flags = struct.unpack('<I', data[18:22])[0]
            number_samples = struct.unpack('<I', data[22:26])[0]
            nadir_depth = struct.unpack('<f', data[26:30])[0]
            
            # Get sonar parameters
            frequency = self.sonar_settings.get('frequency', 0.0) if self.sonar_settings else 0.0
            sample_rate = self.sonar_settings.get('sample_rate', 0.0) if self.sonar_settings else 0.0
            
            record = ResonRecord(
                ofs=record_start,
                channel_id=1,  # Sidescan channel
                seq=ping_number,
                time_ms=time_ms,
                lat=0.0,
                lon=0.0,
                depth_m=nadir_depth,
                sample_cnt=number_samples,
                sonar_ofs=record_start + 64,
                sonar_size=len(data),
                beam_deg=beam_position,
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                record_type_id=7007,
                device_id=header.get('device_id', 0),
                ping_number=ping_number,
                number_samples=number_samples,
                frequency=frequency,
                sample_rate=sample_rate,
                bottom_range=nadir_depth
            )
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing sidescan record: {e}")
            return None
    
    def _parse_v2_bathymetry_record(self, data: bytes, header: Dict, record_start: int, time_ms: int) -> Optional[ResonRecord]:
        """Parse version 2 bathymetry record (type 7018)"""
        # Similar to regular bathymetry but with extended fields
        return self._parse_bathymetry_record(data, header, record_start, time_ms)
    
    def _parse_v2_sidescan_record(self, data: bytes, header: Dict, record_start: int, time_ms: int) -> Optional[ResonRecord]:
        """Parse version 2 sidescan record (type 7019)"""
        # Similar to regular sidescan but with extended fields
        return self._parse_sidescan_record(data, header, record_start, time_ms)

# Test function
def test_reson_parser():
    """Test Reson S7K parser (requires S7K format test file)"""
    test_patterns = [
        r"c:\Temp\Garmin_RSD_releases\testing new design\*.s7k",
        r"c:\Temp\Garmin_RSD_releases\testing new design\*.7k",
        r"c:\Temp\Garmin_RSD_releases\testing new design\*.S7K"
    ]
    
    print("Testing Reson S7K Parser")
    print("=" * 40)
    
    found_files = []
    for pattern in test_patterns:
        import glob
        found_files.extend(glob.glob(pattern))
    
    if not found_files:
        print("No Reson S7K test files found")
        print("The parser is ready for use when S7K format files are available")
        print("\nSupported Reson systems:")
        for model_id, model_name in ResonParser.SEABAT_MODELS.items():
            print(f"  - {model_name}")
        return
    
    for test_file in found_files[:1]:  # Test first file only
        try:
            parser = ResonParser(test_file)
            
            print(f"Testing file: {test_file}")
            print(f"File supported: {parser.is_supported()}")
            print(f"Channels: {parser.get_channels()}")
            print(f"Record count: {parser.get_record_count()}")
            
            file_info = parser.get_file_info()
            print("\nFile Information:")
            for key, value in file_info.items():
                print(f"  {key}: {value}")
            
            # Parse first 3 records as test
            print("\nParsing first 3 records...")
            record_count, csv_path, log_path = parser.parse_records(max_records=3)
            print(f"Processed {record_count} records")
            print(f"CSV output: {csv_path}")
            print(f"Log output: {log_path}")
            
        except Exception as e:
            print(f"Error testing Reson parser: {e}")

if __name__ == "__main__":
    test_reson_parser()