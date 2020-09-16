#!/usr/bin/env bash
set -ex

# This builds the ARM simulator matching the firmware in ./binaries.
# The sim is built separately, as it takes too long for dev CI builds (~45 mins).
# To do a full pull of firmware binaries, run:
#
#   bash pull-firmware.sh
#   bash build-arm-sim.sh
#

FW_DIR="$(readlink -f "${1:-"../brewblox-firmware"}")"
pushd "$(dirname "$0")" > /dev/null

# This prevents sudo blocking the script halfway through
sudo echo "Caching sudo permissions"

# We want to use the same git commit used to build the content of ./binaries
bin_fw_version=$(awk -F "=" '/firmware_version/ {print $2}' binaries/firmware.ini)

git -C "$FW_DIR" fetch --all
git -C "$FW_DIR" checkout "$bin_fw_version"
git -C "$FW_DIR" submodule update

date # Helps estimating ETA
bash "$FW_DIR"/docker/build-bin-arm.sh
cp "$FW_DIR"/build/target/brewblox-gcc/brewblox-gcc ./binaries/brewblox-arm

git -C "$FW_DIR" checkout -
git -C "$FW_DIR" submodule update

echo "Done!"
