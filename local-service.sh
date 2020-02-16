#! /usr/bin/env bash

# Copies the service dir to current working directory
# This allows manual testing without the hassle of building docker images
# This assumes the existence of ../brewblox-service

sudo rm -rf ./brewblox_service
cp -r ../brewblox-service/brewblox_service ./
find ./brewblox_service/ | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
