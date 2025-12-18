#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create necessary directories on the persistent disk if they don't exist
mkdir -p /data/qr_codes
mkdir -p /data/event_photos
mkdir -p /data/db

# Symlink local static directories to persistent disk
# This ensures images survive redeploys
ln -sfn /data/qr_codes static/qr_codes
ln -sfn /data/event_photos static/event_photos
