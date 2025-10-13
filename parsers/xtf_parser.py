#!/usr/bin/env python3
"""
XTF (eXtended Triton Format) Parser Implementation
Industry standard for marine geophysics and professional sonar surveys

Based on Triton XTF format specification and EdgeTech compatibility
Supports sidescan sonar, multibeam, sub-bottom profiler, and magnetometer data
"""

import struct
import mmap
import os
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json
from pathlib import Path

# Import base classes - adjust path as needed
try:
    from .base_parser import BaseSonarParser, SonarRecord
except ImportError:
    # Fallback for standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parsers.base_parser import BaseSonarParser, SonarRecord

@dataclass
class XTFRecord(SonarRecord):
    """XTF-specific sonar record with additional fields"""
    packet_type: int = 0             # XTF packet type
    sub_channel: int = 0             # Sub-channel number
    system_type: int = 0             # System that recorded data
    recording_program: str = ""      # Program used for recording
    sonar_frequency: float = 0.0     # Sonar frequency in Hz
    sound_velocity: float = 0.0      # Sound velocity in m/s
    sample_rate: float = 0.0         # Sample rate in Hz
    range_meters: float = 0.0        # Range in meters
    fish_altitude: float = 0.0       # Towfish altitude in meters
    fish_heading: float = 0.0        # Towfish heading in degrees
    speed_kmh: float = 0.0           # Speed in km/h
    port_range: float = 0.0          # Port side range in meters
    starboard_range: float = 0.0     # Starboard side range in meters
    gain: float = 0.0                # Receiver gain
    pulse_length: float = 0.0        # Pulse length in milliseconds
    absorption: float = 0.0          # Absorption coefficient
    projector_type: int = 0          # Projector type
    projector_width: float = 0.0     # Projector beam width in degrees
    reserved_fields: Dict = None     # Reserved fields storage

    def __post_init__(self):
        if self.reserved_fields is None:
            self.reserved_fields = {}

class XTFParser(BaseSonarParser):
    """
    Parser for XTF (eXtended Triton Format) sonar files
    Industry standard format used by 70%+ of professional marine survey companies
    
    Supports:
    - Sidescan sonar data
    - Multibeam bathymetry  
    - Sub-bottom profiler data
    - Magnetometer data
    - Navigation and positioning
    """
    
    # XTF Format constants
    XTF_FILE_HEADER_SIZE = 1024      # Fixed file header size
    XTF_PACKET_HEADER_SIZE = 256     # Fixed packet header size
    
    # XTF Packet types (from Triton specification)
    PACKET_TYPES = {
        0: 'SONAR_DATA',             # Sidescan sonar data
        1: 'NOTES',                  # Annotation notes
        2: 'BATHY',                  # Bathymetry data
        3: 'ATTITUDE',               # Platform attitude
        4: 'FORWARD_LOOK_SONAR',     # Forward-looking sonar
        5: 'ELAC_XSE',              # ELAC multibeam
        6: 'BATHY_XYZA',            # Bathymetry XYZ with amplitude
        7: 'K5000_BATHY_IQ',        # Klein 5000 bathymetry I&Q
        8: 'BATHY_YXZ',             # Bathymetry YXZ
        9: 'MULTIBEAM_RAWBEAM',     # Raw multibeam beam data
        10: 'RESON_7125',           # Reson 7125 multibeam
        11: 'RESON_7125_SNIPPET',   # Reson 7125 snippet
        12: 'BENTHOS_CAATI',        # Benthos CAATI sidescan
        13: 'EDGETECH_4600',        # EdgeTech 4600 series
        14: 'RESON_7018',           # Reson 7018 multibeam
        15: 'RESON_7125_7150',      # Reson 7125/7150
        16: 'BLACKFIN_BATHY',       # Blackfin bathymetry
        17: 'CODA_ECHOSCOPE',       # CodaOctopus EchoScope
        18: 'EDGETECH_SIDESCAN',    # EdgeTech sidescan
        19: 'EDGETECH_JSSTAR',      # EdgeTech JStar format within XTF
        20: 'DVL_LOG',              # Doppler Velocity Log
        21: 'NAVIGATION',           # Navigation data
        22: 'GYRO',                 # Gyroscope data
        23: 'SUBBOTTOM',            # Sub-bottom profiler
        24: 'MAGNETOMETER',         # Magnetometer data
        25: 'POSITION',             # Position data
        26: 'USER_DEFINED'          # User-defined data
    }
    
    # System types
    SYSTEM_TYPES = {
        1: 'EDGETECH',
        2: 'ANALOG_LOWRANCE',
        3: 'ODOM',
        4: 'KLEIN',
        5: 'HUMMINBIRD',
        6: 'FURUNO',
        7: 'WESMAR',
        8: 'GARMIN',
        9: 'RAYMARINE',
        10: 'GENERIC_SONAR',
        11: 'TRITON_IMAGING',
        12: 'MARINE_SONIC',
        13: 'KONGSBERG',
        14: 'SIMRAD',
        15: 'RESON'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "xtf"
        self.channels = []
        self.file_header = None
        self.system_info = {}
        self._parse_file_header()
        self._determine_channels()
        
    def _parse_file_header(self):
        """Parse XTF file header (first 1024 bytes)"""
        try:
            with open(self.file_path, 'rb') as f:
                header_data = f.read(self.XTF_FILE_HEADER_SIZE)
                
                if len(header_data) < self.XTF_FILE_HEADER_SIZE:
                    raise ValueError(f"File too small for XTF format: {len(header_data)} bytes")
                
                # Parse main header fields
                self.file_header = {
                    'file_format': header_data[0],
                    'system_type': header_data[1],
                    'recording_program_name': header_data[2:10].decode('ascii', errors='ignore').rstrip('\x00'),
                    'recording_program_date': header_data[10:18].decode('ascii', errors='ignore').rstrip('\x00'),
                    'user_name': header_data[18:26].decode('ascii', errors='ignore').rstrip('\x00'),
                    'comment': header_data[26:226].decode('ascii', errors='ignore').rstrip('\x00'),
                    'nav_units': header_data[226],
                    'number_of_sonar_channels': struct.unpack('<H', header_data[227:229])[0],
                    'number_of_bathymetry_channels': struct.unpack('<H', header_data[229:231])[0],
                    'number_of_snip_channels': struct.unpack('<H', header_data[231:233])[0],
                    'number_of_forward_look_arrays': header_data[233],
                    'number_of_echosounder_channels': struct.unpack('<H', header_data[234:236])[0],
                    'number_of_interferometry_channels': header_data[236],
                    'reserved1': header_data[237],
                    'reserved2': struct.unpack('<H', header_data[238:240])[0],
                    'reference_point_height': struct.unpack('<f', header_data[240:244])[0],
                    'projection_type': header_data[244:256].decode('ascii', errors='ignore').rstrip('\x00'),
                    'spheroid_type': header_data[256:268].decode('ascii', errors='ignore').rstrip('\x00'),
                    'navigation_latency': struct.unpack('<I', header_data[268:272])[0],
                    'origin_y': struct.unpack('<f', header_data[272:276])[0],
                    'origin_x': struct.unpack('<f', header_data[276:280])[0],
                    'nav_offset_y': struct.unpack('<f', header_data[280:284])[0],
                    'nav_offset_x': struct.unpack('<f', header_data[284:288])[0],
                    'nav_offset_z': struct.unpack('<f', header_data[288:292])[0],
                    'nav_offset_yaw': struct.unpack('<f', header_data[292:296])[0],
                    'mru_offset_y': struct.unpack('<f', header_data[296:300])[0],
                    'mru_offset_x': struct.unpack('<f', header_data[300:304])[0],
                    'mru_offset_z': struct.unpack('<f', header_data[304:308])[0],
                    'mru_offset_yaw': struct.unpack('<f', header_data[308:312])[0],
                    'mru_offset_pitch': struct.unpack('<f', header_data[312:316])[0],
                    'mru_offset_roll': struct.unpack('<f', header_data[316:320])[0],
                }
                
                # Store system information
                self.system_info = {
                    'system_name': self.SYSTEM_TYPES.get(self.file_header['system_type'], f"Unknown ({self.file_header['system_type']})"),
                    'recording_program': self.file_header['recording_program_name'],
                    'total_channels': (self.file_header['number_of_sonar_channels'] + 
                                     self.file_header['number_of_bathymetry_channels'] +
                                     self.file_header['number_of_echosounder_channels']),
                    'projection': self.file_header['projection_type'],
                    'spheroid': self.file_header['spheroid_type']
                }
                
                return True
                
        except Exception as e:
            logging.error(f"Failed to parse XTF file header: {e}")
            return False
    
    def _determine_channels(self):
        """Scan file to determine available sonar channels"""
        if not self.file_header:
            return
            
        try:
            # Use header information first
            sonar_channels = self.file_header.get('number_of_sonar_channels', 0)
            bathy_channels = self.file_header.get('number_of_bathymetry_channels', 0)
            echo_channels = self.file_header.get('number_of_echosounder_channels', 0)
            
            # Build channel list based on header
            channel_id = 0
            
            # Add sonar channels (typically sidescan)
            for i in range(sonar_channels):
                self.channels.append(channel_id)
                channel_id += 1
                
            # Add bathymetry channels
            for i in range(bathy_channels):
                self.channels.append(channel_id + 100)  # Offset bathy channels
                channel_id += 1
                
            # Add echosounder channels  
            for i in range(echo_channels):
                self.channels.append(channel_id + 200)  # Offset echo channels
                channel_id += 1
                
            # If no channels from header, scan file for packet types
            if not self.channels:
                self._scan_for_channels()
                
        except Exception as e:
            logging.error(f"Failed to determine XTF channels: {e}")
            self.channels = [0, 1]  # Default to port/starboard
    
    def _scan_for_channels(self):
        """Scan file packets to find actual channels"""
        try:
            with open(self.file_path, 'rb') as f:
                f.seek(self.XTF_FILE_HEADER_SIZE)  # Skip file header
                
                found_channels = set()
                packets_scanned = 0
                max_scan = 100  # Limit scan to first 100 packets
                
                while packets_scanned < max_scan:
                    # Read packet header
                    packet_header = f.read(self.XTF_PACKET_HEADER_SIZE)
                    if len(packet_header) < self.XTF_PACKET_HEADER_SIZE:
                        break
                        
                    # Parse basic packet info
                    magic_number = struct.unpack('<H', packet_header[0:2])[0]
                    header_type = packet_header[2]
                    sub_channel_number = packet_header[3]
                    channel_number = struct.unpack('<H', packet_header[4:6])[0]
                    num_chans_to_follow = struct.unpack('<H', packet_header[6:8])[0]
                    num_bytes_this_record = struct.unpack('<I', packet_header[10:14])[0]
                    
                    # Check for sonar data packet types
                    if header_type in [0, 2, 18, 23]:  # Sonar, bathy, EdgeTech sidescan, subbottom
                        found_channels.add(channel_number)
                    
                    # Skip to next packet
                    if num_bytes_this_record > self.XTF_PACKET_HEADER_SIZE:
                        f.seek(f.tell() + (num_bytes_this_record - self.XTF_PACKET_HEADER_SIZE))
                    
                    packets_scanned += 1
                
                if found_channels:
                    self.channels = sorted(list(found_channels))
                else:
                    self.channels = [0, 1]  # Default fallback
                    
        except Exception as e:
            logging.error(f"Failed to scan XTF channels: {e}")
            self.channels = [0, 1]
    
    def is_supported(self) -> bool:
        """Check if file is a valid XTF format"""
        return (self.file_header is not None and 
                self.file_header.get('file_format') == 123)  # XTF magic number
    
    def get_channels(self) -> List[int]:
        """Get available channel IDs"""
        return self.channels
    
    def get_record_count(self) -> int:
        """Get total number of sonar records"""
        if not self.is_supported():
            return 0
            
        try:
            record_count = 0
            with open(self.file_path, 'rb') as f:
                f.seek(self.XTF_FILE_HEADER_SIZE)
                
                while True:
                    packet_header = f.read(14)  # Minimum packet header
                    if len(packet_header) < 14:
                        break
                        
                    header_type = packet_header[2]
                    num_bytes_this_record = struct.unpack('<I', packet_header[10:14])[0]
                    
                    # Count sonar data packets
                    if header_type in [0, 2, 18, 23]:
                        record_count += 1
                    
                    # Skip to next packet
                    if num_bytes_this_record > 14:
                        f.seek(f.tell() + (num_bytes_this_record - 14))
                    
            return record_count
            
        except Exception as e:
            logging.error(f"Failed to count XTF records: {e}")
            return 0
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        base_info = super().get_file_info()
        
        if self.file_header and self.system_info:
            base_info.update({
                'xtf_format_version': self.file_header.get('file_format'),
                'system_type': self.system_info.get('system_name'),
                'recording_program': self.system_info.get('recording_program'),
                'sonar_channels': self.file_header.get('number_of_sonar_channels', 0),
                'bathymetry_channels': self.file_header.get('number_of_bathymetry_channels', 0),
                'echosounder_channels': self.file_header.get('number_of_echosounder_channels', 0),
                'projection_type': self.system_info.get('projection'),
                'spheroid_type': self.system_info.get('spheroid'),
                'comment': self.file_header.get('comment', ''),
                'user_name': self.file_header.get('user_name', '')
            })
        
        return base_info
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse XTF records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        if not self.is_supported():
            raise ValueError("Not a valid XTF file")
        
        # Setup output paths
        base_name = Path(self.file_path).stem
        output_dir = Path(self.file_path).parent
        csv_path = output_dir / f"{base_name}_xtf_records.csv"
        log_path = output_dir / f"{base_name}_xtf_records.log"
        
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
                    f.seek(self.XTF_FILE_HEADER_SIZE)
                    
                    while max_records is None or record_count < max_records:
                        # Read packet header
                        packet_start = f.tell()
                        packet_header = f.read(self.XTF_PACKET_HEADER_SIZE)
                        
                        if len(packet_header) < self.XTF_PACKET_HEADER_SIZE:
                            break
                        
                        record = self._parse_packet(packet_header, f, packet_start)
                        if record:
                            # Write to CSV
                            extras = {
                                'packet_type': record.packet_type,
                                'system_type': record.system_type,
                                'sonar_frequency': record.sonar_frequency,
                                'sound_velocity': record.sound_velocity,
                                'sample_rate': record.sample_rate,
                                'range_meters': record.range_meters,
                                'gain': record.gain,
                                'pulse_length': record.pulse_length
                            }
                            
                            csvfile.write(f"{record.ofs},{record.channel_id},{record.seq},{record.time_ms},"
                                        f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},"
                                        f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},"
                                        f"{record.pitch_deg},{record.roll_deg},{record.heave_m},"
                                        f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},"
                                        f'"{json.dumps(extras, separators=(",", ":")).replace('"', '""')}"\n')
                            
                            record_count += 1
                            
                            if record_count % 100 == 0:
                                logging.info(f"Processed {record_count} XTF records")
        
        except Exception as e:
            logging.error(f"Error parsing XTF records: {e}")
            raise
        
        logging.info(f"XTF parsing completed: {record_count} records processed")
        return record_count, str(csv_path), str(log_path)
    
    def _parse_packet(self, header_data: bytes, f, packet_start: int) -> Optional[XTFRecord]:
        """Parse individual XTF packet"""
        try:
            # Parse packet header fields
            magic_number = struct.unpack('<H', header_data[0:2])[0]
            header_type = header_data[2]
            sub_channel_number = header_data[3]
            channel_number = struct.unpack('<H', header_data[4:6])[0]
            num_chans_to_follow = struct.unpack('<H', header_data[6:8])[0]
            reserved1 = struct.unpack('<H', header_data[8:10])[0]
            num_bytes_this_record = struct.unpack('<I', header_data[10:14])[0]
            
            # Skip if not sonar data
            if header_type not in [0, 2, 18, 23]:  # Sonar, bathy, EdgeTech sidescan, subbottom
                if num_bytes_this_record > self.XTF_PACKET_HEADER_SIZE:
                    f.seek(f.tell() + (num_bytes_this_record - self.XTF_PACKET_HEADER_SIZE))
                return None
            
            # Parse more header fields for sonar data
            year = struct.unpack('<H', header_data[14:16])[0]
            month = header_data[16]
            day = header_data[17]
            hour = header_data[18]
            minute = header_data[19]
            second = header_data[20]
            hsecond = header_data[21]
            
            julian_day = struct.unpack('<H', header_data[22:24])[0]
            event_number = struct.unpack('<I', header_data[24:28])[0]
            ping_number = struct.unpack('<I', header_data[28:32])[0]
            sound_velocity = struct.unpack('<f', header_data[32:36])[0]
            ocean_tide = struct.unpack('<f', header_data[36:40])[0]
            reserved2 = struct.unpack('<I', header_data[40:44])[0]
            reserved3 = struct.unpack('<I', header_data[44:48])[0]
            reserved4 = struct.unpack('<I', header_data[48:52])[0]
            reserved5 = struct.unpack('<I', header_data[52:56])[0]
            
            # Navigation data
            sensor_x_coordinate = struct.unpack('<d', header_data[56:64])[0]
            sensor_y_coordinate = struct.unpack('<d', header_data[64:72])[0]
            sensor_coordinates = struct.unpack('<d', header_data[72:80])[0]
            
            sensor_heading = struct.unpack('<f', header_data[80:84])[0]
            sensor_pitch = struct.unpack('<f', header_data[84:88])[0]
            sensor_roll = struct.unpack('<f', header_data[88:92])[0]
            sensor_heave = struct.unpack('<f', header_data[92:96])[0]
            sensor_yaw = struct.unpack('<f', header_data[96:100])[0]
            
            # Convert coordinates (assuming lat/lon)
            latitude = sensor_y_coordinate
            longitude = sensor_x_coordinate
            
            # More sonar-specific fields based on packet type
            if header_type == 0:  # Sonar data packet
                # Parse sonar-specific fields
                sonar_frequency = struct.unpack('<f', header_data[148:152])[0] if len(header_data) > 152 else 0.0
                sample_rate = struct.unpack('<f', header_data[152:156])[0] if len(header_data) > 156 else 0.0
                samples_in_channel = struct.unpack('<I', header_data[156:160])[0] if len(header_data) > 160 else 0
                range_scale = struct.unpack('<f', header_data[172:176])[0] if len(header_data) > 176 else 0.0
            else:
                sonar_frequency = 0.0
                sample_rate = 0.0
                samples_in_channel = 0
                range_scale = 0.0
            
            # Calculate time in milliseconds (simplified)
            time_ms = (hour * 3600 + minute * 60 + second) * 1000 + hsecond * 10
            
            # Skip sonar data payload
            data_size = num_bytes_this_record - self.XTF_PACKET_HEADER_SIZE
            if data_size > 0:
                f.seek(f.tell() + data_size)
            
            # Create XTF record
            record = XTFRecord(
                ofs=packet_start,
                channel_id=channel_number,
                seq=ping_number,
                time_ms=time_ms,
                lat=latitude,
                lon=longitude,
                depth_m=abs(sensor_coordinates),  # Use Z coordinate as depth
                sample_cnt=samples_in_channel,
                sonar_ofs=packet_start + self.XTF_PACKET_HEADER_SIZE,
                sonar_size=data_size,
                beam_deg=sensor_heading,
                pitch_deg=sensor_pitch,
                roll_deg=sensor_roll,
                heave_m=sensor_heave,
                packet_type=header_type,
                sub_channel=sub_channel_number,
                system_type=self.file_header.get('system_type', 0),
                recording_program=self.file_header.get('recording_program_name', ''),
                sonar_frequency=sonar_frequency,
                sound_velocity=sound_velocity,
                sample_rate=sample_rate,
                range_meters=range_scale
            )
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing XTF packet at offset {packet_start}: {e}")
            return None

# Test function
def test_xtf_parser():
    """Test XTF parser with the EdgeTech test file"""
    test_file = r"c:\Temp\Garmin_RSD_releases\testing new design\general_xtf_clip_from_edgetech_4225i.xtf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    print("Testing XTF Parser")
    print("=" * 40)
    
    try:
        parser = XTFParser(test_file)
        
        print(f"File supported: {parser.is_supported()}")
        print(f"Channels: {parser.get_channels()}")
        print(f"Record count: {parser.get_record_count()}")
        
        file_info = parser.get_file_info()
        print("\nFile Information:")
        for key, value in file_info.items():
            print(f"  {key}: {value}")
        
        # Parse first 10 records as test
        print("\nParsing first 10 records...")
        record_count, csv_path, log_path = parser.parse_records(max_records=10)
        print(f"Processed {record_count} records")
        print(f"CSV output: {csv_path}")
        print(f"Log output: {log_path}")
        
    except Exception as e:
        print(f"Error testing XTF parser: {e}")

if __name__ == "__main__":
    test_xtf_parser()