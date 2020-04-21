"""
Tests brewblox_devcon_spark.simulator
"""

from shutil import rmtree

import pytest

from brewblox_devcon_spark import simulator


@pytest.fixture
async def app(app, loop):
    simulator.setup(app)
    return app


@pytest.fixture
async def managed_dir():
    yield
    rmtree('simulator/', ignore_errors=True)


async def test_sim(app, client, managed_dir):
    assert simulator.get_simulator(app).sim.proc.poll() is None
