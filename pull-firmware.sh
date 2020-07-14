#!/usr/bin/env bash
set -e

# Args
TAG=${1:-"develop"}
echo "Using brewblox/firmware-bin:${TAG}"

# Push script dir
pushd "$(dirname "$(readlink -f "$0")")" > /dev/null

# Pull image
docker rm bin-box 2> /dev/null || true
if [ "${TAG}" != "local" ]
then
    docker pull brewblox/firmware-bin:"${TAG}"
fi
docker create --name bin-box brewblox/firmware-bin:"${TAG}"

# Get files
rm -rf ./binaries 2> /dev/null || true
docker cp bin-box:/binaries ./

# Make simulator executable
chmod a+x ./binaries/brewblox-amd

# Remove image
docker rm bin-box > /dev/null

# Pull submodule
proto_version=$(awk -F "=" '/proto_version/ {print $2}' binaries/firmware.ini)
proto_dir=brewblox_devcon_spark/codec/proto
git -C ${proto_dir} fetch
git -C ${proto_dir} checkout "${proto_version}"

# Compile proto files
pushd brewblox_devcon_spark/codec > /dev/null
rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto
popd > /dev/null
