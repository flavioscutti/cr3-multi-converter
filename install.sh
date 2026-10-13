#!/bin/bash

echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo "Installing dependencies (dcraw, exiftool, Inter font)..."
sudo apt install dcraw libimage-exiftool-perl fonts-inter -y

echo "Checking for dnglab..."
# Note: if dnglab is not available in the apt repositories, download the binary
# from the official releases page: https://github.com/dnglab/dnglab/releases
if ! command -v dnglab &> /dev/null; then
    echo "dnglab not found. Make sure to place the dnglab binary in /usr/local/bin/"
fi

echo "Installation completed successfully!"
