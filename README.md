[![Build Status](https://dev.azure.com/brewblox/brewblox/_apis/build/status/BrewBlox.brewblox-devcon-spark?branchName=develop)](https://dev.azure.com/brewblox/brewblox/_build/latest?definitionId=1&branchName=develop)

# Spark Service

The Spark service handles connectivity for the BrewPi Spark controller.

This includes USB/TCP communication with the controller, but also encoding, decoding, and broadcasting data.

![Command Transformation](https://www.plantuml.com/plantuml/png/0/dLPDZ-Cs3BtdLn2vJ5BaurBqC2YAdSnaiLkqdS4cnHuBHQPZxTYIAygJCOh-zrAIl-99kjZroRQaH_BnaTGxSiAwgiZXtXI5q0dihT2K6bi8fuoUJ4fUL_uLfg9KgxAUmZyJu6VsmnoMorzW-WabgXU43_lz4rZykq9oqx0bB3y9ImZ27gi2jID8hIdEziAiiZcmxRMnS319FPzE-kE_YnBCuGjAjwQQ71RhqffKvGZtd_vyWBJICdZd3EpOrsUGCH2ABcZZ4AmwPYvy-cVxAeeonrjuUjpjOKt-r3gQeE2JiaWW67zxjz_-zRZvTNk_Rs4N7OmdIq0Yd01onY98Yy9XM4TUyvOdCP01Xmc-A8a36hj0xur-GUk0LEA3qIgPTXikHE6VVSPMZNRMv3bQ44Jgg0aqCssLX8yF13F6cNkyJMxaCwtEphzdmYiI1vKhLo_0CLpO1ee0NqjZ7IPmKYxZG2j2kvIPq4TnOFB9MQMFR09cxF3y7FS3CXqUhT_5Y386Y24ylzhx2S_Qd7JxlmzfDJd3lTFibiGoKCc8LYXYE9KoGKCqQQeyWGD2QYgTzBxrQMd_338ZJOAI4mCprFvzFinGbwLjM8D3eCadVtgsvqgY_DFcbpMZf0EJ3cg20t-onfb3bIwZTNQ_TZZAbtzsfi2eEbUNs0cMOKkBIwuDYIm39frhfHpnrt4O2i0p-AZnCv_UL7JxPcVh4J0lx161OazlH99mUT0Df0gPv5bmSyxQWuCW_Ed79kSNFDzOFB6yNk4aGimP5am5bRceUqrucNcmZ9rakweG-NN4VQR2JlYPKzEOZogZHY69qHodZkoCoF7_8zcpaNuxdRG__hsYcD0IMARdvTo9PLCffgZfhDyY58wuOeruYIEL_ArypN5NRel8nn1B9NRjCoaroda3_0VRl0KXfR59030UBjfQ32GD8kTMbjJU_aq0kxd2pzkGTtwjYNW1F4Ha5Zi8qv_NqmidudpuLf9ywwEwA92r8LaZfYmDATxETJNYVNMj59jP52BqP5oep0iiRdgUoAayzoo9bgTcLB4eBNwdfjek5AlkSXTwmE_jGhjhd7sbiVsV-y6bkoHfHrV0-Ehm-isOPuAg134O4ouJBge6QJGZLcz67zT6bOTIQ5W_-NJuwI6uj0-6LSVJBmngzcoKoiyPSeTmle9YzdbQBaRZfvbQV9ZJcSI9PYeh0sDSDYuxT-fZ64HzD5BeRWej8BGYQgu9_1ty4Y-nz_NtY0lZQi1tS-DobTMZ2zU4TxpZ8toP-my0 "Command Transformation")

## Installation

When running integration tests (`pytest --integration`), additional dependencies are required in order to run the firmware simulator.

To install:
```
sudo apt update -y && \
sudo apt install -y \
    socat \
    libboost-system1.67.0 \
    libboost-program-options1.67.0 \
    libboost-random1.67.0 \
    libboost-thread1.67.0
```

## Features

### SparkConnection ([connection.py](./brewblox_devcon_spark/connection.py))

Direct communication with the Spark is handled here, for both USB and TCP connections. Data is not decoded or interpreted, but passed on to the `SparkCommander`.

### Controlbox Protocol ([commands.py](./brewblox_devcon_spark/commands.py))

The Spark communicates using the [Controlbox protocol](https://brewblox.netlify.com/dev/reference/spark_commands.html). A set of commands is defined to manage blocks on the controller.

In the commands module, this protocol of bits and bytes is encapsulated by `Command` classes. They are capable of converting a Python dict to a hexadecimal byte string, and vice versa.

### SparkCommander ([commander.py](./brewblox_devcon_spark/commander.py))

Serial communication is asynchronous: requests and responses are not linked at the transport layer.

`SparkCommander` is responsible for building and sending a command, and then matching it with a subsequently received response.

### SimulationCommander ([commander_sim.py](./brewblox_devcon_spark/commander_sim.py))

For when using an actual Spark is inconvenient, there is a simulation version. It serves as a drop-in replacement for the real commander: it handles commands, and returns sensible values.
Commands are encoded/decoded, to closely match the real situation.

### Datastore ([block_store.py](./brewblox_devcon_spark/block_store.py) / [service_store.py](./brewblox_devcon_spark/service_store.py)) / [global_store.py](./brewblox_devcon_spark/global_store.py))

The service must keep track of object metadata not directly persisted by the controller. This includes user-defined object names and descriptions.

Services are capable of interacting with a BrewPi Spark that has pre-existing blocks, but will be unable to display objects with a human-meaningful name.

Object metadata is persisted to files. This does not include object settings - these are the responsibility of the Spark itself.

### Codec ([codec.py](./brewblox_devcon_spark/codec/codec.py))

While the controller <-> service communication uses the Controlbox protocol, individual objects are encoded separately, using Google's [Protocol Buffers](https://developers.google.com/protocol-buffers/).

The codec is responsible for converting JSON-serializable dicts to byte arrays, and vice versa. A specific transcoder is defined for each object.

For this reason, the object payload in Controlbox consists of two parts: a numerical `object_type` ID, and the `object_data` bytes.

### SparkController ([spark.py](./brewblox_devcon_spark/spark.py))

`SparkController` combines the functionality of `commands`, `commander`, `block_store`, and `codec` to allow interaction with the Spark using Pythonic functions.

Any command is modified both incoming and outgoing: ID's are converted using the datastore, data is sent to codec, and everything is wrapped in the correct command before it is sent to `SparkCommander`.

### Broadcaster ([broadcaster.py](./brewblox_devcon_spark/broadcaster.py))

The Spark service is not responsible for retaining any object data. Any requests are encoded and forwarded to the Spark.

To reduce the impact of this bottleneck, and to persist historic data, `Broadcaster` reads all objects every few seconds, and broadcasts their values to the eventbus.

Here, the data will likely be picked up by the [History Service](https://github.com/BrewBlox/brewblox-history).


### SparkSynchronization ([synchronization.py](./brewblox_devcon_spark/synchronization.py))

Some actions are required when connecting to a (new) Spark controller.
The SparkSynchronization feature waits for a connection to be made, and then performs these one-time tasks.

Examples are:
* Setting Spark system clock
* Reading controller-specific data from the remote datastore

## REST API

- [blocks_api.py](./brewblox_devcon_spark/api/blocks_api.py)
- [system_api.py](./brewblox_devcon_spark/api/system_api.py)
- [settings_api.py](./brewblox_devcon_spark/api/settings_api.py)
- [debug_api.py](./brewblox_devcon_spark/api/debug_api.py)
