#!/usr/bin/env bash
# Setup and start image generation server on Lightning.ai
set -e
cd "$(dirname "$0")"

# Install deps if needed
pip install -q -r requirements.txt

# Load optional .env from this directory
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# Fast defaults for remote image + I2V generation. Override in .env if needed.
: "${SD_MODEL:=stabilityai/stable-diffusion-3.5-medium}"
: "${SD_STEPS:=20}"
: "${SD_WIDTH:=768}"
: "${SD_HEIGHT:=768}"
: "${SD_CFG:=7.0}"

: "${I2V_MODEL:=stabilityai/stable-video-diffusion-img2vid-xt}"
: "${I2V_STEPS:=15}"
: "${I2V_FRAMES:=49}"
: "${I2V_WIDTH:=768}"
: "${I2V_HEIGHT:=432}"

export SD_MODEL SD_STEPS SD_WIDTH SD_HEIGHT SD_CFG
export I2V_MODEL I2V_STEPS I2V_FRAMES I2V_WIDTH I2V_HEIGHT

echo "Starting image server on port 8001"
echo "Image model: $SD_MODEL | steps=$SD_STEPS | size=${SD_WIDTH}x${SD_HEIGHT}"
echo "I2V model:   $I2V_MODEL | steps=$I2V_STEPS | frames=$I2V_FRAMES | size=${I2V_WIDTH}x${I2V_HEIGHT}"
python image_server.py
