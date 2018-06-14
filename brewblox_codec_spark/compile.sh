#! /bin/sh

protoc -I=./proto --python_out=./proto ./proto/*.proto
