#! /usr/bin/env bash
# Automatically executed by CI
set -e

pushd "$(dirname "$(readlink -f "$0")")/.." > /dev/null

cp -rf binaries/ flasher/

popd > /dev/null
