#!/usr/bin/env bash
# Setup and start image generation server on Lightning.ai
set -e
cd "$(dirname "$0")"

# Install deps if needed
pip install -q -r requirements.txt

# Load .env
export $(grep -v '^#' .env | xargs)

echo "Starting image server on port 8001 (model: $FLUX_MODEL)"
python image_server.py
