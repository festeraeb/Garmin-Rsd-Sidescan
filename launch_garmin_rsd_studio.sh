#!/bin/bash

# ====================================================================
# Garmin RSD Studio - macOS/Linux Launcher with Environment Setup
# Professional Marine Survey Analysis
# Contact: festeraeb@yahoo.com for licensing
# ====================================================================

echo ""
echo "=========================================="
echo "  🌊 Garmin RSD Studio - Beta Launch  "
echo "=========================================="
echo ""

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_info() {
    echo -e "${BLUE}📦${NC} $1"
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        echo ""
        echo "Please install Python 3.8+ from: https://python.org"
        echo "On macOS: brew install python"
        echo "On Ubuntu/Debian: sudo apt install python3 python3-pip"
        echo "On CentOS/RHEL: sudo yum install python3 python3-pip"
        echo ""
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Display Python version
print_status "Python detected:"
$PYTHON_CMD --version

# Check if we're in the right directory
if [ ! -f "studio_gui_engines_v3_14.py" ]; then
    echo ""
    print_error "studio_gui_engines_v3_14.py not found"
    echo "Please run this script from the Garmin RSD Studio directory"
    echo ""
    exit 1
fi

echo ""
print_info "Checking dependencies..."

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    print_warning "requirements.txt not found - creating minimal requirements"
    cat > requirements.txt << EOF
tkinter
numpy
matplotlib
EOF
fi

# Install/update dependencies
echo "Installing required packages..."

# Try pip3 first, then pip
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    print_error "pip is not installed"
    echo "Please install pip:"
    echo "On macOS: python3 -m ensurepip --upgrade"
    echo "On Ubuntu/Debian: sudo apt install python3-pip"
    echo "On CentOS/RHEL: sudo yum install python3-pip"
    exit 1
fi

$PIP_CMD install --upgrade pip
$PIP_CMD install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    print_warning "Some packages may have failed to install"
    echo "Continuing with available packages..."
    echo ""
fi

# Check for tkinter (common issue on Linux)
$PYTHON_CMD -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    print_warning "tkinter not available"
    echo "On Ubuntu/Debian: sudo apt install python3-tk"
    echo "On CentOS/RHEL: sudo yum install tkinter"
    echo "On macOS: tkinter should be included with Python"
    echo ""
    echo "Attempting to continue anyway..."
fi

echo ""
echo "🚀 Launching Garmin RSD Studio..."
echo ""

# Launch the application
$PYTHON_CMD studio_gui_engines_v3_14.py

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    print_error "Application exited with error"
    echo ""
    echo "📧 For support, contact: festeraeb@yahoo.com"
    echo "🆘 SAR Groups: FREE licensing available"
    echo "💼 Commercial: One-time purchase (no yearly fees)"
    echo ""
    exit 1
fi

echo ""
print_status "Garmin RSD Studio closed successfully"
echo ""
echo "📧 For licensing and support: festeraeb@yahoo.com"
echo "🆘 SAR Groups: FREE licensing available"
echo "💼 Commercial: One-time purchase licensing"
echo ""