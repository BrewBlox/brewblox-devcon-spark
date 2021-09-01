#!/usr/bin/env bash
set -euo pipefail

# Args
VERSION=${1:-""}

# Push script dir
pushd "$(dirname "$0")" > /dev/null

# Check for required tools
if ! command -v gh &> /dev/null
then
    echo "ERROR: Github CLI could not be found. To install: https://cli.github.com/manual/installation"
    exit 1
fi
if ! command -v az &> /dev/null
then
    echo "ERROR: Azure CLI could not be found. To install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt"
    exit 1
fi

# Version must match 'vMAJOR.MINOR.PATCH', with an optional postfix
if [[ ! "${VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(\-.+)?$ ]]
then
    echo "ERROR: Missing or invalid version argument."
    echo "ERROR: Version '${VERSION}' must be formatted as 'vMAJOR.MINOR.PATCH'"
    exit 1
fi

# Azure SAS token must have been set to upload to Azure
if [[ -z "${AZURE_STORAGE_SAS_TOKEN}" ]]
then
    echo "ERROR: AZURE_STORAGE_SAS_TOKEN was not set."
    exit 1
fi

echo "Using firmware release ${VERSION}"

# Cleanup
rm -rf ./firmware

# Download files
gh release download "${VERSION}" -R BrewBlox/brewblox-firmware -D ./firmware

# Make simulators executable
chmod a+x ./firmware/*.sim

# Pull submodule
proto_version=$(awk -F "=" '/proto_version/ {print $2}' ./firmware/firmware.ini)
proto_dir=brewblox_devcon_spark/codec/proto
git -C ${proto_dir} fetch
git -C ${proto_dir} checkout "${proto_version}"

# Compile proto files
pushd brewblox_devcon_spark/codec > /dev/null
rm -f ./proto-compiled/*_pb2.py
protoc -I=./proto --python_out=./proto-compiled ./proto/*.proto
popd > /dev/null

# Upload ESP32 firmware to Azure
# - This requires Azure CLI to be installed
# - This requires the environment variable AZURE_STORAGE_SAS_TOKEN to be set
az storage blob upload \
    --account-name brewblox \
    --container-name firmware \
    --name "brewblox-esp32-${VERSION}.bin" \
    --file ./firmware/brewblox-esp32.bin
