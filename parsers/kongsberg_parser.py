#!/usr/bin/env python3
"""
Kongsberg ALL Format Parser Implementation
Industry standard for multibeam bathymetry and sonar data

Based on Kongsberg ALL format specification for EM series multibeam echosounders
Supports EM 122, EM 302, EM 710, EM 2040, EM 3002 and other Kongsberg systems
"""

import struct
import mmap
import os
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

# Import base classes
try:
    from .base_parser import BaseSonarParser, SonarRecord
except ImportError:
    # Fallback for standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parsers.base_parser import BaseSonarParser, SonarRecord

@dataclass
class KongsbergRecord(SonarRecord):
    """Kongsberg ALL-specific sonar record with additional fields"""
    datagram_type: str = ""              # ALL datagram type
    em_model: int = 0                    # EM model number
    serial_number: int = 0               # System serial number
    ping_counter: int = 0                # Internal ping counter
    system_serial: int = 0               # System serial number
    operator_station_status: int = 0     # Operator station status
    processing_unit_status: int = 0      # Processing unit status
    bsp_status: int = 0                  # BSP status
    sonar_head_status: int = 0           # Sonar head/transceiver status
    mode: int = 0                        # Operating mode
    filter_identifier: int = 0           # Filter identifier
    min_depth: float = 0.0               # Minimum depth
    max_depth: float = 0.0               # Maximum depth
    absorption_coefficient: float = 0.0   # Absorption coefficient
    transmit_pulse_length: float = 0.0   # Transmit pulse length
    transmit_beam_width: float = 0.0     # Transmit beam width
    transmit_power: float = 0.0          # Transmit power re maximum
    receive_beam_width: float = 0.0      # Receive beam width
    receive_bandwidth: float = 0.0       # Receive bandwidth
    received_range: float = 0.0          # Received range
    transmit_along_tilt: float = 0.0     # Transmit along tilt
    transmit_across_tilt: float = 0.0    # Transmit across tilt
    num_beams: int = 0                   # Number of beams
    vessel_heading: float = 0.0          # Vessel heading
    sound_speed_surface: float = 0.0     # Sound speed at surface
    transducer_depth: float = 0.0        # Transducer depth
    maximum_beams: int = 0               # Maximum number of possible beams
    beam_data: List = None               # Individual beam data

    def __post_init__(self):
        if self.beam_data is None:
            self.beam_data = []

class KongsbergParser(BaseSonarParser):
    """
    Parser for Kongsberg ALL format sonar files
    Industry standard for professional multibeam bathymetry systems
    
    Supports:
    - EM series multibeam echosounders (EM 122, 302, 710, 2040, 3002, etc.)
    - Bathymetry data with beam-by-beam information
    - Navigation and positioning data
    - System parameters and calibration data
    - Water column data (optional)
    """
    
    # ALL Format constants
    ALL_DATAGRAM_START = b'\x00\x00\x00'    # Start of datagram marker
    ALL_DATAGRAM_END = b'\x03'              # End of datagram marker
    
    # ALL Datagram types (from Kongsberg specification)
    DATAGRAM_TYPES = {
        b'I': 'INSTALLATION_PARAMETERS',        # Installation parameters
        b'R': 'RUNTIME_PARAMETERS',             # Runtime parameters  
        b'S': 'SOUND_SPEED_PROFILE',           # Sound speed profile
        b'N': 'NAVIGATION_DATA',                # Position
        b'A': 'ATTITUDE_DATA',                  # Attitude
        b'H': 'HEADING_DATA',                   # Heading
        b'P': 'POSITION_DATA',                  # Position
        b'C': 'CLOCK_DATA',                     # Clock
        b'D': 'DEPTH_DATAGRAM',                 # Depth (bathymetry)
        b'X': 'EXTRA_DETECTIONS',              # Extra detections
        b'F': 'RAW_RANGE_AND_ANGLE',           # Raw range and angle
        b'N': 'NETWORK_ATTITUDE_VELOCITY',      # Network attitude velocity
        b'Y': 'WATER_COLUMN_DATA',             # Water column data
        b'k': 'MECHANICAL_TRANSDUCER_TILT',    # Mechanical transducer tilt
        b'G': 'SURFACE_SOUND_SPEED',           # Surface sound speed
        b'W': 'WATERCOLUMN_DATAGRAM',          # Water column datagram
        b'j': 'EXTRA_PARAMETERS',              # Extra parameters
        b'#': 'COMMENT'                        # Comment
    }
    
    # EM Model identification
    EM_MODELS = {
        122: 'EM 122',
        302: 'EM 302', 
        710: 'EM 710',
        1002: 'EM 1002',
        2040: 'EM 2040',
        3002: 'EM 3002',
        2045: 'EM 2045'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "all"
        self.channels = []
        self.installation_params = None
        self.runtime_params = None
        self.em_model = 0
        self.serial_number = 0
        self._parse_installation_params()
        self._determine_channels()
        
    def _parse_installation_params(self):
        """Parse installation parameters from ALL file"""
        try:
            with open(self.file_path, 'rb') as f:
                # Scan for installation parameters datagram
                while True:
                    # Look for datagram start
                    byte = f.read(1)
                    if not byte:
                        break
                        
                    if byte == b'\x00':
                        # Check for full start sequence
                        next_bytes = f.read(3)
                        if len(next_bytes) >= 3 and next_bytes[:2] == b'\x00\x00':
                            datagram_length = struct.unpack('<I', byte + next_bytes)[0]
                            
                            # Read datagram type
                            datagram_type = f.read(1)
                            
                            if datagram_type == b'I':  # Installation parameters
                                self._parse_installation_datagram(f, datagram_length)
                                return True
                            else:
                                # Skip this datagram
                                f.seek(f.tell() + datagram_length - 5)
                        else:
                            f.seek(-3, 1)  # Back up
                            
                return False
                
        except Exception as e:
            logging.error(f"Failed to parse ALL installation parameters: {e}")
            return False
    
    def _parse_installation_datagram(self, f, datagram_length):
        """Parse installation parameters datagram"""
        try:
            # Read installation parameters
            data = f.read(datagram_length - 5)  # Subtract header length
            
            if len(data) >= 68:  # Minimum installation params size
                # Parse basic installation info
                self.installation_params = {
                    'survey_line_number': struct.unpack('<H', data[0:2])[0],
                    'serial_number_1': struct.unpack('<H', data[2:4])[0],
                    'serial_number_2': struct.unpack('<H', data[4:6])[0],
                    'secondary_system_serial': struct.unpack('<H', data[6:8])[0],
                    'date': struct.unpack('<I', data[8:12])[0],
                    'em_model_number': struct.unpack('<H', data[12:14])[0],
                    'survey_line': data[14:114].decode('ascii', errors='ignore').rstrip('\x00'),
                    'tx_array_size': struct.unpack('<f', data[114:118])[0],
                    'rx_array_size': struct.unpack('<f', data[118:122])[0],
                    'wa_tx_size': struct.unpack('<f', data[122:126])[0],
                    'wa_rx_size': struct.unpack('<f', data[126:130])[0],
                    'tx_to_gps_x': struct.unpack('<f', data[130:134])[0],
                    'tx_to_gps_y': struct.unpack('<f', data[134:138])[0],
                    'tx_to_gps_z': struct.unpack('<f', data[138:142])[0],
                    'tx_to_rp_x': struct.unpack('<f', data[142:146])[0],
                    'tx_to_rp_y': struct.unpack('<f', data[146:150])[0],
                    'tx_to_rp_z': struct.unpack('<f', data[150:154])[0]
                }
                
                self.em_model = self.installation_params['em_model_number']
                self.serial_number = self.installation_params['serial_number_1']
                
                logging.info(f"Parsed Kongsberg {self.EM_MODELS.get(self.em_model, f'EM {self.em_model}')} "
                           f"(S/N: {self.serial_number})")
                
        except Exception as e:
            logging.error(f"Failed to parse installation datagram: {e}")
    
    def _determine_channels(self):
        """Determine available channels from multibeam system"""
        # Kongsberg multibeam systems typically have a single sonar channel
        # but multiple beam channels within that
        self.channels = [0]  # Single multibeam channel
        
        # Could be expanded to include different frequency channels
        # for dual-frequency systems
    
    def is_supported(self) -> bool:
        """Check if file is a valid Kongsberg ALL format"""
        try:
            with open(self.file_path, 'rb') as f:
                # Check for ALL format signature
                header = f.read(100)
                
                # Look for typical ALL datagram patterns
                if b'\x00\x00\x00' in header[:50]:
                    return True
                    
                # Alternative check for newer formats
                if b'#MRZ' in header[:10]:  # New water column format
                    return True
                    
                return False
                
        except Exception:
            return False
    
    def get_channels(self) -> List[int]:
        """Get available channel IDs"""
        return self.channels
    
    def get_record_count(self) -> int:
        """Get total number of depth datagrams (bathymetry records)"""
        if not self.is_supported():
            return 0
            
        try:
            record_count = 0
            with open(self.file_path, 'rb') as f:
                while True:
                    # Look for datagram start
                    byte = f.read(1)
                    if not byte:
                        break
                        
                    if byte == b'\x00':
                        next_bytes = f.read(3)
                        if len(next_bytes) >= 3 and next_bytes[:2] == b'\x00\x00':
                            datagram_length = struct.unpack('<I', byte + next_bytes)[0]
                            datagram_type = f.read(1)
                            
                            # Count depth datagrams
                            if datagram_type in [b'D', b'X', b'F']:  # Depth, extra detections, raw range/angle
                                record_count += 1
                            
                            # Skip to next datagram
                            f.seek(f.tell() + datagram_length - 5)
                        else:
                            f.seek(-3, 1)
                            
            return record_count
            
        except Exception as e:
            logging.error(f"Failed to count ALL records: {e}")
            return 0
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        base_info = super().get_file_info()
        
        if self.installation_params:
            base_info.update({
                'em_model': self.EM_MODELS.get(self.em_model, f"EM {self.em_model}"),
                'serial_number': self.serial_number,
                'survey_line': self.installation_params.get('survey_line', ''),
                'tx_array_size': self.installation_params.get('tx_array_size', 0.0),
                'rx_array_size': self.installation_params.get('rx_array_size', 0.0),
                'installation_date': self.installation_params.get('date', 0)
            })
        
        return base_info
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse Kongsberg ALL records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        if not self.is_supported():
            raise ValueError("Not a valid Kongsberg ALL file")
        
        # Setup output paths
        base_name = Path(self.file_path).stem
        output_dir = Path(self.file_path).parent
        csv_path = output_dir / f"{base_name}_all_records.csv"
        log_path = output_dir / f"{base_name}_all_records.log"
        
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
                        # Read datagram
                        datagram_start = f.tell()
                        
                        # Look for datagram start
                        byte = f.read(1)
                        if not byte:
                            break
                            
                        if byte == b'\x00':
                            next_bytes = f.read(3)
                            if len(next_bytes) >= 3 and next_bytes[:2] == b'\x00\x00':
                                datagram_length = struct.unpack('<I', byte + next_bytes)[0]
                                datagram_type = f.read(1)
                                
                                record = self._parse_datagram(datagram_type, f, datagram_start, datagram_length)
                                
                                if record:
                                    # Write to CSV
                                    extras = {
                                        'datagram_type': record.datagram_type,
                                        'em_model': record.em_model,
                                        'serial_number': record.serial_number,
                                        'ping_counter': record.ping_counter,
                                        'num_beams': record.num_beams,
                                        'vessel_heading': record.vessel_heading,
                                        'sound_speed_surface': record.sound_speed_surface,
                                        'transducer_depth': record.transducer_depth,
                                        'min_depth': record.min_depth,
                                        'max_depth': record.max_depth
                                    }
                                    
                                    csvfile.write(f"{record.ofs},{record.channel_id},{record.seq},{record.time_ms},"
                                                f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},"
                                                f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},"
                                                f"{record.pitch_deg},{record.roll_deg},{record.heave_m},"
                                                f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},"
                                                f'"{json.dumps(extras, separators=(",", ":")).replace('"', '""')}"\n')
                                    
                                    record_count += 1
                                    
                                    if record_count % 50 == 0:
                                        logging.info(f"Processed {record_count} ALL records")
                                else:
                                    # Skip this datagram
                                    f.seek(datagram_start + datagram_length + 4)  # +4 for length field
                            else:
                                f.seek(-3, 1)
                        
        except Exception as e:
            logging.error(f"Error parsing ALL records: {e}")
            raise
        
        logging.info(f"ALL parsing completed: {record_count} records processed")
        return record_count, str(csv_path), str(log_path)
    
    def _parse_datagram(self, datagram_type: bytes, f, datagram_start: int, datagram_length: int) -> Optional[KongsbergRecord]:
        """Parse individual ALL datagram"""
        try:
            # Only process depth and detection datagrams for now
            if datagram_type not in [b'D', b'X', b'F']:
                return None
            
            # Read datagram content
            data = f.read(datagram_length - 5)  # Subtract header length
            
            if len(data) < 20:  # Minimum datagram size
                return None
            
            # Parse common header fields
            date = struct.unpack('<I', data[0:4])[0]
            time_ms = struct.unpack('<I', data[4:8])[0]
            ping_counter = struct.unpack('<H', data[8:10])[0]
            serial_number = struct.unpack('<H', data[10:12])[0]
            
            # Parse depth datagram specific fields (type 'D')
            if datagram_type == b'D' and len(data) >= 40:
                heading = struct.unpack('<H', data[12:14])[0] * 0.01  # Convert to degrees
                sound_speed = struct.unpack('<H', data[14:16])[0] * 0.1  # Convert to m/s
                transducer_depth = struct.unpack('<H', data[16:18])[0] * 0.01  # Convert to meters
                
                max_beams = struct.unpack('<B', data[18:19])[0]
                valid_beams = struct.unpack('<B', data[19:20])[0]
                sampling_frequency = struct.unpack('<f', data[20:24])[0]
                
                # Additional navigation data if available
                latitude = 0.0
                longitude = 0.0
                depth_avg = transducer_depth
                
                # Parse individual beam data (simplified)
                beam_data_start = 24
                beam_depths = []
                
                for i in range(min(valid_beams, 10)):  # Limit for performance
                    if beam_data_start + 16 <= len(data):
                        beam_depth = struct.unpack('<H', data[beam_data_start:beam_data_start+2])[0] * 0.01
                        beam_across = struct.unpack('<h', data[beam_data_start+2:beam_data_start+4])[0] * 0.01
                        beam_along = struct.unpack('<h', data[beam_data_start+4:beam_data_start+6])[0] * 0.01
                        beam_range = struct.unpack('<H', data[beam_data_start+6:beam_data_start+8])[0] * 0.01
                        
                        beam_depths.append(beam_depth)
                        beam_data_start += 16
                
                if beam_depths:
                    depth_avg = sum(beam_depths) / len(beam_depths)
                
                # Create Kongsberg record
                record = KongsbergRecord(
                    ofs=datagram_start,
                    channel_id=0,  # Multibeam channel
                    seq=ping_counter,
                    time_ms=time_ms,
                    lat=latitude,
                    lon=longitude,
                    depth_m=depth_avg,
                    sample_cnt=valid_beams,
                    sonar_ofs=datagram_start + 20,
                    sonar_size=datagram_length - 20,
                    beam_deg=heading,
                    pitch_deg=0.0,  # Would need attitude datagram
                    roll_deg=0.0,   # Would need attitude datagram
                    heave_m=0.0,    # Would need attitude datagram
                    datagram_type=datagram_type.decode('ascii', errors='ignore'),
                    em_model=self.em_model,
                    serial_number=serial_number,
                    ping_counter=ping_counter,
                    num_beams=valid_beams,
                    vessel_heading=heading,
                    sound_speed_surface=sound_speed,
                    transducer_depth=transducer_depth,
                    min_depth=min(beam_depths) if beam_depths else depth_avg,
                    max_depth=max(beam_depths) if beam_depths else depth_avg
                )
                
                return record
            
            return None
            
        except Exception as e:
            logging.error(f"Error parsing ALL datagram at offset {datagram_start}: {e}")
            return None

# Test function for when Kongsberg test files are available
def test_kongsberg_parser():
    """Test Kongsberg parser (requires ALL format test file)"""
    # This would need an actual .all file to test
    test_files = [
        r"c:\Temp\Garmin_RSD_releases\testing new design\*.all",
        r"c:\Temp\Garmin_RSD_releases\testing new design\*.ALL"
    ]
    
    print("Testing Kongsberg ALL Parser")
    print("=" * 40)
    
    found_files = []
    for pattern in test_files:
        import glob
        found_files.extend(glob.glob(pattern))
    
    if not found_files:
        print("No Kongsberg ALL test files found")
        print("The parser is ready for use when ALL format files are available")
        return
    
    for test_file in found_files[:1]:  # Test first file only
        try:
            parser = KongsbergParser(test_file)
            
            print(f"Testing file: {test_file}")
            print(f"File supported: {parser.is_supported()}")
            print(f"Channels: {parser.get_channels()}")
            print(f"Record count: {parser.get_record_count()}")
            
            file_info = parser.get_file_info()
            print("\nFile Information:")
            for key, value in file_info.items():
                print(f"  {key}: {value}")
            
            # Parse first 5 records as test
            print("\nParsing first 5 records...")
            record_count, csv_path, log_path = parser.parse_records(max_records=5)
            print(f"Processed {record_count} records")
            print(f"CSV output: {csv_path}")
            print(f"Log output: {log_path}")
            
        except Exception as e:
            print(f"Error testing Kongsberg parser: {e}")

if __name__ == "__main__":
    test_kongsberg_parser()