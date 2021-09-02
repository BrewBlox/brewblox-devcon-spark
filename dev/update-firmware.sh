#!/usr/bin/env bash
set -euo pipefail

# Args
RELEASE=${1:-"develop"}

# Push root dir
pushd "$(dirname "$0")/.." > /dev/null

# Download ini file from Azure
curl -sSf \
    -o ./firmware.ini \
    "https://brewblox.blob.core.windows.net/firmware/${RELEASE}-firmware.ini"

firmware_date=$(awk -F "=" '/firmware_date/ {print $2}' ./firmware.ini)
firmware_version=$(awk -F "=" '/firmware_version/ {print $2}' ./firmware.ini)

echo "Using firmware release ${firmware_date}-${firmware_version}"

# Pull submodule
proto_version=$(awk -F "=" '/proto_version/ {print $2}' ./firmware.ini)
proto_dir=brewblox_devcon_spark/codec/proto
git -C ${proto_dir} fetch
git -C ${proto_dir} checkout "${proto_version}"

# Compile proto files
pushd brewblox_devcon_spark/codec > /dev/null
rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto
popd > /dev/null
