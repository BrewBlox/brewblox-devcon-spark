"""
Simulator-specific endpoints
"""

import logging

from fastapi import APIRouter, WebSocket
from httpx_ws import aconnect_ws

from .. import exceptions, state_machine, utils

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/sim', tags=['Sim'])


@router.websocket('/display')
async def sim_display_websocket(ws: WebSocket):  # pragma: no cover
    """
    Open a WebSocket to stream the simulator's display.
    Every message is a whole frame of 480 x 320 pixels, 3 bytes R, G, B each,
    in position order: the pixel at x, y is pixel y * 480 + x.
    """
    config = utils.get_config()
    state = state_machine.CV.get()

    if not config.simulation:
        raise exceptions.ConnectionImpossible('Device is not a simulation')

    await ws.accept()

    try:
        await state.wait_synchronized()

        async with aconnect_ws(
            url=f'ws://localhost:{config.simulation_display_port}/',
        ) as client_ws:
            while True:
                msg = await client_ws.receive_bytes()
                await ws.send_bytes(msg)

    except Exception as ex:
        LOGGER.error(utils.strex(ex), exc_info=config.debug)
        raise ex
