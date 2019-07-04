#!/usr/bin/env bash

# Proto files are relative to script directory, not current directory
# Pushd script directory
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
pushd "${SCRIPT_DIR}" > /dev/null

# Write to settings file #####
FILE="config/protobuf.ini"

rm $FILE 2> /dev/null || true
touch $FILE

# Needs an update if we get a second submodule
echo "[PROTOBUF]" >> $FILE
echo "proto_version=$(git submodule --quiet foreach git rev-parse --short HEAD)" >> $FILE
echo "proto_date=$(git submodule --quiet foreach git show -s --format=%ci)" >> $FILE

# Compile proto files
pushd brewblox_devcon_spark/codec > /dev/null

rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto

popd > /dev/null
popd > /dev/null
