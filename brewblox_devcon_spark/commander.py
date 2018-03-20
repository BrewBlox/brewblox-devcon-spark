"""
Command-based device communication
"""

import asyncio
import codecs
import logging
from binascii import unhexlify
from collections import defaultdict
from functools import partialmethod

from brewblox_devcon_spark import commands, communication

LOGGER = logging.getLogger(__name__)


class SparkCommander():

    def __init__(self):
        self._requests = defaultdict(asyncio.Queue)
        self._conduit = communication.SparkConduit(
            on_data=self._on_data)

    @property
    def conduit(self):
        return self._conduit

    def bind(self, *args, **kwargs):
        return self._conduit.bind(*args, **kwargs)

    def close(self):
        self._conduit.close()

    async def _on_data(self, conduit, msg: str):
        try:
            msg = msg.replace(' ', '')
            unhexed = unhexlify(msg)

            command = commands.identify(unhexed)
            raw_request = unhexed[:command.request.sizeof()]
            response = command.response.parse(unhexed)

            # Resolve the request using its encoded representation
            await self._requests[raw_request].put(response)
        except Exception as ex:
            LOGGER.error(ex)

    async def _command(self, cmd, **kwargs):
        raw_request = cmd.request.build(dict(**kwargs))
        await self._conduit.write_encoded(codecs.encode(raw_request, 'hex'))

        # Wait for a request resolution (matched by request)
        return await self._requests[raw_request].get()

    async def do(self, cmd: str, **kwargs):
        command = commands.COMMANDS[cmd.upper()]
        return await self._command(command, **kwargs)

    # TODO(Bob): automatically generate this?
    list_objects = partialmethod(_command, cmd=commands.COMMANDS['LIST_OBJECTS'], profile_id=0)
