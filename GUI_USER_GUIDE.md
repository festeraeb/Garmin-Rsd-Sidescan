# Enhanced RSD Studio GUI - User Guide

## Overview

The enhanced RSD Studio GUI now features a tabbed interface that separates main file processing from advanced target detection capabilities. This design keeps the interface clean while providing powerful analysis tools for specialized users.

## Interface Structure

### 📁 File Processing Tab
The main tab for standard RSD file processing operations:

#### Input Settings
- **RSD File**: Select your Garmin RSD file for processing
- **Parser Engine**: Choose from three options:
  - `auto-nextgen-then-classic`: Recommended - tries next-gen first, falls back to classic
  - `nextgen`: Tolerant parsing with better resync heuristics
  - `classic`: Strict CRC checking, conservative failure handling

#### Parse Options
- **Limit Rows**: Optional limit on number of records to process (useful for testing)
- **Output Directory**: Where to save the parsed CSV files
- **Parse Button**: Start the RSD file processing

#### Preview & Export
- **CSV Records**: Select the CSV file generated from parsing
- **Build Preview**: Generate a waterfall preview image
- **Export Video**: Create an MP4 waterfall video

#### Output Log
Real-time display of processing status and results.

### 🎯 Target Detection Tab (Advanced)
Advanced features for SAR (Search and Rescue) and wreck hunting applications:

#### Target Detection Settings
- **CSV Records File**: Select the parsed CSV file for block analysis
- **Detection Mode**: 
  - `SAR`: Optimized for Search and Rescue victim detection (0.3-2m targets)
  - `Wreck Hunting`: Optimized for larger wreck detection (2-100m targets)
  - `General`: General purpose anomaly detection
- **Detection Sensitivity**: Slider from 0.1 (conservative) to 1.0 (aggressive)

#### Analysis Controls
- **Run Block Analysis**: Start the target detection analysis
- **Detection Results**: Summary of found targets with GPS coordinates and confidence scores

#### Report Generation
- **SAR Report**: Generate professional Search and Rescue report
- **Wreck Report**: Generate wreck hunting survey report

#### Target Visualization
- **Target Map**: Visual display of detected targets (planned feature)
- **Reports**: Full text reports with professional formatting

### ℹ️ About Tab
Information about the software, features, and credits.

## Workflow Guide

### Standard File Processing Workflow
1. **Select RSD File**: Use the Browse button in the File Processing tab
2. **Choose Parser**: Select appropriate engine (auto is recommended)
3. **Set Output**: Choose output directory for CSV files
4. **Parse**: Click "Parse RSD File" and monitor progress
5. **Preview**: Build preview images from the generated CSV
6. **Export**: Create MP4 waterfall videos for sharing

### Advanced Target Detection Workflow
1. **Parse RSD File**: First complete the standard workflow to generate CSV
2. **Switch to Target Detection Tab**: Click the "🎯 Target Detection (Advanced)" tab
3. **Select CSV**: Choose the CSV file from your parse operation
4. **Configure Detection**:
   - Set detection mode based on your mission (SAR vs Wreck Hunting)
   - Adjust sensitivity based on conditions and requirements
5. **Run Analysis**: Click "Run Block Analysis" and wait for completion
6. **Review Results**: Examine detected targets in the results summary
7. **Generate Reports**: Create professional SAR or wreck hunting reports

## Target Detection Features

### Block-Level Analysis
- Processes sonar data in 25-record blocks for better signal analysis
- Uses phase correlation for automatic alignment
- Implements machine learning for anomaly detection

### Detection Capabilities
- **SAR Mode**: Optimized for human-sized targets (0.3-2m)
  - Detects potential victims in water
  - Identifies debris fields
  - Provides GPS coordinates for rescue teams
- **Wreck Hunting Mode**: Optimized for larger structures (2-100m)
  - Detects shipwrecks and large debris
  - Analyzes acoustic shadows
  - Measures target dimensions

### Professional Reporting
- GPS coordinates with high precision
- Confidence scoring for each detection
- Standardized report formats
- Suitable for emergency response documentation

## Technical Notes

### System Requirements
- Windows 10/11 (PowerShell environment)
- Python 3.8+ with required packages
- Sufficient disk space for RSD processing and video export

### Performance Considerations
- Large RSD files may take significant time to process
- Target detection analysis is computationally intensive
- Use row limits for testing with large files
- Background processing prevents UI freezing

### File Formats
- **Input**: Garmin RSD files (.RSD)
- **Intermediate**: CSV records with GPS and sonar data  
- **Output**: MP4 waterfall videos, preview images, text reports

## Troubleshooting

### Common Issues
1. **Parser Fails**: Try different engine (classic vs nextgen)
2. **Target Detection Unavailable**: Ensure block_target_detection.py is present
3. **Memory Issues**: Use row limits for very large RSD files
4. **Video Export Fails**: Check available codecs and disk space

### Error Messages
- Monitor the Output Log for detailed error information
- Progress bars indicate current operation status
- Report generation requires completed target analysis

## Educational Applications

### CESARops Program
This tool is designed to support high school emergency response education:
- Teaches sonar data analysis principles
- Provides hands-on experience with professional tools
- Demonstrates real-world SAR techniques
- Builds technical skills for emergency response careers

### Training Scenarios
- Practice target detection on test data
- Learn to interpret sonar signatures
- Understand GPS coordinate systems
- Generate professional reports

## Support and Development

### Getting Help
- Check the About tab for version information
- Review error messages in the Output Log
- Ensure all required Python packages are installed

### Advanced Users
- Modify detection parameters in block_target_detection.py
- Customize report templates for specific needs
- Integrate with external mapping systems
- Extend colormap options for different display preferences

## Version History

### v3.14 - Enhanced Edition
- Added tabbed interface for better organization
- Integrated advanced target detection capabilities
- Implemented professional reporting system
- Enhanced for CESARops educational program
- Improved error handling and user feedback
- Added progress tracking for long operations

This enhanced version maintains backward compatibility while adding powerful new capabilities for specialized users.