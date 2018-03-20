"""
Command-based device communication
"""

import asyncio
import codecs
import logging
from binascii import unhexlify
from collections import defaultdict
from concurrent.futures import CancelledError
from datetime import datetime, timedelta

from brewblox_devcon_spark import commands, communication

LOGGER = logging.getLogger(__name__)

# As requests are matched on request code + arguments, they may cause bloating in the matcher
# This would happen if the same request is made often with different arguments
#
# There is no functional danger here - we just need to curb this equivalent of a memory leak
QUEUE_VALID_DURATION = timedelta(minutes=15)
CLEANUP_INTERVAL_S = 60

# There is no strict guarantee that when ClientA and ClientB make the same request at the same time,
# they get the exact response they triggered.
# We only guarantee that they get a response that matches their request + arguments.
#
# This leaves the error condition where ClientA makes a request, but never retrieves its response.
# When ClientB makes the same request an hour later, the ClientA response is still in the queue.
#
# RESPONSE_VALID_DURATION sets how long ago the response may have been received by the matcher.
# Example:
#   t=0   -> request made, and sent to controller
#   t=100 -> response received from controller, stored in queue
#   t=110 -> response retrieved from queue
#
# In this scenario, the response will only be t=10 old, as it was stored at t=100
RESPONSE_VALID_DURATION = timedelta(seconds=5)


class TimestampedQueue():

    def __init__(self):
        self._queue = asyncio.Queue()
        self._timestamp = datetime.utcnow()

    @property
    def queue(self):
        self._timestamp = datetime.utcnow()
        return self._queue

    @property
    def fresh(self):
        return self._timestamp + QUEUE_VALID_DURATION > datetime.utcnow()


class TimestampedResponse():

    def __init__(self, data):
        self._data = data
        self._timestamp = datetime.utcnow()

    def __str__(self):
        return f'{self.data} @ {self._timestamp}'

    @property
    def data(self):
        return self._data

    @property
    def fresh(self):
        return self._timestamp + RESPONSE_VALID_DURATION > datetime.utcnow()


class SparkCommander():

    def __init__(self, loop: asyncio.BaseEventLoop):
        self._loop = loop or asyncio.get_event_loop()
        self._requests = defaultdict(TimestampedQueue)
        self._cleanup_task = None
        # TODO(Bob): handle events
        self._conduit = communication.SparkConduit(
            on_data=self._on_data)

    async def bind(self, *args, **kwargs):
        self._conduit.bind(*args, **kwargs)
        self._cleanup_task = self._loop.create_task(self._cleanup())

    async def close(self):
        self._conduit.close()

        if self._cleanup_task:
            try:
                self._cleanup_task.cancel()
                await self._cleanup_task
            except CancelledError:
                pass

    async def _cleanup(self):
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_S)
            stale = [k for k, queue in self._requests.items() if not queue.fresh]
            LOGGER.info(f'Cleaning stale queues: {stale}')
            for key in stale:
                del self._requests[key]

    async def _on_data(self, conduit, msg: str):
        try:
            msg = msg.replace(' ', '')
            unhexed = unhexlify(msg)
            LOGGER.info(unhexed)

            command = commands.identify(unhexed)
            raw_request = unhexed[:command.request.sizeof()]
            response = command.response.parse(unhexed)

            # Resolve the request using its encoded representation
            queue = self._requests[raw_request].queue
            await queue.put(TimestampedResponse(response))
        except Exception as ex:
            LOGGER.error(ex)

    async def _command(self, cmd, **kwargs):
        raw_request = cmd.request.build(dict(**kwargs))
        await self._conduit.write_encoded(codecs.encode(raw_request, 'hex'))

        while cmd.response is not None:
            # Wait for a request resolution (matched by request)
            queue = self._requests[raw_request].queue
            response = await queue.get()

            if not response.fresh:
                LOGGER.warn(f'Discarding stale response: {response}')
                continue

            return response.data

    async def do(self, cmd: str, **kwargs):
        command = commands.COMMANDS[cmd.upper()]
        return await self._command(command, **kwargs)

    async def write(self, data: str):
        return await self._conduit.write(data)
