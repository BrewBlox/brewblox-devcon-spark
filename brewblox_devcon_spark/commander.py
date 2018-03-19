"""
Command-based device communication
"""

# from construct.lib import hexlify
import codecs
import logging
from functools import partialmethod

from brewblox_devcon_spark import commands, communication

LOGGER = logging.getLogger(__name__)


class SparkCommander():

    def __init__(self):
        self._conduit = communication.SparkConduit()

    @property
    def conduit(self):
        return self._conduit

    def bind(self, *args, **kwargs):
        return self._conduit.bind(*args, **kwargs)

    def close(self):
        self._conduit.close()

    async def _command(self, cmd, **kwargs):
        built_cmd = cmd.build(dict(**kwargs))
        return await self._conduit.write_encoded(codecs.encode(built_cmd, 'hex'))

    list_objects = partialmethod(_command, cmd=commands.ListObjectsCommandRequest, profile_id=0)
