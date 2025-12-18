#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Create necessary directories locally
mkdir -p static/qr_codes
mkdir -p static/event_photos
