"""
Tests brewblox_controller_spark.controller
"""

import pytest
from brewblox_controller_spark import controller

TESTED = controller.__name__


@pytest.fixture
async def app(app):
    """App + controller routes"""
    controller.setup(app)
    return app


async def test_all_state(app, client):
    res = await client.get('/state')
    assert res.status == 200


async def test_absent_path(app, client):
    res = await client.get('/state/country')
    assert res.status == 200
    assert (await res.json()) is None
