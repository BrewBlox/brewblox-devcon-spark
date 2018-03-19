"""
Command-based device communication
"""

# from construct.lib import hexlify
import codecs
import logging
from functools import partialmethod
from collections import defaultdict
import asyncio
from binascii import unhexlify

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

            opcode = commands.CBoxOpcodeEnum.parse(unhexed)
            command = commands.COMMANDS[opcode]
            raw_request = unhexed[:command.request.sizeof()]
            response = command.response.parse(unhexed)

            # Resolve the request using its encoded representation
            await self._requests[raw_request].put(response)
        except Exception as ex:
            LOGGER.error(ex)

    async def _command(self, cmd, **kwargs):
        built_cmd = cmd.request.build(dict(**kwargs))
        await self._conduit.write_encoded(codecs.encode(built_cmd, 'hex'))

        # Wait for a request resolution (matched by request)
        return await self._requests[built_cmd].get()

    # TODO(Bob): automatically generate this?
    list_objects = partialmethod(_command, cmd=commands.COMMANDS['LIST_OBJECTS'], profile_id=0)
