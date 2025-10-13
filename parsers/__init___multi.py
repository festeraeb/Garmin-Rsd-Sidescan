#!/usr/bin/env python3
"""
RSD Studio Multi-Format Sonar Parser Package
Comprehensive sonar format support based on PINGVerter research
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Any

# Import all parser implementations
try:
    from .universal_parser import UniversalSonarParser
except ImportError:
    from .universal_parser import UniversalSonarParser

try:
    from .garmin_parser import GarminParser
except ImportError:
    print("Warning: GarminParser not available")
    GarminParser = None

try:
    from .lowrance_parser_enhanced import LowranceParser
except ImportError:
    print("Warning: LowranceParser not available")
    LowranceParser = None

try:
    from .humminbird_parser import HumminbirdParser
except ImportError:
    print("Warning: HumminbirdParser not available") 
    HumminbirdParser = None

try:
    from .edgetech_parser import EdgeTechParser
except ImportError:
    print("Warning: EdgeTechParser not available")
    EdgeTechParser = None

try:
    from .cerulean_parser import CeruleanParser
except ImportError:
    print("Warning: CeruleanParser not available")
    CeruleanParser = None

# Format detection mappings
FORMAT_EXTENSIONS = {
    'garmin': ['.rsd', '.RSD'],
    'lowrance': ['.sl2', '.sl3', '.SL2', '.SL3'], 
    'humminbird': ['.dat', '.son', '.DAT', '.SON', '.idx', '.IDX'],
    'edgetech': ['.jsf', '.JSF'],
    'cerulean': ['.svlog', '.SVLOG']
}

FORMAT_PARSERS = {}
if GarminParser:
    FORMAT_PARSERS['garmin'] = GarminParser
if LowranceParser:
    FORMAT_PARSERS['lowrance'] = LowranceParser
if HumminbirdParser:
    FORMAT_PARSERS['humminbird'] = HumminbirdParser
if EdgeTechParser:
    FORMAT_PARSERS['edgetech'] = EdgeTechParser
if CeruleanParser:
    FORMAT_PARSERS['cerulean'] = CeruleanParser

def detect_sonar_format(file_path: str) -> Optional[str]:
    """
    Detect sonar file format based on extension and magic bytes
    
    Args:
        file_path: Path to sonar file
        
    Returns:
        Format identifier or None if unsupported
    """
    if not os.path.exists(file_path):
        return None
        
    file_path_obj = Path(file_path)
    extension = file_path_obj.suffix
    
    # Check by extension first
    for format_name, extensions in FORMAT_EXTENSIONS.items():
        if extension in extensions:
            # Verify with magic bytes if possible
            if format_name in FORMAT_PARSERS:
                parser_class = FORMAT_PARSERS[format_name]
                try:
                    parser = parser_class(file_path)
                    if parser.is_supported():
                        return format_name
                except:
                    pass
    
    return None

def get_supported_formats() -> Dict[str, List[str]]:
    """
    Get all supported sonar formats and their extensions
    
    Returns:
        Dictionary mapping manufacturer to file extensions
    """
    return {
        'Garmin': FORMAT_EXTENSIONS['garmin'],
        'Lowrance': FORMAT_EXTENSIONS['lowrance'],
        'Humminbird': FORMAT_EXTENSIONS['humminbird'],
        'EdgeTech': FORMAT_EXTENSIONS['edgetech'],
        'Cerulean': FORMAT_EXTENSIONS['cerulean']
    }

def create_parser(file_path: str) -> Optional[object]:
    """
    Create appropriate parser for sonar file
    
    Args:
        file_path: Path to sonar file
        
    Returns:
        Parser instance or None if unsupported
    """
    format_type = detect_sonar_format(file_path)
    if not format_type or format_type not in FORMAT_PARSERS:
        return None
        
    parser_class = FORMAT_PARSERS[format_type]
    return parser_class(file_path)

def get_format_status_report():
    """Print detailed status of all supported formats"""
    print("\n🌐 Multi-Format Sonar Support Status")
    print("=" * 40)
    
    total_formats = len(FORMAT_EXTENSIONS)
    implemented = len(FORMAT_PARSERS)
    
    for format_name, extensions in FORMAT_EXTENSIONS.items():
        extensions_str = ', '.join(extensions)
        
        # Test basic instantiation
        if format_name in FORMAT_PARSERS:
            try:
                parser_class = FORMAT_PARSERS[format_name]
                # Create dummy parser to test implementation
                test_path = f"dummy.{extensions[0][1:]}"
                parser = parser_class(test_path)
                status = "✅ Implemented"
            except Exception as e:
                status = f"⚠️ Partial: {str(e)[:20]}..."
        else:
            status = "❌ Missing"
        
        print(f"  {format_name.title():<12}: {extensions_str:<25} {status}")
    
    print(f"\nImplementation Status: {implemented}/{total_formats} formats ready")
    
    # Feature matrix
    print(f"\n📊 Feature Matrix:")
    print("  Format      | Parse | Enhanced | Magic Bytes | Channels")
    print("  ------------|-------|----------|-------------|----------")
    
    for format_name in FORMAT_EXTENSIONS:
        parser_name = format_name.title()
        parse_support = "✅" if format_name in FORMAT_PARSERS else "❌"
        enhanced_support = "✅" if format_name in ['garmin'] else "🔄"
        magic_support = "✅" if format_name in FORMAT_PARSERS else "❌"
        channel_support = "✅" if format_name in FORMAT_PARSERS else "❌"
        
        print(f"  {parser_name:<11} |   {parse_support}   |    {enhanced_support}    |      {magic_support}      |    {channel_support}")

def format_file_filter() -> str:
    """
    Generate file dialog filter string for all supported formats
    
    Returns:
        File filter string for GUI dialogs
    """
    # All sonar files filter
    all_extensions = []
    for extensions in FORMAT_EXTENSIONS.values():
        all_extensions.extend(extensions)
    
    all_filter = f"All Sonar Files|{'|'.join(['*' + ext for ext in all_extensions])}"
    
    # Individual format filters
    format_filters = []
    for format_name, extensions in FORMAT_EXTENSIONS.items():
        manufacturer = format_name.title()
        ext_pattern = '|'.join(['*' + ext for ext in extensions])
        format_filters.append(f"{manufacturer} Files|{ext_pattern}")
    
    # Combine all filters
    return f"{all_filter}|{'|'.join(format_filters)}|All Files|*.*"

# Export main interface functions
__all__ = [
    'UniversalSonarParser',
    'GarminParser', 
    'LowranceParser',
    'HumminbirdParser',
    'EdgeTechParser',
    'CeruleanParser',
    'detect_sonar_format',
    'get_supported_formats',
    'create_parser',
    'get_format_status_report',
    'format_file_filter'
]