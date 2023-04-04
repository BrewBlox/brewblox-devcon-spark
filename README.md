# Spark Service

[![Build Status](https://dev.azure.com/brewblox/brewblox/_apis/build/status/BrewBlox.brewblox-devcon-spark?branchName=develop)](https://dev.azure.com/brewblox/brewblox/_build/latest?definitionId=1&branchName=develop)

**For user documentation, see <https://www.brewblox.com>**

The Spark service handles connectivity for the BrewPi Spark controller.

This includes USB/TCP communication with the controller, but also encoding, decoding, and broadcasting data.

## Installation

To set up the development environment, follow the instructions at <https://github.com/BrewBlox/brewblox-boilerplate#readme>.

When running integration tests (`pytest --integration`), additional system packages are required in order to run the firmware simulator:

```sh
sudo apt install -y \
    socat \
    libboost-system1.67.0 \
    libboost-program-options1.67.0 \
    libboost-random1.67.0 \
    libboost-thread1.67.0
```

When updating firmware, the protobuf compiler is required:

```sh
sudo apt install -y \
    protobuf-compiler
```

## Firmware

The Spark service is coupled to a specific Spark firmware version.
Version info is tracked in [firmware.ini](./firmware.ini), and firmware binaries are downloaded during the Docker image build.

Protobuf message definitions are loaded from the [Brewblox proto](https://github.com/BrewBlox/brewblox-proto) submodule at *[brewblox_devcon_spark/codec/proto](./brewblox_devcon_spark/codec/proto)*.
The firmware.ini file contains a sha for the relevant brewblox-proto commit.

The brewblox-proto repository only contains .proto files. The associated pb2.py files are compiled here and committed into version control.

Firmware dependency management is handled by scripts in *dev/*:

**[update-firmware.sh](./dev/update-firmware.sh)** fetches the latest firmware.ini file for a given firmware build (*develop* by default), checks out the associated brewblox-proto commit for the submodule, and calls both `compile-proto.sh` and `download-firmware.sh`.

**[compile-proto.sh](./dev/compile-proto.sh)** compiles .proto files found in the proto submodule into _pb2.py python files.
The_pb2.py files are committed into version control.

**[download-firmware.sh](./dev/download-firmware.sh)** reads the version information in firmware.ini,
and downloads the associated binary files into `firmware/`.
The binary files are **not** committed into version control.
Instead, they are re-downloaded during the CI build.

**To update the service when making changes to firmware:**

- Commit the firmware changes to the *develop* branch in the [Brewblox firmware](https://github.com/BrewBlox/brewblox-firmware) repository.
- Wait until the firmware CI build is done.
- Run `bash dev/update-firmware.sh`
- Run `pytest --integration` to verify that no code changes are required.
- Commit the changed files (firmware.ini, the proto submodule, and compiled _pb2.py files).
