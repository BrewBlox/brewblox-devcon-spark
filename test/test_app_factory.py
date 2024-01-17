import asyncio

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from brewblox_devcon_spark import app_factory, state_machine

TESTED = app_factory.__name__


@pytest.fixture
def app() -> FastAPI:
    return app_factory.create_app()


async def test_startup(client: AsyncClient):
    state = state_machine.CV.get()
    await asyncio.wait_for(state.wait_synchronized(), timeout=5)
    resp = await client.get('/sparkey/api/doc')
    assert resp.status_code == 200
