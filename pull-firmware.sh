#!/usr/bin/env bash
set -e

# Args
TAG=${1:-"develop"}
echo "Using brewblox/firmware-bin:${TAG}"

# Nagivate to script dir
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
pushd "${SCRIPT_DIR}" > /dev/null

# Pull image
docker rm bin-box 2> /dev/null || true
if [ $TAG != "local" ]
then
    docker pull brewblox/firmware-bin:${TAG}
fi
docker create --name bin-box brewblox/firmware-bin:${TAG}

# Get files
rm -rf ./binaries 2> /dev/null || true
docker cp bin-box:/binaries ./

# Remove image
docker rm bin-box > /dev/null

# Pull submodule
proto_version=$(awk -F "=" '/proto_version/ {print $2}' binaries/firmware.ini)
cd brewblox_devcon_spark/codec/proto
git checkout ${proto_version}
cd ../../..

# Compile proto files
pushd brewblox_devcon_spark/codec > /dev/null
rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto
popd > /dev/null

# Get bootloader and system files
PARTICLE_VERSION=1.2.1-rc.2
PARTICLE_RELEASES=https://github.com/particle-iot/device-os/releases/download/v${PARTICLE_VERSION}

curl -sL -o ./binaries/bootloader-p1.bin ${PARTICLE_RELEASES}/p1-bootloader@${PARTICLE_VERSION}.bin
curl -sL -o ./binaries/system-part1-p1.bin ${PARTICLE_RELEASES}/p1-system-part1@${PARTICLE_VERSION}.bin
curl -sL -o ./binaries/system-part2-p1.bin ${PARTICLE_RELEASES}/p1-system-part2@${PARTICLE_VERSION}.bin

curl -sL -o ./binaries/bootloader-photon.bin ${PARTICLE_RELEASES}/photon-bootloader@${PARTICLE_VERSION}.bin
curl -sL -o ./binaries/system-part1-photon.bin ${PARTICLE_RELEASES}/photon-system-part1@${PARTICLE_VERSION}.bin
curl -sL -o ./binaries/system-part2-photon.bin ${PARTICLE_RELEASES}/photon-system-part2@${PARTICLE_VERSION}.bin

# Pop script dir
popd > /dev/null
