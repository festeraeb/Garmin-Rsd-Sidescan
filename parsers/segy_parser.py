#!/usr/bin/env python3
"""
SEG-Y Seismic Format Parser Implementation
Industry standard for marine seismic and sub-bottom profiler data

Based on SEG-Y Revision 2.0 specification from Society of Exploration Geophysicists
Supports marine seismic surveys, sub-bottom profiling, and acoustic sediment analysis
"""

import struct
import os
from typing import Iterator, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging
import json
from pathlib import Path
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
class SEGYRecord(SonarRecord):
    """SEG-Y specific seismic record with additional fields"""
    trace_sequence_line: int = 0         # Trace sequence number within line
    trace_sequence_file: int = 0         # Trace sequence number within file
    field_record_number: int = 0         # Original field record number
    trace_number: int = 0                # Trace number within field record
    energy_source_point: int = 0         # Energy source point number
    ensemble_number: int = 0             # Ensemble number (CDP, CMP, CRP)
    trace_number_ensemble: int = 0       # Trace number within ensemble
    trace_identification_code: int = 0   # Trace identification code
    num_vertically_summed: int = 0       # Number of vertically summed traces
    num_horizontally_stacked: int = 0    # Number of horizontally stacked traces
    data_use: int = 0                    # Data use (1=production, 2=test)
    
    # Geometry and positioning
    distance_center_shot: int = 0        # Distance from center of shot point to receiver
    receiver_group_elevation: int = 0    # Receiver group elevation
    surface_elevation_shot: int = 0      # Surface elevation at shot point
    source_depth_below_surface: int = 0  # Source depth below surface
    datum_elevation_receiver: int = 0    # Datum elevation at receiver group
    datum_elevation_shot: int = 0        # Datum elevation at shot point
    water_depth_shot: int = 0            # Water depth at shot point
    water_depth_receiver: int = 0        # Water depth at receiver group
    
    # Coordinate information
    coordinate_scalar: int = 0           # Scalar for coordinates
    coordinate_units: int = 0            # Coordinate units
    source_x: int = 0                    # Source coordinate X
    source_y: int = 0                    # Source coordinate Y
    receiver_x: int = 0                  # Receiver coordinate X
    receiver_y: int = 0                  # Receiver coordinate Y
    
    # Time and sampling
    lag_time_a: int = 0                  # Lag time A
    lag_time_b: int = 0                  # Lag time B
    delay_recording_time: int = 0        # Delay recording time
    mute_time_start: int = 0             # Mute time start
    mute_time_end: int = 0               # Mute time end
    samples_per_trace: int = 0           # Number of samples per trace
    sample_interval: int = 0             # Sample interval in microseconds
    gain_type: int = 0                   # Gain type
    instrument_gain_constant: int = 0    # Instrument gain constant
    instrument_early_gain: int = 0       # Instrument early or initial gain
    correlated_data: int = 0             # Correlated data (1=no, 2=yes)
    sweep_frequency_start: int = 0       # Sweep frequency at start
    sweep_frequency_end: int = 0         # Sweep frequency at end
    sweep_length: int = 0                # Sweep length in milliseconds
    sweep_type: int = 0                  # Sweep type
    sweep_taper_length_start: int = 0    # Sweep taper length at start
    sweep_taper_length_end: int = 0      # Sweep taper length at end
    taper_type: int = 0                  # Taper type
    alias_filter_frequency: int = 0      # Alias filter frequency
    alias_filter_slope: int = 0          # Alias filter slope
    notch_filter_frequency: int = 0      # Notch filter frequency
    notch_filter_slope: int = 0          # Notch filter slope
    low_cut_frequency: int = 0           # Low cut frequency
    high_cut_frequency: int = 0          # High cut frequency
    low_cut_slope: int = 0               # Low cut slope
    high_cut_slope: int = 0              # High cut slope
    
    # Additional fields
    year: int = 0                        # Year data recorded
    day_of_year: int = 0                 # Day of year
    hour: int = 0                        # Hour of day
    minute: int = 0                      # Minute of hour
    second: int = 0                      # Second of minute
    time_basis_code: int = 0             # Time basis code
    trace_weighting_factor: int = 0      # Trace weighting factor
    geophone_group_number_roll: int = 0  # Geophone group number of roll switch
    geophone_group_number_first: int = 0 # Geophone group number of first trace
    geophone_group_number_last: int = 0  # Geophone group number of last trace
    gap_size: int = 0                    # Gap size
    over_travel: int = 0                 # Over travel
    
    # Data format and trace data
    data_format_code: int = 0            # Data sample format code
    trace_data: List = None              # Actual seismic trace data

    def __post_init__(self):
        if self.trace_data is None:
            self.trace_data = []

class SEGYParser(BaseSonarParser):
    """
    Parser for SEG-Y seismic format files
    Industry standard for marine seismic surveys and sub-bottom profiling
    
    Supports:
    - Marine seismic reflection surveys
    - Sub-bottom profiler data
    - Acoustic sediment analysis
    - High-resolution shallow seismic
    - Chirp sonar data
    - Parametric echo sounder data
    """
    
    # SEG-Y format constants
    SEGY_HEADER_SIZE = 3600              # 3200 text + 400 binary header
    TRACE_HEADER_SIZE = 240              # Trace header size
    
    # Data sample format codes
    DATA_FORMATS = {
        1: ('IBM_FLOAT', 4),             # 4-byte IBM floating point
        2: ('INT32', 4),                 # 4-byte two's complement integer
        3: ('INT16', 2),                 # 2-byte two's complement integer
        4: ('GAIN_CONSTANT', 4),         # 4-byte fixed-point with gain
        5: ('IEEE_FLOAT', 4),            # 4-byte IEEE floating point
        6: ('IEEE_DOUBLE', 8),           # 8-byte IEEE floating point
        7: ('INT24', 3),                 # 3-byte two's complement integer
        8: ('INT8', 1),                  # 1-byte two's complement integer
        9: ('INT64', 8),                 # 8-byte two's complement integer
        10: ('UINT32', 4),               # 4-byte unsigned integer
        11: ('UINT16', 2),               # 2-byte unsigned integer
        12: ('UINT64', 8),               # 8-byte unsigned integer
        15: ('UINT24', 3),               # 3-byte unsigned integer
        16: ('UINT8', 1)                 # 1-byte unsigned integer
    }
    
    # Coordinate units
    COORDINATE_UNITS = {
        1: 'LENGTH_METERS',
        2: 'LENGTH_FEET',
        3: 'ARC_SECONDS',
        4: 'DECIMAL_DEGREES',
        5: 'DECIMAL_MINUTES',
        6: 'DECIMAL_SECONDS'
    }
    
    # Trace identification codes
    TRACE_ID_CODES = {
        1: 'SEISMIC_DATA',
        2: 'DEAD_TRACE',
        3: 'DUMMY_TRACE',
        4: 'TIME_BREAK',
        5: 'UPHOLE',
        6: 'SWEEP',
        7: 'TIMING',
        8: 'WATER_BREAK',
        9: 'NEAR_FIELD_GUN',
        10: 'FAR_FIELD_GUN',
        11: 'SEISMIC_OTHER'
    }
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "segy"
        self.channels = []
        self.text_header = ""
        self.binary_header = None
        self.trace_info = {}
        self._parse_headers()
        self._determine_channels()
        
    def _parse_headers(self):
        """Parse SEG-Y text and binary headers"""
        try:
            with open(self.file_path, 'rb') as f:
                # Read text header (3200 bytes EBCDIC)
                text_data = f.read(3200)
                if len(text_data) < 3200:
                    logging.error("File too small for SEG-Y format")
                    return False
                
                # Convert EBCDIC to ASCII (simplified)
                self.text_header = self._ebcdic_to_ascii(text_data)
                
                # Read binary header (400 bytes)
                binary_data = f.read(400)
                if len(binary_data) < 400:
                    logging.error("Incomplete SEG-Y binary header")
                    return False
                
                self._parse_binary_header(binary_data)
                
                # Analyze first few traces for additional info
                self._analyze_trace_structure(f)
                
                return True
                
        except Exception as e:
            logging.error(f"Failed to parse SEG-Y headers: {e}")
            return False
    
    def _ebcdic_to_ascii(self, ebcdic_data: bytes) -> str:
        """Convert EBCDIC text header to ASCII (simplified conversion)"""
        try:
            # Simple EBCDIC to ASCII conversion
            # In production, would use proper EBCDIC codepage
            ascii_chars = []
            for byte in ebcdic_data:
                if 64 <= byte <= 249:  # Printable EBCDIC range
                    ascii_chars.append(chr(byte - 64 + 32))
                elif byte == 64:  # EBCDIC space
                    ascii_chars.append(' ')
                else:
                    ascii_chars.append('.')
            
            return ''.join(ascii_chars)
            
        except Exception:
            return "EBCDIC conversion failed"
    
    def _parse_binary_header(self, data: bytes):
        """Parse SEG-Y binary header"""
        try:
            self.binary_header = {
                'job_identification': struct.unpack('>I', data[0:4])[0],
                'line_number': struct.unpack('>I', data[4:8])[0],
                'reel_number': struct.unpack('>I', data[8:12])[0],
                'traces_per_ensemble': struct.unpack('>H', data[12:14])[0],
                'auxiliary_traces_per_ensemble': struct.unpack('>H', data[14:16])[0],
                'sample_interval': struct.unpack('>H', data[16:18])[0],  # Microseconds
                'sample_interval_original': struct.unpack('>H', data[18:20])[0],
                'samples_per_trace': struct.unpack('>H', data[20:22])[0],
                'samples_per_trace_original': struct.unpack('>H', data[22:24])[0],
                'data_sample_format': struct.unpack('>H', data[24:26])[0],
                'ensemble_fold': struct.unpack('>H', data[26:28])[0],
                'trace_sorting': struct.unpack('>H', data[28:30])[0],
                'vertical_sum_code': struct.unpack('>H', data[30:32])[0],
                'sweep_frequency_start': struct.unpack('>H', data[32:34])[0],
                'sweep_frequency_end': struct.unpack('>H', data[34:36])[0],
                'sweep_length': struct.unpack('>H', data[36:38])[0],
                'sweep_type': struct.unpack('>H', data[38:40])[0],
                'trace_number_sweep_channel': struct.unpack('>H', data[40:42])[0],
                'sweep_taper_length_start': struct.unpack('>H', data[42:44])[0],
                'sweep_taper_length_end': struct.unpack('>H', data[44:46])[0],
                'taper_type': struct.unpack('>H', data[46:48])[0],
                'correlated_data_traces': struct.unpack('>H', data[48:50])[0],
                'binary_gain_recovered': struct.unpack('>H', data[50:52])[0],
                'amplitude_recovery_method': struct.unpack('>H', data[52:54])[0],
                'measurement_system': struct.unpack('>H', data[54:56])[0],
                'impulse_signal_polarity': struct.unpack('>H', data[56:58])[0],
                'vibratory_polarity_code': struct.unpack('>H', data[58:60])[0],
                'segy_format_revision': struct.unpack('>H', data[300:302])[0],
                'fixed_length_trace_flag': struct.unpack('>H', data[302:304])[0],
                'extended_textual_headers': struct.unpack('>H', data[304:306])[0]
            }
            
            # Log key information
            format_code = self.binary_header.get('data_sample_format', 0)
            samples_per_trace = self.binary_header.get('samples_per_trace', 0)
            sample_interval = self.binary_header.get('sample_interval', 0)
            
            logging.info(f"SEG-Y Format: Rev {self.binary_header.get('segy_format_revision', 0)}")
            logging.info(f"Data format: {format_code} ({self.DATA_FORMATS.get(format_code, ('Unknown', 0))[0]})")
            logging.info(f"Samples per trace: {samples_per_trace}")
            logging.info(f"Sample interval: {sample_interval} μs")
            
        except Exception as e:
            logging.error(f"Failed to parse binary header: {e}")
    
    def _analyze_trace_structure(self, f):
        """Analyze first few traces to understand file structure"""
        try:
            traces_analyzed = 0
            max_analyze = 5
            
            while traces_analyzed < max_analyze:
                trace_start = f.tell()
                
                # Read trace header
                trace_header = f.read(self.TRACE_HEADER_SIZE)
                if len(trace_header) < self.TRACE_HEADER_SIZE:
                    break
                
                # Parse basic trace header info
                trace_seq_line = struct.unpack('>I', trace_header[0:4])[0]
                trace_seq_file = struct.unpack('>I', trace_header[4:8])[0]
                samples_this_trace = struct.unpack('>H', trace_header[114:116])[0]
                sample_interval_this_trace = struct.unpack('>H', trace_header[116:118])[0]
                
                # Use binary header default if trace header is zero
                if samples_this_trace == 0:
                    samples_this_trace = self.binary_header.get('samples_per_trace', 0)
                if sample_interval_this_trace == 0:
                    sample_interval_this_trace = self.binary_header.get('sample_interval', 0)
                
                # Calculate trace data size
                format_code = self.binary_header.get('data_sample_format', 1)
                bytes_per_sample = self.DATA_FORMATS.get(format_code, ('Unknown', 4))[1]
                trace_data_size = samples_this_trace * bytes_per_sample
                
                # Store trace info
                if traces_analyzed == 0:
                    self.trace_info = {
                        'samples_per_trace': samples_this_trace,
                        'sample_interval_us': sample_interval_this_trace,
                        'bytes_per_sample': bytes_per_sample,
                        'trace_data_size': trace_data_size,
                        'total_trace_size': self.TRACE_HEADER_SIZE + trace_data_size
                    }
                
                # Skip trace data
                f.seek(f.tell() + trace_data_size)
                traces_analyzed += 1
                
        except Exception as e:
            logging.error(f"Failed to analyze trace structure: {e}")
    
    def _determine_channels(self):
        """Determine channels from SEG-Y data characteristics"""
        if not self.binary_header:
            self.channels = [0]
            return
        
        # SEG-Y typically represents single-channel seismic data
        # But may have multiple traces per shot (multichannel)
        traces_per_ensemble = self.binary_header.get('traces_per_ensemble', 1)
        
        if traces_per_ensemble > 1:
            # Multichannel seismic
            self.channels = list(range(traces_per_ensemble))
        else:
            # Single channel seismic/sub-bottom
            self.channels = [0]
    
    def is_supported(self) -> bool:
        """Check if file is a valid SEG-Y format"""
        try:
            with open(self.file_path, 'rb') as f:
                # Check file size
                f.seek(0, 2)  # End of file
                file_size = f.tell()
                f.seek(0)
                
                if file_size < self.SEGY_HEADER_SIZE:
                    return False
                
                # Read beginning of file
                header_start = f.read(100)
                
                # Look for SEG-Y indicators in text header
                if b'SEG-Y' in header_start or b'SEGY' in header_start:
                    return True
                
                # Check binary header position for valid data
                f.seek(3200)  # Skip text header
                binary_sample = f.read(50)
                if len(binary_sample) >= 26:
                    # Check data format code
                    format_code = struct.unpack('>H', binary_sample[24:26])[0]
                    if 1 <= format_code <= 16:
                        return True
                
                # Check for typical seismic file patterns
                f.seek(0)
                sample_data = f.read(1000)
                
                # Look for EBCDIC patterns in text header
                ebcdic_chars = sum(1 for b in sample_data[:100] if 64 <= b <= 249)
                if ebcdic_chars > 50:  # Likely EBCDIC text header
                    return True
                
                return False
                
        except Exception:
            return False
    
    def get_channels(self) -> List[int]:
        """Get available channel IDs"""
        return self.channels
    
    def get_record_count(self) -> int:
        """Get total number of seismic traces"""
        if not self.is_supported() or not self.trace_info:
            return 0
            
        try:
            with open(self.file_path, 'rb') as f:
                # Calculate based on file size and trace structure
                f.seek(0, 2)
                file_size = f.tell()
                
                data_size = file_size - self.SEGY_HEADER_SIZE
                trace_size = self.trace_info.get('total_trace_size', 0)
                
                if trace_size > 0:
                    return data_size // trace_size
                else:
                    return 0
                    
        except Exception as e:
            logging.error(f"Failed to count SEG-Y traces: {e}")
            return 0
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get comprehensive file information"""
        base_info = super().get_file_info()
        
        if self.binary_header:
            base_info.update({
                'segy_revision': self.binary_header.get('segy_format_revision', 0),
                'data_format_code': self.binary_header.get('data_sample_format', 0),
                'data_format_name': self.DATA_FORMATS.get(
                    self.binary_header.get('data_sample_format', 0), ('Unknown', 0))[0],
                'samples_per_trace': self.binary_header.get('samples_per_trace', 0),
                'sample_interval_us': self.binary_header.get('sample_interval', 0),
                'traces_per_ensemble': self.binary_header.get('traces_per_ensemble', 0),
                'job_identification': self.binary_header.get('job_identification', 0),
                'line_number': self.binary_header.get('line_number', 0),
                'measurement_system': self.binary_header.get('measurement_system', 0)
            })
        
        if self.trace_info:
            base_info.update({
                'bytes_per_sample': self.trace_info.get('bytes_per_sample', 0),
                'trace_data_size': self.trace_info.get('trace_data_size', 0),
                'total_trace_size': self.trace_info.get('total_trace_size', 0)
            })
        
        return base_info
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse SEG-Y records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        if not self.is_supported():
            raise ValueError("Not a valid SEG-Y file")
        
        # Setup output paths
        base_name = Path(self.file_path).stem
        output_dir = Path(self.file_path).parent
        csv_path = output_dir / f"{base_name}_segy_records.csv"
        log_path = output_dir / f"{base_name}_segy_records.log"
        
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
                    # Skip SEG-Y headers
                    f.seek(self.SEGY_HEADER_SIZE)
                    
                    while max_records is None or record_count < max_records:
                        trace_start = f.tell()
                        
                        # Read trace header
                        trace_header_data = f.read(self.TRACE_HEADER_SIZE)
                        if len(trace_header_data) < self.TRACE_HEADER_SIZE:
                            break
                        
                        record = self._parse_trace(trace_header_data, f, trace_start)
                        
                        if record:
                            # Write to CSV
                            extras = {
                                'trace_sequence_line': record.trace_sequence_line,
                                'trace_sequence_file': record.trace_sequence_file,
                                'field_record_number': record.field_record_number,
                                'energy_source_point': record.energy_source_point,
                                'trace_identification_code': record.trace_identification_code,
                                'data_format_code': record.data_format_code,
                                'sample_interval': record.sample_interval,
                                'coordinate_scalar': record.coordinate_scalar,
                                'source_x': record.source_x,
                                'source_y': record.source_y,
                                'receiver_x': record.receiver_x,
                                'receiver_y': record.receiver_y,
                                'water_depth_shot': record.water_depth_shot,
                                'sweep_frequency_start': record.sweep_frequency_start,
                                'sweep_frequency_end': record.sweep_frequency_end
                            }
                            
                            csvfile.write(f"{record.ofs},{record.channel_id},{record.seq},{record.time_ms},"
                                        f"{record.lat},{record.lon},{record.depth_m},{record.sample_cnt},"
                                        f"{record.sonar_ofs},{record.sonar_size},{record.beam_deg},"
                                        f"{record.pitch_deg},{record.roll_deg},{record.heave_m},"
                                        f"{record.tx_ofs_m},{record.rx_ofs_m},{record.color_id},"
                                        f'"{json.dumps(extras, separators=(",", ":")).replace('"', '""')}"\n')
                            
                            record_count += 1
                            
                            if record_count % 50 == 0:
                                logging.info(f"Processed {record_count} SEG-Y traces")
        
        except Exception as e:
            logging.error(f"Error parsing SEG-Y records: {e}")
            raise
        
        logging.info(f"SEG-Y parsing completed: {record_count} records processed")
        return record_count, str(csv_path), str(log_path)
    
    def _parse_trace(self, header_data: bytes, f, trace_start: int) -> Optional[SEGYRecord]:
        """Parse individual SEG-Y trace"""
        try:
            # Parse trace header fields (240 bytes total)
            trace_seq_line = struct.unpack('>I', header_data[0:4])[0]
            trace_seq_file = struct.unpack('>I', header_data[4:8])[0]
            field_record_number = struct.unpack('>I', header_data[8:12])[0]
            trace_number = struct.unpack('>I', header_data[12:16])[0]
            energy_source_point = struct.unpack('>I', header_data[16:20])[0]
            ensemble_number = struct.unpack('>I', header_data[20:24])[0]
            trace_number_ensemble = struct.unpack('>I', header_data[24:28])[0]
            trace_identification_code = struct.unpack('>H', header_data[28:30])[0]
            
            # Geometry fields
            source_x = struct.unpack('>i', header_data[72:76])[0]  # Signed
            source_y = struct.unpack('>i', header_data[76:80])[0]  # Signed
            receiver_x = struct.unpack('>i', header_data[80:84])[0]  # Signed
            receiver_y = struct.unpack('>i', header_data[84:88])[0]  # Signed
            coordinate_units = struct.unpack('>H', header_data[88:90])[0]
            
            # Elevation and depth
            surface_elevation_shot = struct.unpack('>i', header_data[44:48])[0]
            water_depth_shot = struct.unpack('>i', header_data[60:64])[0]
            coordinate_scalar = struct.unpack('>h', header_data[70:72])[0]  # Signed
            
            # Time fields
            samples_this_trace = struct.unpack('>H', header_data[114:116])[0]
            sample_interval_this_trace = struct.unpack('>H', header_data[116:118])[0]
            
            # Use binary header defaults if trace header is zero
            if samples_this_trace == 0:
                samples_this_trace = self.binary_header.get('samples_per_trace', 0)
            if sample_interval_this_trace == 0:
                sample_interval_this_trace = self.binary_header.get('sample_interval', 0)
            
            # Sweep parameters (for chirp/parametric systems)
            sweep_freq_start = struct.unpack('>H', header_data[118:120])[0]
            sweep_freq_end = struct.unpack('>H', header_data[120:122])[0]
            sweep_length = struct.unpack('>H', header_data[122:124])[0]
            
            # Time information
            year = struct.unpack('>H', header_data[156:158])[0]
            day_of_year = struct.unpack('>H', header_data[158:160])[0]
            hour = struct.unpack('>H', header_data[160:162])[0]
            minute = struct.unpack('>H', header_data[162:164])[0]
            second = struct.unpack('>H', header_data[164:166])[0]
            
            # Calculate coordinates with scalar
            if coordinate_scalar != 0:
                if coordinate_scalar > 0:
                    coord_multiplier = coordinate_scalar
                else:
                    coord_multiplier = 1.0 / abs(coordinate_scalar)
                
                source_x *= coord_multiplier
                source_y *= coord_multiplier
                receiver_x *= coord_multiplier
                receiver_y *= coord_multiplier
            
            # Convert coordinates to lat/lon (simplified)
            # In production, would use proper coordinate transformation
            latitude = source_y / 1000000.0 if coordinate_units in [3, 4] else 0.0
            longitude = source_x / 1000000.0 if coordinate_units in [3, 4] else 0.0
            
            # Calculate depth from water depth
            depth_m = abs(water_depth_shot) / 1000.0 if water_depth_shot != 0 else 0.0
            
            # Calculate time in milliseconds
            time_ms = (hour * 3600 + minute * 60 + second) * 1000
            
            # Determine channel from trace ensemble position
            channel_id = trace_number_ensemble if trace_number_ensemble > 0 else 0
            
            # Calculate trace data size and skip it
            format_code = self.binary_header.get('data_sample_format', 1)
            bytes_per_sample = self.DATA_FORMATS.get(format_code, ('Unknown', 4))[1]
            trace_data_size = samples_this_trace * bytes_per_sample
            
            # Skip trace data (could read and process if needed)
            f.seek(f.tell() + trace_data_size)
            
            # Create SEG-Y record
            record = SEGYRecord(
                ofs=trace_start,
                channel_id=channel_id,
                seq=trace_seq_line,
                time_ms=time_ms,
                lat=latitude,
                lon=longitude,
                depth_m=depth_m,
                sample_cnt=samples_this_trace,
                sonar_ofs=trace_start + self.TRACE_HEADER_SIZE,
                sonar_size=trace_data_size,
                beam_deg=0.0,  # Not applicable to seismic
                pitch_deg=0.0,
                roll_deg=0.0,
                heave_m=0.0,
                trace_sequence_line=trace_seq_line,
                trace_sequence_file=trace_seq_file,
                field_record_number=field_record_number,
                trace_number=trace_number,
                energy_source_point=energy_source_point,
                ensemble_number=ensemble_number,
                trace_number_ensemble=trace_number_ensemble,
                trace_identification_code=trace_identification_code,
                coordinate_scalar=coordinate_scalar,
                coordinate_units=coordinate_units,
                source_x=int(source_x),
                source_y=int(source_y),
                receiver_x=int(receiver_x),
                receiver_y=int(receiver_y),
                water_depth_shot=water_depth_shot,
                samples_per_trace=samples_this_trace,
                sample_interval=sample_interval_this_trace,
                sweep_frequency_start=sweep_freq_start,
                sweep_frequency_end=sweep_freq_end,
                sweep_length=sweep_length,
                year=year,
                day_of_year=day_of_year,
                hour=hour,
                minute=minute,
                second=second,
                data_format_code=format_code
            )
            
            return record
            
        except Exception as e:
            logging.error(f"Error parsing SEG-Y trace at offset {trace_start}: {e}")
            return None

# Test function
def test_segy_parser():
    """Test SEG-Y parser (create sample SEG-Y file for testing)"""
    test_dir = Path(r"c:\Temp\Garmin_RSD_releases\testing new design")
    test_patterns = [
        "*.segy", "*.sgy", "*.SGY", "*.SEGY"
    ]
    
    print("Testing SEG-Y Parser Implementation")
    print("=" * 40)
    
    # Look for existing SEG-Y files
    found_files = []
    for pattern in test_patterns:
        found_files.extend(test_dir.glob(pattern))
    
    if found_files:
        # Test with real file
        test_file = found_files[0]
        print(f"Testing with existing file: {test_file}")
    else:
        # Create a minimal SEG-Y file for testing
        test_file = test_dir / "sample_seismic.segy"
        
        try:
            with open(test_file, 'wb') as f:
                # Create minimal SEG-Y file
                
                # Text header (3200 bytes) - simplified EBCDIC
                text_header = b'C01 SEG-Y FORMAT TEST FILE - MARINE SEISMIC SURVEY' + b' ' * 3150
                f.write(text_header)
                
                # Binary header (400 bytes)
                binary_header = bytearray(400)
                struct.pack_into('>H', binary_header, 16, 1000)   # Sample interval (1ms)
                struct.pack_into('>H', binary_header, 20, 1000)   # Samples per trace
                struct.pack_into('>H', binary_header, 24, 5)      # IEEE float format
                struct.pack_into('>H', binary_header, 300, 2)     # SEG-Y revision 2
                f.write(binary_header)
                
                # Create 5 sample traces
                for trace_num in range(5):
                    # Trace header (240 bytes)
                    trace_header = bytearray(240)
                    struct.pack_into('>I', trace_header, 0, trace_num + 1)    # Trace seq line
                    struct.pack_into('>I', trace_header, 4, trace_num + 1)    # Trace seq file
                    struct.pack_into('>I', trace_header, 16, 1001)            # Energy source
                    struct.pack_into('>H', trace_header, 28, 1)               # Seismic data
                    struct.pack_into('>i', trace_header, 72, -71000000)       # Source X (lon)
                    struct.pack_into('>i', trace_header, 76, 42000000)        # Source Y (lat)
                    struct.pack_into('>h', trace_header, 70, -10000)          # Coord scalar
                    struct.pack_into('>H', trace_header, 88, 4)               # Decimal degrees
                    struct.pack_into('>H', trace_header, 114, 1000)           # Samples this trace
                    struct.pack_into('>H', trace_header, 116, 1000)           # Sample interval
                    struct.pack_into('>H', trace_header, 156, 2025)           # Year
                    struct.pack_into('>H', trace_header, 158, 286)            # Day of year
                    struct.pack_into('>H', trace_header, 160, 14)             # Hour
                    struct.pack_into('>H', trace_header, 162, 30)             # Minute
                    f.write(trace_header)
                    
                    # Trace data (1000 samples * 4 bytes = 4000 bytes)
                    trace_data = bytearray(4000)
                    # Simple synthetic seismic trace
                    for i in range(1000):
                        amplitude = math.sin(i * 0.02) * math.exp(-i * 0.001)
                        struct.pack_into('>f', trace_data, i * 4, amplitude)
                    f.write(trace_data)
            
            print(f"Created sample SEG-Y file: {test_file}")
            
        except Exception as e:
            print(f"Failed to create test file: {e}")
            return
    
    try:
        # Test the parser
        parser = SEGYParser(str(test_file))
        
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
        
        # Clean up test file if we created it
        if not found_files:
            test_file.unlink()
        
    except Exception as e:
        print(f"Error testing SEG-Y parser: {e}")

if __name__ == "__main__":
    test_segy_parser()