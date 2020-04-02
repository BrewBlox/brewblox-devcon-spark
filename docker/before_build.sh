#!/usr/bin/env bash
# Automatically executed by CI
set -e

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
pushd "$SCRIPT_DIR/.." > /dev/null

rm -rf dist docker/dist docker/binaries

poetry build --format sdist
poetry export --without-hashes -f requirements.txt -o docker/requirements.txt

cp -rf dist/ docker/
cp -rf binaries/ docker/

popd > /dev/null
