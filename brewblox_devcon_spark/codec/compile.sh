#!/usr/bin/env bash

# Proto files are relative to script directory, not current directory
# Pushd script directory
pushd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )" > /dev/null

rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto

popd > /dev/null
