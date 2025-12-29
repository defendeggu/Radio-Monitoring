#!/bin/bash

echo "========================================="
echo "Radio Transcription System - Setup"
echo "========================================="
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Warning: This setup script is designed for Linux."
    echo "For macOS, please install dependencies manually using Homebrew."
    echo ""
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "Please do not run this script as root"
   exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
echo "You may be prompted for your sudo password."
echo ""

sudo apt-get update
sudo apt-get install -y \
    libusb-1.0-0-dev \
    libhackrf-dev \
    hackrf \
    build-essential \
    python3-pip \
    python3-venv \
    direwolf \
    multimon-ng \
    libasound2-dev \
    cmake

# Create virtual environment
echo ""
echo "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
echo ""
echo "Creating directories..."
mkdir -p recordings

# Copy environment file
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env to customize your configuration"
fi

# Add user to plugdev group for USB access
echo ""
echo "Setting up USB permissions for HackRF..."
sudo usermod -a -G plugdev $USER

# Create udev rules for HackRF
echo ""
echo "Creating udev rules for HackRF..."
sudo tee /etc/udev/rules.d/53-hackrf.rules > /dev/null <<EOF
ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", SYMLINK+="hackrf-one-%k", MODE="660", GROUP="plugdev"
ATTR{idVendor}=="1d50", ATTR{idProduct}=="604b", SYMLINK+="hackrf-one-%k", MODE="660", GROUP="plugdev"
ATTR{idVendor}=="1d50", ATTR{idProduct}=="6062", SYMLINK+="rad1o-%k", MODE="660", GROUP="plugdev"
ATTR{idVendor}=="1d50", ATTR{idProduct}=="cc15", SYMLINK+="rad1o-%k", MODE="660", GROUP="plugdev"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

# Test HackRF connection
echo ""
echo "Testing HackRF connection..."
if command -v hackrf_info &> /dev/null; then
    hackrf_info
else
    echo "Warning: hackrf_info command not found. Please reconnect your HackRF device."
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Log out and log back in for USB permissions to take effect"
echo "2. Connect your HackRF device"
echo "3. Run: source venv/bin/activate"
echo "4. Run: ./start.sh"
echo ""
echo "Or use Docker:"
echo "  docker-compose up -d"
echo ""
