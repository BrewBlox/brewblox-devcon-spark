"""
Tests brewblox_devcon_spark.simulator
"""

from shutil import rmtree

import pytest

from brewblox_devcon_spark import service_status, simulator


@pytest.fixture
async def app(app, loop):
    app['config']['simulation'] = True
    service_status.setup(app)
    simulator.setup(app)
    return app


@pytest.fixture
async def managed_dir():
    yield
    rmtree('simulator/', ignore_errors=True)


async def test_sim(app, client, managed_dir):
    assert simulator.fget(app).sim.proc.poll() is None
    assert service_status.desc(app).connection_kind is None
    service_status.set_connected(app, 'localhost:8332')
    assert service_status.desc(app).connection_kind == 'simulation'
