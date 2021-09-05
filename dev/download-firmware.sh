#!/usr/bin/env bash
set -euo pipefail

# Push root dir
pushd "$(dirname "$0")/.." > /dev/null

firmware_date=$(awk -F "=" '/firmware_date/ {print $2}' ./firmware.ini)
firmware_version=$(awk -F "=" '/firmware_version/ {print $2}' ./firmware.ini)

echo "Using firmware version ${firmware_date}-${firmware_version}"

mkdir -p ./firmware
rm -rf ./firmware/*

# Download all firmware files
curl -sSf \
    "https://brewblox.blob.core.windows.net/firmware/${firmware_date}-${firmware_version}/brewblox-release.tar.gz" \
    | tar -C ./firmware -xzv

# Make simulators executable
chmod +x ./firmware/*.sim
