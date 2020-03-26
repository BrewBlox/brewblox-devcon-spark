"""
Tests brewblox_devcon_spark.simulator
"""

import pytest

from brewblox_devcon_spark import simulator


@pytest.fixture
async def app(app, loop):
    simulator.setup(app)
    return app


async def test_sim(app, client):
    assert simulator.get_simulator(app).proc.poll() is None
