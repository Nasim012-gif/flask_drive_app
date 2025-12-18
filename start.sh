#!/bin/bash
# Simple startup script for Flask Google Drive API

cd "$(dirname "$0")"
source venv/bin/activate
python app.py
