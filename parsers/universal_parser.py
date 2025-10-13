#!/usr/bin/env python3
"""
Universal Sonar Format Detection and Parsing
Based on PINGVerter research and format specifications
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from abc import ABC, abstractmethod
import struct

def detect_sonar_format(file_path: str) -> Optional[str]:
    """
    Auto-detect sonar file format based on extension and file signature
    
    Returns:
        Format identifier string or None if unknown
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    
    # Extension-based detection
    format_map = {
        '.rsd': 'garmin',
        '.sl2': 'lowrance_sl2',
        '.sl3': 'lowrance_sl3', 
        '.dat': 'humminbird',
        '.son': 'humminbird_sonar',
        '.idx': 'humminbird_index',
        '.jsf': 'edgetech',
        '.svlog': 'cerulean',
        '.xtf': 'xtf_generic'
    }
    
    if extension in format_map:
        detected = format_map[extension]
        
        # Verify with file signature if possible
        if os.path.exists(file_path) and os.path.getsize(file_path) > 16:
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(16)
                    
                if _verify_format_signature(header, detected):
                    return detected
                else:
                    print(f"Warning: Extension suggests {detected} but signature doesn't match")
                    return detected  # Trust extension for now
                    
            except Exception as e:
                print(f"Could not read file signature: {e}")
                return detected
        
        return detected
    
    return None

def _verify_format_signature(header: bytes, format_type: str) -> bool:
    """
    Verify file format using binary signatures
    """
    if format_type == 'garmin':
        # RSD files often start with specific patterns
        # This is a simplified check - real RSD has complex headers
        return len(header) >= 4
        
    elif format_type.startswith('lowrance'):
        # Lowrance SL files have specific headers
        # Look for Lowrance/Navico signatures
        navico_signatures = [b'SLGF', b'SL02', b'SL03']
        return any(sig in header for sig in navico_signatures)
        
    elif format_type == 'humminbird':
        # Humminbird .DAT files have specific patterns
        # Often contain manufacturer IDs
        return b'HUM' in header or b'JRC' in header
        
    elif format_type == 'edgetech':
        # JSF format has specific headers
        return b'JSF' in header or header[:4] == b'\x16\x81\x00\x00'
        
    elif format_type == 'cerulean':
        # Cerulean .svlog format patterns
        return b'CERU' in header or b'SVL' in header
    
    return True  # Default to allow unknown signatures

class BaseSonarParser(ABC):
    """
    Abstract base class for all sonar format parsers
    """
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.format_type = detect_sonar_format(str(file_path))
        self._channels = None
        self._total_records = None
        
    @abstractmethod
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Parse sonar records and export to CSV
        
        Returns:
            (record_count, csv_path, log_path)
        """
        pass
    
    @abstractmethod
    def get_channels(self) -> List[int]:
        """
        Get available channel IDs in this file
        """
        pass
    
    @abstractmethod
    def get_record_count(self) -> int:
        """
        Get total number of records in file
        """
        pass
    
    def get_file_info(self) -> Dict:
        """
        Get basic file information
        """
        stat = self.file_path.stat()
        return {
            'path': str(self.file_path),
            'size_mb': stat.st_size / (1024 * 1024),
            'format': self.format_type,
            'channels': self.get_channels(),
            'total_records': self.get_record_count()
        }

class UniversalSonarParser:
    """
    Universal parser that automatically detects format and delegates to appropriate parser
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.format_type = detect_sonar_format(file_path)
        self.parser = self._create_parser()
        
    def _create_parser(self) -> BaseSonarParser:
        """
        Create appropriate parser based on detected format
        """
        if self.format_type == 'garmin':
            from .garmin_parser import GarminParser
            return GarminParser(self.file_path)
            
        elif self.format_type.startswith('lowrance'):
            from .lowrance_parser import LowranceParser
            return LowranceParser(self.file_path)
            
        elif self.format_type == 'humminbird':
            from .humminbird_parser import HumminbirdParser
            return HumminbirdParser(self.file_path)
            
        elif self.format_type == 'edgetech':
            from .edgetech_parser import EdgeTechParser
            return EdgeTechParser(self.file_path)
            
        elif self.format_type == 'cerulean':
            from .cerulean_parser import CeruleanParser 
            return CeruleanParser(self.file_path)
            
        else:
            raise ValueError(f"Unsupported format: {self.format_type}")
    
    def parse_records(self, max_records: Optional[int] = None) -> Tuple[int, str, str]:
        """
        Universal parsing interface
        """
        return self.parser.parse_records(max_records)
    
    def get_channels(self) -> List[int]:
        """
        Get available channels for any format
        """
        return self.parser.get_channels()
    
    def get_file_info(self) -> Dict:
        """
        Get comprehensive file information
        """
        return self.parser.get_file_info()
    
    def is_supported(self) -> bool:
        """
        Check if file format is supported
        """
        return self.format_type is not None

# Convenience functions for backward compatibility
def auto_parse_sonar(file_path: str, output_dir: str, max_records: Optional[int] = None):
    """
    Auto-detect and parse any supported sonar format
    """
    parser = UniversalSonarParser(file_path)
    
    if not parser.is_supported():
        raise ValueError(f"Unsupported file format: {file_path}")
    
    print(f"Detected format: {parser.format_type}")
    print(f"Available channels: {parser.get_channels()}")
    
    return parser.parse_records(max_records)

def get_supported_formats() -> Dict[str, List[str]]:
    """
    Get all supported formats and their extensions
    """
    return {
        'Garmin': ['.rsd'],
        'Lowrance': ['.sl2', '.sl3'],
        'Humminbird': ['.dat', '.son', '.idx'], 
        'EdgeTech': ['.jsf'],
        'Cerulean': ['.svlog'],
        'Generic': ['.xtf']
    }

def format_file_filter() -> str:
    """
    Generate file filter string for GUI dialogs
    """
    filters = []
    
    # All sonar files
    all_extensions = []
    for extensions in get_supported_formats().values():
        all_extensions.extend(extensions)
    
    all_pattern = ';'.join(f'*{ext}' for ext in all_extensions)
    filters.append(f"All Sonar Files ({all_pattern})")
    
    # Individual formats
    for format_name, extensions in get_supported_formats().items():
        pattern = ';'.join(f'*{ext}' for ext in extensions)
        filters.append(f"{format_name} ({pattern})")
    
    return '|'.join(filters)

if __name__ == "__main__":
    # Test detection
    test_files = [
        "test.rsd",
        "test.sl2", 
        "test.dat",
        "test.jsf",
        "unknown.xyz"
    ]
    
    for file_path in test_files:
        format_type = detect_sonar_format(file_path)
        print(f"{file_path} -> {format_type}")
    
    print("\nSupported formats:")
    for format_name, extensions in get_supported_formats().items():
        print(f"  {format_name}: {', '.join(extensions)}")
    
    print(f"\nFile filter: {format_file_filter()}")