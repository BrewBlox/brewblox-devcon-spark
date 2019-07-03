#!/usr/bin/env bash

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
pushd "${SCRIPT_DIR}" > /dev/null

TAG=${2:-"newest-tag"}

# Pull image
docker rm bin-box 2> /dev/null || true
docker pull brewblox/firmware-bin:${TAG}
docker create --name bin-box brewblox/firmware-bin:${TAG}

# Get files
rm -rf ./binaries 2> /dev/null || true
docker cp bin-box:/binaries ./

# Remove image
docker rm bin-box

popd > /dev/null