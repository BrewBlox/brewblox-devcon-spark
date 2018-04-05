#!/bin/sh

mkdir -p "$1"
cp .tox/dist/* "$1"/
ls "$1"
