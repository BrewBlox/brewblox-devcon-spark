#!/bin/bash
#
# Standalone script for compiling proto changes
# This is only required when making local inline changes
# When pulling external updates, use update-firmware.sh
#
set -euo pipefail
pushd "$(dirname "$0")/../brewblox_devcon_spark/codec" > /dev/null

rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/**.proto
