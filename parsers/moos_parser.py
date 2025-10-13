#!/usr/bin/env python3
"""
MOOS (Mission Oriented Operating Suite) Format Parser Implementation
Standard for robotic and autonomous underwater vehicle (AUV) data logging

Based on MOOS-IvP community standard for autonomous marine vehicles
Supports real-time data streams from robotic sidescan sonar systems
"""

import os
import re
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json
from pathlib import Path
from datetime import datetime
import csv

# Import base classes
try:
    from .base_parser import BaseSonarParser, SonarRecord
except ImportError:
    # Fallback for standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parsers.base_parser import BaseSonarParser, SonarRecord

@dataclass
class MOOSRecord(SonarRecord):
    """MOOS-specific sonar record with additional fields"""
    moos_time: float = 0.0               # MOOS timestamp
    var_name: str = ""                   # MOOS variable name
    source_name: str = ""                # Source application name
    community: str = ""                  # MOOS community name
    message_type: str = ""               # MOOS message type
    original_value: str = ""             # Original MOOS value string
    sonar_ping_time: float = 0.0         # Sonar ping timestamp
    vehicle_name: str = ""               # Vehicle/robot name
    mission_mode: str = ""               # Mission mode (survey, transit, etc.)
    altitude_agl: float = 0.0            # Altitude above ground level
    vehicle_speed: float = 0.0           # Vehicle speed
    vehicle_heading: float = 0.0         # Vehicle heading
    current_drift: float = 0.0           # Current drift estimate
    battery_level: float = 0.0           # Battery level percentage
    payload_status: str = ""             # Payload system status
    nav_quality: float = 0.0             # Navigation quality metric
    range_to_bottom: float = 0.0         # Range to bottom measurement
    sonar_gain: float = 0.0              # Sonar gain setting
    transmit_power: float = 0.0          # Transmit power level
    frequency: float = 0.0               # Sonar frequency
    pulse_width: float = 0.0             # Pulse width setting

class MOOSParser(BaseSonarParser):
    """
    Parser for MOOS (Mission Oriented Operating Suite) log files
    Standard format for autonomous underwater vehicle data logging
    
    Supports:
    - Real-time robotic sidescan sonar data
    - AUV navigation and control data
    - Mission planning and execution logs
    - Multi-vehicle coordination data
    - Sensor fusion and environmental data
    - Remote operation command/control logs
    """
    
    # MOOS variable patterns for sonar data
    SONAR_VARIABLES = {
        'SONAR_RAW': 'raw_sonar_data',
        'SIDESCAN_PORT': 'port_sidescan',
        'SIDESCAN_STBD': 'starboard_sidescan', 
        'SONAR_RANGE': 'sonar_range',
        'SONAR_BEARING': 'sonar_bearing',
        'SONAR_PING': 'sonar_ping_data',
        'SSS_DATA': 'sidescan_sonar_data',
        'ACOUSTIC_IMAGE': 'acoustic_image_data',
        'BATHYMETRY': 'bathymetry_data',
        'SUB_BOTTOM': 'sub_bottom_data'
    }
    
    # Navigation and positioning variables
    NAV_VARIABLES = {
        'NAV_X': 'x_position',
        'NAV_Y': 'y_position', 
        'NAV_Z': 'z_position',
        'NAV_LAT': 'latitude',
        'NAV_LON': 'longitude',
        'NAV_DEPTH': 'depth',
        'NAV_ALTITUDE': 'altitude',
        'NAV_HEADING': 'heading',
        'NAV_SPEED': 'speed',
        'NAV_YAW': 'yaw',
        'NAV_PITCH': 'pitch',
        'NAV_ROLL': 'roll',
        'GPS_LAT': 'gps_latitude',
        'GPS_LON': 'gps_longitude'
    }
    
    # Vehicle control and status variables
    VEHICLE_VARIABLES = {
        'DESIRED_HEADING': 'desired_heading',
        'DESIRED_SPEED': 'desired_speed',
        'DESIRED_DEPTH': 'desired_depth',
        'MISSION_MODE': 'mission_mode',
        'VEHICLE_NAME': 'vehicle_name',
        'BATTERY_VOLTAGE': 'battery_voltage',
        'PAYLOAD_STATUS': 'payload_status',
        'ALTITUDE_AGL': 'altitude_above_ground',
        'RANGE_TO_BOTTOM': 'range_to_bottom'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "moos"
        self.channels = []
        self.moos_metadata = {}
        self.sonar_channels = {}
        self.navigation_data = {}
        self._parse_moos_header()
        self._determine_channels()
        
    def _parse_moos_header(self):
        """Parse MOOS log file header and metadata"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first few lines for MOOS log identification
                header_lines = []
                for i in range(20):
                    line = f.readline()
                    if not line:
                        break
                    header_lines.append(line.strip())
                
                # Look for MOOS log signature
                self.moos_metadata = {
                    'is_moos_log': False,
                    'version': 'unknown',
                    'community': 'unknown',
                    'start_time': 0.0,
                    'variables': set(),
                    'applications': set()
                }
                
                for line in header_lines:
                    # MOOS log identification patterns
                    if 'MOOS' in line.upper() or 'MOOSLOG' in line.upper():
                        self.moos_metadata['is_moos_log'] = True
                    
                    # Version detection
                    if 'VERSION' in line.upper():
                        version_match = re.search(r'(\d+\.\d+)', line)
                        if version_match:
                            self.moos_metadata['version'] = version_match.group(1)
                    
                    # Community detection
                    if 'COMMUNITY' in line.upper():
                        comm_match = re.search(r'COMMUNITY[:\s]+(\w+)', line.upper())
                        if comm_match:
                            self.moos_metadata['community'] = comm_match.group(1)
                
                # If not obvious MOOS file, check for MOOS data patterns
                if not self.moos_metadata['is_moos_log']:
                    self._check_moos_data_patterns(f)
                
        except Exception as e:
            logging.error(f"Failed to parse MOOS header: {e}")
    
    def _check_moos_data_patterns(self, f):
        """Check for MOOS data patterns in file content"""
        try:
            f.seek(0)
            sample_lines = []
            for i in range(100):  # Check first 100 lines
                line = f.readline()
                if not line:
                    break
                sample_lines.append(line.strip())
            
            # Look for MOOS variable patterns
            moos_patterns = [
                r'^\d+\.\d+\s+\w+\s+\w+\s+',  # timestamp var source pattern
                r'NAV_[XYZ]',                   # Navigation variables
                r'DESIRED_\w+',                 # Control variables
                r'SONAR_\w+',                   # Sonar variables
                r'MISSION_\w+',                 # Mission variables
            ]
            
            pattern_matches = 0
            for line in sample_lines:
                for pattern in moos_patterns:
                    if re.search(pattern, line):
                        pattern_matches += 1
                        break
            
            # If enough patterns match, assume MOOS format
            if pattern_matches >= 5:
                self.moos_metadata['is_moos_log'] = True
                logging.info(f"Detected MOOS format based on data patterns ({pattern_matches} matches)")
                
        except Exception as e:
            logging.error(f"Error checking MOOS patterns: {e}")
    
    def _determine_channels(self):
        """Scan file to determine sonar channels from MOOS variables"""
        if not self.moos_metadata.get('is_moos_log', False):
            return
            
        try:
            channel_id = 0
            found_variables = set()
            
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = 0
                while line_count < 1000:  # Scan first 1000 lines
                    line = f.readline()
                    if not line:
                        break
                    
                    line_count += 1
                    
                    # Parse MOOS log line format: timestamp variable source value
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        variable = parts[1]
                        source = parts[2]
                        
                        found_variables.add(variable)
                        
                        # Check for sonar variables
                        if any(var in variable.upper() for var in self.SONAR_VARIABLES.keys()):
                            if variable not in self.sonar_channels:
                                self.sonar_channels[variable] = channel_id
                                self.channels.append(channel_id)
                                channel_id += 1
            
            self.moos_metadata['variables'] = found_variables
            
            # If no explicit sonar channels found, create default channels
            if not self.channels:
                self.channels = [0, 1]  # Default port/starboard
                
        except Exception as e:
            logging.error(f"Failed to determine MOOS channels: {e}")
            self.channels = [0, 1]
    
    def is_supported(self) -> bool:
        """Check if file is a valid MOOS log format"""
        return self.moos_metadata.get('is_moos_log', False)
    
    def get_channels(self) -> List[int]:
        """Get available channel IDs"""
        return self.channels
    
    def get_record_count(self) -> int:
        """Get total number of sonar-related records"""
        if not self.is_supported():
            return 0
            
        try:
            record_count = 0
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        variable = parts[1]
                        if any(var in variable.upper() for var in self.SONAR_VARIABLES.keys()):
                            record_count += 1
                            
            return record_count
            
        except Exception as e:
            logging.error(f"Failed to count MOOS records: {e}")
            return 0
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        base_info = super().get_file_info()
        
        if self.moos_metadata:
            base_info.update({
                'moos_version': self.moos_metadata.get('version', 'unknown'),
                'community': self.moos_metadata.get('community', 'unknown'),
                'variable_count': len(self.moos_metadata.get('variables', [])),
                'sonar_channels_found': len(self.sonar_channels),
                'sonar_variables': list(self.sonar_channels.keys()),
                'start_time': self.moos_metadata.get('start_time', 0.0)
            })
        
        return base_info
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse MOOS records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        if not self.is_supported():
            raise ValueError("Not a valid MOOS log file")
        
        # Setup output paths
        base_name = Path(self.file_path).stem
        output_dir = Path(self.file_path).parent
        csv_path = output_dir / f"{base_name}_moos_records.csv"
        log_path = output_dir / f"{base_name}_moos_records.log"
        
        # Setup logging
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )
        
        record_count = 0
        current_nav = {}  # Store latest navigation data
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write CSV header
                csvfile.write("ofs,channel_id,seq,time_ms,lat,lon,depth_m,sample_cnt,sonar_ofs,sonar_size,"
                            "beam_deg,pitch_deg,roll_deg,heave_m,tx_ofs_m,rx_ofs_m,color_id,extras_json\n")
                
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    line_number = 0
                    
                    while max_records is None or record_count < max_records:
                        file_position = f.tell()
                        line = f.readline()
                        line_number += 1
                        
                        if not line:
                            break
                        
                        record = self._parse_moos_line(line.strip(), file_position, line_number, current_nav)
                        
                        if record:
                            # Write to CSV
                            extras = {
                                'moos_time': record.moos_time,
                                'var_name': record.var_name,
                                'source_name': record.source_name,
                                'community': record.community,
                                'message_type': record.message_type,
                                'vehicle_name': record.vehicle_name,
                                'mission_mode': record.mission_mode,
                                'altitude_agl': record.altitude_agl,
                                'vehicle_speed': record.vehicle_speed,
                                'vehicle_heading': record.vehicle_heading,
                                'battery_level': record.battery_level,
                                'frequency': record.frequency,
                                'sonar_gain': record.sonar_gain
                            }
                            
                            csvfile.write(f"{record.ofs},{record.channel_id},{record.seq},{record.time_ms},"
                                        f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},"
                                        f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},"
                                        f"{record.pitch_deg},{record.roll_deg},{record.heave_m},"
                                        f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},"
                                        f'"{json.dumps(extras, separators=(",", ":")).replace('"', '""')}"\n')
                            
                            record_count += 1
                            
                            if record_count % 100 == 0:
                                logging.info(f"Processed {record_count} MOOS records")
        
        except Exception as e:
            logging.error(f"Error parsing MOOS records: {e}")
            raise
        
        logging.info(f"MOOS parsing completed: {record_count} records processed")
        return record_count, str(csv_path), str(log_path)
    
    def _parse_moos_line(self, line: str, file_pos: int, line_num: int, current_nav: Dict) -> Optional[MOOSRecord]:
        """Parse individual MOOS log line"""
        try:
            parts = line.split()
            if len(parts) < 4:
                return None
            
            # Basic MOOS format: timestamp variable source value [additional...]
            timestamp = float(parts[0])
            variable = parts[1]
            source = parts[2]
            value = ' '.join(parts[3:])  # Join remaining parts as value
            
            # Update navigation data cache
            if variable.upper() in self.NAV_VARIABLES:
                try:
                    current_nav[variable.upper()] = float(value)
                except ValueError:
                    current_nav[variable.upper()] = value
            
            # Only process sonar-related variables
            if not any(var in variable.upper() for var in self.SONAR_VARIABLES.keys()):
                return None
            
            # Determine channel ID
            channel_id = self.sonar_channels.get(variable, 0)
            
            # Extract navigation from cache
            latitude = current_nav.get('NAV_LAT', current_nav.get('GPS_LAT', 0.0))
            longitude = current_nav.get('NAV_LON', current_nav.get('GPS_LON', 0.0))
            depth = current_nav.get('NAV_DEPTH', current_nav.get('NAV_Z', 0.0))
            heading = current_nav.get('NAV_HEADING', current_nav.get('NAV_YAW', 0.0))
            pitch = current_nav.get('NAV_PITCH', 0.0)
            roll = current_nav.get('NAV_ROLL', 0.0)
            speed = current_nav.get('NAV_SPEED', 0.0)
            altitude = current_nav.get('NAV_ALTITUDE', current_nav.get('ALTITUDE_AGL', 0.0))
            
            # Convert timestamp to milliseconds
            time_ms = int(timestamp * 1000)
            
            # Parse sonar-specific data from value
            sample_count = 0
            sonar_size = len(value.encode('utf-8'))
            frequency = 0.0
            gain = 0.0
            
            # Try to extract sonar parameters from value string
            if 'FREQ=' in value.upper():
                freq_match = re.search(r'FREQ=(\d+\.?\d*)', value.upper())
                if freq_match:
                    frequency = float(freq_match.group(1))
            
            if 'GAIN=' in value.upper():
                gain_match = re.search(r'GAIN=(\d+\.?\d*)', value.upper())
                if gain_match:
                    gain = float(gain_match.group(1))
            
            if 'SAMPLES=' in value.upper():
                samples_match = re.search(r'SAMPLES=(\d+)', value.upper())
                if samples_match:
                    sample_count = int(samples_match.group(1))
            
            # Create MOOS record
            record = MOOSRecord(
                ofs=file_pos,
                channel_id=channel_id,
                seq=line_num,
                time_ms=time_ms,
                lat=latitude,
                lon=longitude,
                depth_m=abs(depth) if isinstance(depth, (int, float)) else 0.0,
                sample_cnt=sample_count,
                sonar_ofs=file_pos,
                sonar_size=sonar_size,
                beam_deg=heading if isinstance(heading, (int, float)) else 0.0,
                pitch_deg=pitch if isinstance(pitch, (int, float)) else 0.0,
                roll_deg=roll if isinstance(roll, (int, float)) else 0.0,
                heave_m=0.0,  # Not typically available in MOOS
                moos_time=timestamp,
                var_name=variable,
                source_name=source,
                community=self.moos_metadata.get('community', ''),
                message_type='LOG_ENTRY',
                original_value=value,
                vehicle_speed=speed if isinstance(speed, (int, float)) else 0.0,
                vehicle_heading=heading if isinstance(heading, (int, float)) else 0.0,
                altitude_agl=altitude if isinstance(altitude, (int, float)) else 0.0,
                frequency=frequency,
                sonar_gain=gain,
                mission_mode=current_nav.get('MISSION_MODE', ''),
                vehicle_name=current_nav.get('VEHICLE_NAME', '')
            )
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing MOOS line {line_num}: {e}")
            return None

# Test function
def test_moos_parser():
    """Test MOOS parser (create sample MOOS log for testing)"""
    test_dir = Path(r"c:\Temp\Garmin_RSD_releases\testing new design")
    test_file = test_dir / "sample_moos_log.moos"
    
    print("Testing MOOS Parser Implementation")
    print("=" * 40)
    
    # Create a sample MOOS log file for testing
    try:
        sample_moos_data = """# MOOS Log File - Autonomous Underwater Vehicle Survey Mission
# Community: AUV_SURVEY  Version: 2.5  
# Start Time: 1234567890.0
1234567890.123 NAV_LAT pNav 42.123456
1234567890.456 NAV_LON pNav -71.234567
1234567890.789 NAV_DEPTH pNav 15.5
1234567891.012 NAV_HEADING pNav 90.5
1234567891.234 SONAR_RAW pSonar FREQ=400000 GAIN=50 SAMPLES=1024 DATA=binary_data_here
1234567891.567 SIDESCAN_PORT pSidescan FREQ=900000 RANGE=100 GAIN=45 SAMPLES=2048
1234567891.890 SIDESCAN_STBD pSidescan FREQ=900000 RANGE=100 GAIN=45 SAMPLES=2048
1234567892.123 NAV_SPEED pNav 2.5
1234567892.456 MISSION_MODE pMission SURVEY_LINE_01
1234567892.789 VEHICLE_NAME pVehicle BLUEFIN_AUV_21
1234567893.012 ALTITUDE_AGL pNav 3.2
1234567893.345 SONAR_PING pSonar PING=14500 FREQ=400000 POWER=75
1234567893.678 BATTERY_VOLTAGE pPower 24.6V
1234567894.012 RANGE_TO_BOTTOM pSonar 18.7
"""
        
        with open(test_file, 'w') as f:
            f.write(sample_moos_data)
        
        print(f"Created sample MOOS log: {test_file}")
        
        # Test the parser
        parser = MOOSParser(str(test_file))
        
        print(f"File supported: {parser.is_supported()}")
        print(f"Channels: {parser.get_channels()}")
        print(f"Record count: {parser.get_record_count()}")
        
        file_info = parser.get_file_info()
        print("\nFile Information:")
        for key, value in file_info.items():
            print(f"  {key}: {value}")
        
        # Parse all records as test
        print("\nParsing all records...")
        record_count, csv_path, log_path = parser.parse_records()
        print(f"Processed {record_count} records")
        print(f"CSV output: {csv_path}")
        print(f"Log output: {log_path}")
        
        # Clean up test file
        test_file.unlink()
        
    except Exception as e:
        print(f"Error testing MOOS parser: {e}")

if __name__ == "__main__":
    test_moos_parser()