#!/usr/bin/env bash
# Exit on error
set -o errexit

STORAGE_DIR=/opt/render/project/src/chrome

echo "Build starting..."

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download and install Chrome locally
if [[ ! -d "$STORAGE_DIR" ]]; then
  echo "...Downloading Chrome"
  mkdir -p "$STORAGE_DIR"
  cd "$STORAGE_DIR"
  
  # Download the stable Chrome .deb file
  wget -q -O chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  
  # Unpack it locally (since we can't use sudo apt-get)
  dpkg -x chrome.deb "$STORAGE_DIR"
  
  rm chrome.deb
  cd /opt/render/project/src # Go back to project root
  echo "...Chrome extracted to $STORAGE_DIR"
else
  echo "...Chrome already exists, skipping download"
fi
