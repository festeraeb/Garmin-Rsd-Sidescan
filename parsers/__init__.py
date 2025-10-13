#!/usr/bin/env python3
"""
Multi-Format Sonar Parser Package
Universal support for Garmin, Lowrance, Humminbird, EdgeTech, and Cerulean formats
"""

from .universal_parser import (
    UniversalSonarParser, 
    detect_sonar_format,
    auto_parse_sonar,
    get_supported_formats,
    format_file_filter
)

from .garmin_parser import GarminParser, parse_garmin_rsd, get_garmin_channels
from .lowrance_parser import LowranceParser, HumminbirdParser, EdgeTechParser, CeruleanParser

__version__ = "1.0.0"
__author__ = "RSD Studio Development Team"

# Supported format registry
SUPPORTED_FORMATS = {
    'garmin': {
        'name': 'Garmin RSD',
        'extensions': ['.rsd'],
        'parser': GarminParser,
        'status': 'Production',
        'features': ['sidescan', 'downscan', 'gps', 'depth', 'multifreq']
    },
    'lowrance_sl2': {
        'name': 'Lowrance SL2',
        'extensions': ['.sl2'],
        'parser': LowranceParser,
        'status': 'Framework',
        'features': ['sidescan', 'gps', 'depth']
    },
    'lowrance_sl3': {
        'name': 'Lowrance SL3', 
        'extensions': ['.sl3'],
        'parser': LowranceParser,
        'status': 'Framework',
        'features': ['sidescan', 'gps', 'depth', 'multifreq']
    },
    'humminbird': {
        'name': 'Humminbird DAT/SON',
        'extensions': ['.dat', '.son', '.idx'],
        'parser': HumminbirdParser,
        'status': 'Planned',
        'features': ['sidescan', 'downscan', 'gps', 'depth']
    },
    'edgetech': {
        'name': 'EdgeTech JSF',
        'extensions': ['.jsf'],
        'parser': EdgeTechParser,
        'status': 'Planned', 
        'features': ['sidescan', 'gps', 'multifreq']
    },
    'cerulean': {
        'name': 'Cerulean SVLOG',
        'extensions': ['.svlog'],
        'parser': CeruleanParser,
        'status': 'Planned',
        'features': ['sidescan', 'gps']
    }
}

def get_format_status_report():
    """Get comprehensive status of all supported formats"""
    
    print("🎯 RSD Studio Multi-Format Support Status")
    print("=" * 50)
    
    for format_id, info in SUPPORTED_FORMATS.items():
        status_icon = {
            'Production': '✅',
            'Framework': '🔄', 
            'Planned': '⏳'
        }.get(info['status'], '❓')
        
        features_str = ', '.join(info['features'])
        extensions_str = ', '.join(info['extensions'])
        
        print(f"{status_icon} {info['name']}")
        print(f"   Extensions: {extensions_str}")
        print(f"   Status: {info['status']}")
        print(f"   Features: {features_str}")
        print()
    
    print("Status Legend:")
    print("✅ Production - Fully functional")
    print("🔄 Framework - Basic structure, needs implementation")
    print("⏳ Planned - Future development")

def create_parser(file_path: str):
    """
    Convenience function to create appropriate parser
    """
    return UniversalSonarParser(file_path)

# Backward compatibility aliases
parse_sonar = auto_parse_sonar
detect_format = detect_sonar_format

__all__ = [
    'UniversalSonarParser',
    'GarminParser', 
    'LowranceParser',
    'HumminbirdParser',
    'EdgeTechParser', 
    'CeruleanParser',
    'detect_sonar_format',
    'auto_parse_sonar',
    'get_supported_formats',
    'format_file_filter',
    'get_format_status_report',
    'create_parser',
    'SUPPORTED_FORMATS'
]