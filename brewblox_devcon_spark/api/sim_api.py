"""
Simulator-specific endpoints
"""

import logging

from fastapi import APIRouter, WebSocket
from httpx_ws import aconnect_ws

from .. import state_machine, utils

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

    async with utils.task_context(listen()):
        try:
            await state_machine.CV.get().wait_synchronized()

            async with aconnect_ws(f'ws://localhost:{config.simulation_display_port}') as client_ws:
                while True:
                    msg = await client_ws.receive_bytes()
                    await ws.send_bytes(msg)

        except Exception as ex:
            LOGGER.error(utils.strex(ex), exc_info=config.debug)
