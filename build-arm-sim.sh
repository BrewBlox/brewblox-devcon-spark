#!/usr/bin/env bash
set -ex

# This builds the ARM simulator matching the firmware in firmware-bin/.
# The sim is built separately, as it takes too long for dev CI builds (~45 mins).
# To do a full pull of firmware files, run:
#
#   bash pull-firmware.sh
#   bash build-arm-sim.sh
#

FW_DIR="$(readlink -f "${1:-"../brewblox-firmware"}")"
pushd "$(dirname "$0")" > /dev/null

# This prevents sudo blocking the script halfway through
sudo echo "Caching sudo permissions"

# We want to use the same git commit used to build the content of ./binaries
bin_fw_version=$(awk -F "=" '/firmware_version/ {print $2}' ./firmware-bin/binaries/firmware.ini)

git -C "$FW_DIR" fetch --all
git -C "$FW_DIR" checkout "$bin_fw_version"
git -C "$FW_DIR" submodule update

date # Start 32
bash "$FW_DIR"/build/build-sim-arm32.sh
cp "$FW_DIR"/build/target/brewblox-gcc/brewblox-gcc ./firmware-bin/binaries/brewblox-arm32.sim

date # Start 64
bash "$FW_DIR"/build/build-sim-arm64.sh
cp "$FW_DIR"/build/target/brewblox-gcc/brewblox-gcc ./firmware-bin/binaries/brewblox-arm64.sim

git -C "$FW_DIR" checkout -
git -C "$FW_DIR" submodule update

date # End
echo "Done!"
