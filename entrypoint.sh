#!/bin/env bash
set -euo pipefail

python3 ./parse_appenv.py "$@" >.appenv

source ./.venv/bin/activate

exec ./.venv/bin/uvicorn \
    --host 0.0.0.0 \
    --port 5000 \
    --factory \
    brewblox_devcon_spark.app_factory:create_app
