#!/usr/bin/env python3
"""
Base Parser Classes for Multi-Format Sonar Support
Provides common interface and functionality for all sonar parsers
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
import json

@dataclass
class SonarRecord:
    """Base sonar record structure - common fields across all formats"""
    ofs: int = 0                    # File offset
    channel_id: int = 0             # Channel/beam identifier  
    seq: int = 0                    # Sequence/ping number
    time_ms: int = 0                # Timestamp in milliseconds
    lat: float = 0.0                # Latitude in decimal degrees
    lon: float = 0.0                # Longitude in decimal degrees
    depth_m: float = 0.0            # Depth/distance in meters
    sample_cnt: int = 0             # Number of sonar samples
    sonar_ofs: int = 0              # Offset to sonar data
    sonar_size: int = 0             # Size of sonar data in bytes
    beam_deg: float = 0.0           # Beam angle in degrees
    pitch_deg: float = 0.0          # Platform pitch in degrees
    roll_deg: float = 0.0           # Platform roll in degrees
    heave_m: float = 0.0            # Heave displacement in meters
    tx_ofs_m: float = 0.0           # Transmitter offset in meters
    rx_ofs_m: float = 0.0           # Receiver offset in meters
    color_id: int = 0               # Color/intensity ID

class BaseSonarParser:
    """
    Base class for all sonar format parsers
    Provides common interface and utility methods
    """
    
    def __init__(self, file_path: str):
        """
        Initialize parser with file path
        
        Args:
            file_path: Path to sonar file
        """
        self.file_path = file_path
        self.format_type = "unknown"
        self.channels = []
        
    def get_file_info(self) -> Dict[str, Any]:
        """
        Get basic file information
        
        Returns:
            Dictionary with file metadata
        """
        path = Path(self.file_path)
        
        try:
            file_size = os.path.getsize(self.file_path)
            size_mb = file_size / (1024 * 1024)
        except OSError:
            file_size = 0
            size_mb = 0.0
        
        return {
            'path': str(path),
            'name': path.name,
            'size_bytes': file_size,
            'size_mb': size_mb,
            'format_type': self.format_type,
            'channels': self.channels,
            'exists': path.exists()
        }
    
    def parse_records(self, max_records: Optional[int] = None, progress_callback=None) -> Tuple[int, str, str]:
        """
        Parse sonar records and export to CSV
        
        Args:
            max_records: Maximum number of records to parse (None for all)
            progress_callback: Optional callback function for progress updates (pct, message)
            
        Returns:
            Tuple of (record_count, csv_path, log_path)
        """
        raise NotImplementedError("Subclasses must implement parse_records")
    
    def is_supported(self) -> bool:
        """
        Check if the file format is supported by this parser
        
        Returns:
            True if supported, False otherwise
        """
        return os.path.exists(self.file_path)
    
    def get_enhanced_file_info(self) -> Dict[str, Any]:
        """
        Get enhanced file information with format-specific details
        
        Returns:
            Enhanced metadata dictionary
        """
        # Default implementation returns basic info
        return self.get_file_info()
    
    def _format_extras_json(self, extras: Dict) -> str:
        """
        Format extras dictionary as JSON string for CSV export
        
        Args:
            extras: Dictionary of extra fields
            
        Returns:
            JSON string representation
        """
        try:
            # Clean up any non-serializable values
            clean_extras = {}
            for key, value in extras.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    clean_extras[key] = value
                else:
                    clean_extras[key] = str(value)
            
            return json.dumps(clean_extras, separators=(',', ':'))
        except Exception:
            return "{}"
    
    def count_records(self) -> int:
        """
        Count total records in file (may be approximate)
        
        Returns:
            Estimated record count
        """
        # Default implementation - subclasses should override
        return 0
    
    def get_sample_records(self, count: int = 10) -> List[SonarRecord]:
        """
        Get sample records for analysis
        
        Args:
            count: Number of sample records to retrieve
            
        Returns:
            List of sample sonar records
        """
        # Default implementation - subclasses should override
        return []
    
    def validate_format(self) -> Dict[str, Any]:
        """
        Validate file format and structure
        
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'file_size': 0,
            'magic_bytes_valid': False
        }
        
        try:
            if not os.path.exists(self.file_path):
                results['errors'].append("File does not exist")
                return results
                
            file_size = os.path.getsize(self.file_path)
            results['file_size'] = file_size
            
            if file_size == 0:
                results['errors'].append("File is empty")
                return results
                
            if file_size < 1024:
                results['warnings'].append("File is very small (< 1KB)")
            
            # Basic validation passed
            results['valid'] = True
            
        except Exception as e:
            results['errors'].append(f"Validation error: {e}")
        
        return results