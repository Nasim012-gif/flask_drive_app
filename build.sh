#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create necessary directories locally
mkdir -p static/qr_codes
mkdir -p static/event_photos
