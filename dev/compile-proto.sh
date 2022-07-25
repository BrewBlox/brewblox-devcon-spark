#!/bin/bash
#
# Standalone script for compiling proto changes
# This is only required when making local inline changes
# When pulling external updates, use update-firmware.sh
#
set -euo pipefail
pushd "$(git rev-parse --show-toplevel)" >/dev/null

TARGET=brewblox_devcon_spark/codec/proto-compiled

rm -f ${TARGET}/*_pb2.py
protoc -I=./brewblox-proto/proto --python_out=${TARGET} ./brewblox-proto/proto/**.proto
