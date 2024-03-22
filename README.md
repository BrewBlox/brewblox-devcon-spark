# Spark Service

[![CI build](https://github.com/BrewBlox/brewblox-devcon-spark/actions/workflows/build.yml/badge.svg)](https://github.com/BrewBlox/brewblox-devcon-spark/actions/workflows/build.yml)

**For user documentation, see <https://www.brewblox.com>**

The Spark service handles connectivity for the BrewPi Spark controller.

This includes USB/TCP communication with the controller, but also encoding, decoding, and broadcasting data.

## Installation

To set up the development environment, follow the instructions at <https://brewblox.com/dev/python_env.html>.

## Tests

Integration tests run against the firmware simulator. This firmware is downloaded, but not committed.
To ensure you have the latest firmware, run `invoke download-firmware`.
This also happens during `invoke update-firmware`.

During tests, you may need to kill the pytest process.
This will cause it to skip test teardown, and leave leftover containers and processes. \
To remove these leftovers, run `invoke testclean`.

## Firmware

The Spark service is coupled to a specific Spark firmware version.
Version info is tracked in [firmware.ini](./firmware.ini), and firmware binaries are downloaded during the Docker image build.

Protobuf message definitions are loaded from the [Brewblox proto](https://github.com/BrewBlox/brewblox-proto) submodule at *[brewblox_devcon_spark/codec/proto](./brewblox_devcon_spark/codec/proto)*.
The firmware.ini file contains a sha for the relevant brewblox-proto commit.

The brewblox-proto repository only contains .proto files. The associated pb2.py files are compiled here and committed into version control.

Firmware dependency management is handled by [invoke](https://docs.pyinvoke.org/en/stable/index.html) commands, defined in `tasks.py`:

`invoke update-firmware` fetches the latest firmware.ini file for a given firmware build (*develop* by default),
checks out the associated brewblox-proto commit for the submodule, and then calls `compile-proto` and `download-firmware`.

`invoke compile-proto` compiles .proto files found in the proto submodule into _pb2.py python files.
The_pb2.py files are committed into version control.

`invoke download-firmware` reads the version information in firmware.ini,
and downloads the associated binary files into `firmware/`.
The binary files are **not** committed into version control.
Instead, they are re-downloaded during the CI build.

**To update the service when making changes to firmware:**

- Commit the firmware changes to the *develop* branch in the [Brewblox firmware](https://github.com/BrewBlox/brewblox-firmware) repository.
- Wait until the firmware CI build is done.
- Run `invoke update-firmware`
- Run `pytest` to verify that no code changes are required.
- Commit the changed files (firmware.ini, the proto submodule, and compiled _pb2.py files).
