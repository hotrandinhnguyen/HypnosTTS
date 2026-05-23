#!/usr/bin/env bash
set -e

echo "=== [1/2] Chrome dependencies ==="
sudo apt-get install -y \
  libnspr4 libnss3 \
  libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
  libgbm1 libasound2t64 \
  libx11-6 libxcb1 libxext6 libxrender1 \
  libpango-1.0-0 libpangocairo-1.0-0 \
  libcairo2 libfontconfig1

echo "=== [2/2] npm install ==="
npm install

echo "=== Done. ==="
