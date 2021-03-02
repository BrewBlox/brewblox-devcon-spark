#! /usr/bin/env bash
# Automatically executed by CI
set -e
pushd "$(dirname "$0")/.." > /dev/null

rm -rf flasher/firmware-bin
cp -rf firmware-bin/ flasher/
