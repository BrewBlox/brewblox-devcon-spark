"""
Simulator-specific endpoints
"""

import asyncio
import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket
from httpx_ws import aconnect_ws

from .. import service_status, utils

SPARK_WS_ADDR = 'ws://localhost:7377/'

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/sim', tags=['Sim'])


@router.websocket('/display')
async def sim_display_websocket(ws: WebSocket):
    """
    Open a WebSocket to stream display buffer updates.
    The full buffer will be sent in the initial push,
    and subsequent updates will only include changed areas.
    """

    async def listen():
        while True:
            await ws.receive_text()

    config = utils.get_config()
    await ws.accept()
    listen_task = asyncio.create_task(listen())

    try:
        await service_status.CV.get().wait_synchronized()

        async with aconnect_ws(SPARK_WS_ADDR) as client_ws:
            while True:
                msg = await client_ws.receive_bytes()
                await ws.send_bytes(msg)

    except Exception as ex:
        LOGGER.error(utils.strex(ex), exc_info=config.debug)

    finally:
        listen_task.cancel()
        with suppress(asyncio.CancelledError):
            await listen_task
