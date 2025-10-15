#!/usr/bin/env python3
"""
Enhanced Garmin RSD Parser with depth field improvements
Integrates with existing RSD Studio engine
"""

import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from .base_parser import BaseSonarParser

class GarminParser(BaseSonarParser):
    """
    Enhanced Garmin RSD parser with improved depth handling
    """
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self.format_type = "garmin_rsd"
        self._cached_channels = None
        self._cached_record_count = None
        
    def parse_records(self, max_records: Optional[int] = None, progress_callback=None) -> Tuple[int, str, str]:
        """
        Parse Garmin RSD records using enhanced engine
        
        Args:
            max_records: Maximum number of records to parse (None for all)
            progress_callback: Optional callback function for progress updates (pct, message)
        """
        # Use our existing engine with improvements
        from engine_nextgen_syncfirst import parse_rsd_records_nextgen
        from pathlib import Path
        import csv
        import os
        
        file_path_obj = Path(self.file_path)
        output_dir = file_path_obj.parent / "parsed_output"
        output_dir.mkdir(exist_ok=True)
        
        csv_name = f"{file_path_obj.stem}_parsed.csv"
        csv_path = str(output_dir / csv_name)
        log_path = str(output_dir / f"{file_path_obj.stem}_parsed.log")
        
        # CSV header - must match what GUI expects
        header = [
            "ofs", "channel_id", "seq", "time_ms", "lat", "lon", "depth_m", 
            "sample_cnt", "sonar_ofs", "sonar_size", "beam_deg", "pitch_deg", 
            "roll_deg", "heave_m", "tx_ofs_m", "rx_ofs_m", "color_id", "extras_json"
        ]
        
        record_count = 0
        
        # Parse records and write to CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            try:
                for record in parse_rsd_records_nextgen(str(self.file_path), limit_records=max_records, progress=progress_callback):
                    writer.writerow([
                        record.ofs,
                        record.channel_id,
                        record.seq,
                        record.time_ms,
                        record.lat,
                        record.lon,
                        record.depth_m,
                        record.sample_cnt,
                        record.sonar_ofs,
                        record.sonar_size,
                        record.beam_deg,
                        record.pitch_deg,
                        record.roll_deg,
                        record.heave_m,
                        record.tx_ofs_m,
                        record.rx_ofs_m,
                        record.color_id,
                        "{}"  # Empty JSON for extras
                    ])
                    record_count += 1
                    
            except Exception as e:
                # Write error to log
                with open(log_path, 'w') as log_file:
                    log_file.write(f"Parse error: {str(e)}\n")
                raise
        
        return record_count, csv_path, log_path
    
    def get_channels(self) -> List[int]:
        """
        Get available channels in Garmin RSD file
        """
        if self._cached_channels is not None:
            return self._cached_channels
            
        try:
            # Quick parse to get channel info
            from engine_nextgen_syncfirst import parse_rsd_records_nextgen
            
            channels = set()
            record_count = 0
            
            # Sample first 1000 records to get channel list
            for record in parse_rsd_records_nextgen(str(self.file_path), limit_records=1000):
                channels.add(record.channel_id)
                record_count += 1
                
                if record_count >= 1000:  # Limit for channel detection
                    break
            
            self._cached_channels = sorted(list(channels))
            return self._cached_channels
            
        except Exception as e:
            print(f"Warning: Could not determine channels: {e}")
            return [0, 4, 5]  # Default Garmin channels
    
    def get_record_count(self) -> int:
        """
        Get total number of records in Garmin RSD file
        """
        if self._cached_record_count is not None:
            return self._cached_record_count
            
        try:
            # Fast record counting without full parse
            from engine_nextgen_syncfirst import count_rsd_records
            
            # If count function doesn't exist, estimate from file size
            try:
                self._cached_record_count = count_rsd_records(str(self.file_path))
            except AttributeError:
                # Fallback: estimate from file size (rough approximation)
                file_size = self.file_path.stat().st_size
                avg_record_size = 4100  # Typical RSD record size in bytes
                self._cached_record_count = file_size // avg_record_size
                
            return self._cached_record_count
            
        except Exception as e:
            print(f"Warning: Could not count records: {e}")
            return 0
    
    def analyze_depth_fields(self, sample_size: int = 1000) -> Dict:
        """
        Analyze depth-related fields to understand encoding
        """
        try:
            from engine_nextgen_syncfirst import parse_rsd_records_nextgen
            
            depth_analysis = {
                'depth_values': [],
                'extras_with_depth': [],
                'potential_depth_fields': [],
                'coordinate_info': []
            }
            
            record_count = 0
            for record in parse_rsd_records_nextgen(str(self.file_path), limit_records=sample_size):
                # Collect depth values
                depth_analysis['depth_values'].append(record.depth_m)
                
                # Analyze extras for potential depth fields
                if hasattr(record, 'extras') and record.extras:
                    if isinstance(record.extras, dict):
                        for key, value in record.extras.items():
                            if isinstance(value, (int, float)):
                                # Look for values in reasonable depth range (1-100 meters)
                                if 1.0 <= value <= 100.0:
                                    depth_analysis['potential_depth_fields'].append({
                                        'field': key,
                                        'value': value,
                                        'record': record_count
                                    })
                                    
                                # Look for depth-related keywords
                                if any(keyword in key.lower() for keyword in ['depth', 'water', 'bottom', 'range']):
                                    depth_analysis['extras_with_depth'].append({
                                        'field': key, 
                                        'value': value,
                                        'record': record_count
                                    })
                
                # Collect coordinate info
                if record.lat != 0.0 and record.lon != 0.0:
                    depth_analysis['coordinate_info'].append({
                        'lat': record.lat,
                        'lon': record.lon,
                        'depth': record.depth_m,
                        'record': record_count
                    })
                
                record_count += 1
                
                if record_count >= sample_size:
                    break
            
            # Calculate statistics
            depths = depth_analysis['depth_values']
            depth_analysis['stats'] = {
                'count': len(depths),
                'min': min(depths) if depths else 0,
                'max': max(depths) if depths else 0,
                'avg': sum(depths) / len(depths) if depths else 0,
                'non_zero_count': sum(1 for d in depths if d != 0.0)
            }
            
            return depth_analysis
            
        except Exception as e:
            print(f"Warning: Depth analysis failed: {e}")
            return {}
    
    def get_enhanced_file_info(self) -> Dict:
        """
        Get comprehensive Garmin RSD file information including depth analysis
        """
        base_info = self.get_file_info()
        
        # Add Garmin-specific analysis
        try:
            depth_info = self.analyze_depth_fields(500)  # Smaller sample for speed
            base_info['depth_analysis'] = depth_info
            
            # Add format-specific details
            base_info['format_details'] = {
                'manufacturer': 'Garmin',
                'format_name': 'RSD (Garmin Sonar Data)',
                'typical_channels': {
                    0: 'Metadata/Header',
                    1: 'Traditional Sonar',
                    2: 'CHIRP Sonar',
                    4: 'Left Sidescan',
                    5: 'Right Sidescan'
                },
                'supports_gps': True,
                'supports_depth': True,
                'supports_multifreq': True
            }
            
        except Exception as e:
            print(f"Warning: Could not get enhanced info: {e}")
            
        return base_info
    
    def is_supported(self) -> bool:
        """
        Check if file is a supported Garmin RSD file
        """
        try:
            # For RSD files, if the filename ends with .RSD, assume it's supported
            # Real-world RSD files don't always have magic bytes at the start
            if self.file_path.lower().endswith('.rsd'):
                return True
                
            # Also check for some basic binary patterns that suggest sonar data
            with open(self.file_path, 'rb') as f:
                header = f.read(512)  # Read more data
                if len(header) < 16:
                    return False
                
                # Look for binary patterns that suggest sonar data
                # Check for structured binary data (non-ASCII patterns)
                binary_bytes = sum(1 for b in header[:100] if b < 32 or b > 126)
                if binary_bytes > 50:  # Likely binary format
                    return True
                    
                return False
                
        except Exception as e:
            print(f"Error checking Garmin RSD support: {e}")
            return False

# Backward compatibility functions
def parse_garmin_rsd(file_path: str, output_dir: str, max_records: Optional[int] = None):
    """
    Parse Garmin RSD file (backward compatibility)
    """
    parser = GarminParser(file_path)
    return parser.parse_records(max_records)

def get_garmin_channels(file_path: str) -> List[int]:
    """
    Get Garmin RSD channels (backward compatibility)
    """
    parser = GarminParser(file_path)
    return parser.get_channels()

if __name__ == "__main__":
    # Test with sample file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        parser = GarminParser(file_path)
        
        print("=== Garmin RSD Analysis ===")
        info = parser.get_enhanced_file_info()
        
        print(f"File: {info['path']}")
        print(f"Size: {info['size_mb']:.1f} MB")
        print(f"Channels: {info['channels']}")
        print(f"Records: {info['total_records']}")
        
        if 'depth_analysis' in info:
            depth = info['depth_analysis']['stats']
            print(f"\nDepth Analysis:")
            print(f"  Depth range: {depth['min']:.3f} - {depth['max']:.3f}m")
            print(f"  Average: {depth['avg']:.3f}m")
            print(f"  Non-zero readings: {depth['non_zero_count']}/{depth['count']}")
        
        # Test parsing small sample
        try:
            count, csv_path, log_path = parser.parse_records(100)
            print(f"\nTest parse: {count} records -> {csv_path}")
        except Exception as e:
            print(f"\nParse test failed: {e}")
    else:
        print("Usage: python garmin_parser.py <rsd_file>")