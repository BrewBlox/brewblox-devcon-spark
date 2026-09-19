# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The Spark service connects a BrewPi Spark controller (USB, TCP, MQTT, or the firmware
simulator) to Brewblox: it discovers the device, encodes and decodes its protobuf
messages, exposes the blocks over HTTP and MQTT, and broadcasts state to the eventbus.
README.md covers the firmware/proto coupling and the update workflow; this file holds
what changes how an agent works here. `invoke --list` lists every task.

## Commands

The environment is uv (`uv sync`). VS Code terminals have `.venv/bin` on PATH; elsewhere
prefix commands with `uv run`.

```sh
pytest                                    # full suite: the gate, 100% branch coverage required
pytest --no-cov test/test_codec.py        # one file; without --no-cov a partial run fails on coverage
pytest --no-cov test/test_codec.py -k name
ruff format --check --diff                # what CI lints; `ruff format` fixes
ruff check                                # lint (select ALL, ignores in pyproject.toml); not enforced by CI
invoke testclean                          # remove containers and simulators left by a killed pytest
invoke download-firmware                  # binaries and simulator into firmware/ (not committed); needed by tests
docker compose up                         # the service in simulation mode with hot reload, plus its dependencies
```

Tests need Docker: pytest-docker starts the eventbus, redis, victoria, and history
services from test/docker-compose.yml once per session, and integration tests spawn the
simulator binary from firmware/. Every test has a 10s timeout (`--timeout`) that also
covers fixture setup, so on a machine without the images the first test errors while
`docker compose up` is still pulling: run `docker compose -f test/docker-compose.yml pull`
first (CI does). `asyncio.sleep` calls over 0.1s print the test name: config intervals in
the `config` fixture are milliseconds, so a long sleep in a test means a real delay
slipped through.
The `app` fixture must stay synchronous: contextvars set in async fixtures are invisible
to the test function.

## Firmware and proto coupling

- firmware.ini pins the firmware and proto commits. A controller with a different proto
  version is INCOMPATIBLE and synchronization stops (`skip_version_check` overrides); a
  different firmware version is only reported as MISMATCHED. `invoke update-firmware`
  moves both pins and recompiles; `--local` takes them from a firmware checkout instead
  (README.md).
- brewblox_devcon_spark/codec/proto-compiled/ holds the compiled `_pb2.py` files
  (committed; regenerate with `invoke compile-proto`). They import each other as top-level
  modules, so codec/pb2.py appends the directory to `sys.path` and imports every module by
  name, and `[tool.pyright]` lists it in `extraPaths`. The directory is excluded from
  ruff, coverage, and test collection.
- Adding a block type: compile-proto writes the `_pb2.py` file, but the codec lookup is
  built from the import list in codec/pb2.py, so add the import there too. Adding a unit:
  `FORMATS` in codec/unit_conversion.py must match the `UnitType` enum by name.
  test/test_codec_lookup.py asserts both, from the compiled descriptors (CI has no proto
  submodule checkout).

## Architecture

- Every feature module exposes `setup()`, which builds its singleton and stores it in a
  module-level `CV` ContextVar; consumers call `module.CV.get()`. `app_factory.create_app()`
  runs the `setup()` calls in dependency order, and `lifespan()` enters the background
  features (mqtt, datastore_settings, connection, synchronization, broadcast, time_sync,
  block_backup) in an AsyncExitStack. Config is `utils.get_config()`, an lru-cached
  `ServiceConfig` read from `BREWBLOX_SPARK_*` env vars and `.appenv` (written by
  parse_appenv.py from the container's command-line args); `utils.get_fw_config()` reads
  firmware/firmware.ini.
- Request path: endpoints/ (FastAPI routers under `/{service name}/`, and MQTT block
  commands) → spark_api.SparkApi (block CRUD by string id, translated to numeric ids
  through the in-memory bidict in datastore_blocks, filled from the controller's block
  names during synchronization) →
  command.CboxCommander (matches one request to one response, encodes through codec) →
  connection.ConnectionHandler (discovery, connect, backoff) → a ConnectionImplBase
  subclass per transport. cbox_parser splits the inbound stream into `<events>` and
  newline-terminated data.
- codec/ converts protobuf ↔ dicts: lookup maps block types to messages, processor
  handles the field options (units through Pint in unit_conversion, links, and the other
  bloxfield kinds).
- state_machine holds awaitable status events; synchronization drives them
  DISCONNECTED → CONNECTED → ACKNOWLEDGED → SYNCHRONIZED (→ UPDATING), and its module
  docstring is the reference for what happens at each step. A handshake (`!BREWBLOX`) that
  was not solicited marks a new session: buffered stream data before it is discarded.

## Git

- Commit messages carry no AI attribution trailers (no Co-Authored-By, no session links).
- PRs target `develop` in BrewBlox/brewblox-devcon-spark. CI runs `uv run pytest` against
  freshly downloaded firmware, then `ruff format --check`, then builds the images.
