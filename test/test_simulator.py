"""
Tests brewblox_devcon_spark.simulator
"""

from shutil import rmtree

import pytest

from brewblox_devcon_spark import simulator, state


@pytest.fixture
async def app(app, loop):
    app['config']['simulation'] = True
    state.setup(app)
    simulator.setup(app)
    return app


@pytest.fixture
async def managed_dir():
    yield
    rmtree('simulator/', ignore_errors=True)


async def test_sim(app, client, managed_dir):
    assert simulator.get_simulator(app).sim.proc.poll() is None
    assert state.summary(app).connection is None
    await state.set_connect(app, 'localhost:8332')
    assert state.summary(app).connection == 'simulation'
