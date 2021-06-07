#! /bin/bash
set -ex

export PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
export PIP_FIND_LINKS=/wheeley

mkdir /wheeley
pip3 install --upgrade pip wheel
pip3 wheel --wheel-dir=/wheeley -r /app/requirements.txt
pip3 wheel --wheel-dir=/wheeley /app/dist/*
