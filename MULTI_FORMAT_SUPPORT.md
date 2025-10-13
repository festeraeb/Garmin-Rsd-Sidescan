# Multi-Format Sonar Support for RSD Studio

Based on research of PINGVerter and PINGMapper, this document outlines expanding RSD Studio to support all major commercial sonar formats.

## Supported Formats Analysis

### Current RSD Studio Support
- ✅ **Garmin RSD** (.rsd) - Full support with dual sidescan channels

### Target Commercial Formats (from PINGVerter)
- 🎯 **Humminbird** (.DAT/.SON/.IDX) - Johnson Outdoors
- 🎯 **Lowrance** (.sl2/.sl3) - Navico family (Lowrance, Simrad, B&G) 
- 🎯 **EdgeTech** (.jsf) - Professional sidescan systems
- 🎯 **Cerulean** (.svlog) - Omniscan 450 SS
- 🎯 **Generic** - Support for research/custom formats

## File Format Specifications

### Humminbird (.DAT/.SON/.IDX)
- **Primary**: .DAT (main data file)
- **Sonar**: .SON (sonar ping data)
- **Index**: .IDX (file indexing)
- **Data**: Sidescan, downscan, GPS, depth
- **Channels**: Typically 2-4 channels

### Lowrance (.sl2/.sl3)
- **Format**: Structured Log format
- **Channels**: .sl2 (2 channels), .sl3 (3+ channels)
- **Data**: High-resolution sidescan, structure scan
- **GPS**: Integrated positioning
- **Reference**: [Navico SLG Format PDF](https://www.memotech.franken.de/FileFormats/Navico_SLG_Format.pdf)

### EdgeTech (.jsf)
- **Format**: JSF (JSTAR Format) 
- **Use**: Professional marine surveys
- **Channels**: High-resolution dual frequency
- **Data**: Georeferenced sidescan sonar
- **Features**: Sub-bottom profiling, bathymetry

### Garmin (.rsd) - Enhanced
- **Current**: Basic parsing working
- **Reference**: [Garmin RSD Format PDF](https://www.memotech.franken.de/FileFormats/Garmin_RSD_Format.pdf)
- **Enhancements needed**: Depth field decoding, advanced GPS precision

## Architecture Plan

### Phase 1: Format Detection Engine
```python
# format_detector.py
def detect_sonar_format(file_path):
    """Auto-detect sonar file format"""
    formats = {
        '.rsd': 'garmin',
        '.sl2': 'lowrance_sl2', 
        '.sl3': 'lowrance_sl3',
        '.DAT': 'humminbird',
        '.jsf': 'edgetech',
        '.svlog': 'cerulean'
    }
```

### Phase 2: Universal Parser Interface
```python
# universal_parser.py
class UniversalSonarParser:
    def __init__(self, file_path):
        self.format = detect_sonar_format(file_path)
        self.parser = self._get_parser()
    
    def parse_records(self, max_records=None):
        """Universal parsing interface"""
        return self.parser.parse_records(max_records)
    
    def get_channels(self):
        """Get available channels for any format"""
        return self.parser.get_channels()
```

### Phase 3: Format-Specific Parsers
```
parsers/
├── garmin_parser.py      # Enhanced RSD support
├── humminbird_parser.py  # .DAT/.SON/.IDX
├── lowrance_parser.py    # .sl2/.sl3  
├── edgetech_parser.py    # .jsf
├── cerulean_parser.py    # .svlog
└── base_parser.py        # Common interface
```

## Implementation Strategy

### Leverage Existing Work
1. **PINGVerter Integration**: Use as reference for format specifications
2. **PyHum**: Established sidescan processing algorithms
3. **SL3Reader**: Proven Lowrance format handling
4. **Format Documentation**: Herbert Oppmann's PDF specifications

### Rust Acceleration Benefits
- **All Formats**: Rust core benefits every format
- **Memory Efficiency**: Handle large multi-format files
- **Performance**: 10-100x speedup applies universally
- **Cross-Platform**: Single codebase for all platforms

## Enhanced Feature Matrix

| Format | Sidescan | Downscan | GPS | Depth | Multi-Freq | Status |
|--------|----------|----------|-----|-------|------------|--------|
| Garmin RSD | ✅ | ✅ | ✅ | ⚠️ | ✅ | Current |
| Humminbird | 🎯 | 🎯 | 🎯 | 🎯 | 🎯 | Planned |
| Lowrance | 🎯 | 🎯 | 🎯 | 🎯 | 🎯 | Planned |
| EdgeTech | 🎯 | ❌ | 🎯 | 🎯 | 🎯 | Planned |
| Cerulean | 🎯 | ❌ | 🎯 | 🎯 | ❌ | Planned |

## GUI Integration

### Universal File Dialog
```python
# Support all formats in single dialog
file_types = [
    ("All Sonar Files", "*.rsd;*.sl2;*.sl3;*.DAT;*.jsf;*.svlog"),
    ("Garmin RSD", "*.rsd"),
    ("Lowrance", "*.sl2;*.sl3"), 
    ("Humminbird", "*.DAT"),
    ("EdgeTech", "*.jsf"),
    ("Cerulean", "*.svlog")
]
```

### Format-Specific Options
- **Auto-detection** with manual override
- **Format-specific** optimization settings
- **Channel mapping** for different manufacturers
- **Coordinate system** handling per format

## Performance Targets

### Rust-Accelerated Multi-Format
- **Garmin RSD**: Current 3-6s for 1600 frames
- **Humminbird**: Target 5-8s for equivalent data
- **Lowrance**: Target 4-7s (efficient format)
- **EdgeTech**: Target 8-15s (high-resolution data)

## Development Roadmap

### Immediate (Current Branch)
1. ✅ Rust video acceleration framework
2. 🔄 Enhanced Garmin RSD depth parsing
3. ⏳ Multi-format detection engine

### Phase 1 (Next 2 weeks)
1. Humminbird .DAT parser
2. Lowrance .sl2 parser  
3. Universal parser interface
4. Format auto-detection

### Phase 2 (Next month)
1. EdgeTech .jsf support
2. Advanced GPS coordinate handling
3. Multi-frequency channel support
4. Professional export options

### Phase 3 (Future)
1. Cerulean .svlog support
2. Custom format plugins
3. Real-time sonar processing
4. Advanced substrate classification

## References & Acknowledgments

Based on research and documentation from:
- **PINGVerter**: Cameron Bodine's multi-format converter
- **PINGMapper**: Comprehensive sonar processing suite
- **PyHum**: Daniel Buscombe's sidescan algorithms
- **Format Specs**: Herbert Oppmann's technical documentation
- **SL3Reader**: Lowrance format reference implementation

This expansion will make RSD Studio the most comprehensive open-source sonar processing tool available, supporting virtually all commercial fishfinder and professional sonar formats.