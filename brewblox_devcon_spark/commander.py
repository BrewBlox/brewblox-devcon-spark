"""
Command-based device communication
"""

import asyncio
import codecs
import logging
from binascii import unhexlify
from collections import defaultdict, namedtuple
from concurrent.futures import CancelledError
from datetime import datetime, timedelta

from brewblox_devcon_spark import commands, communication

LOGGER = logging.getLogger(__name__)
ActualCommand = namedtuple('ActualCommand', ['command', 'raw_request', 'raw_response'])

RESPONSE_SEPARATOR = '|'

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
REQUEST_TIMEOUT = timedelta(seconds=5)


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

    def __init__(self, content):
        self._content = content
        self._timestamp = datetime.utcnow()

    def __str__(self):
        return f'{self._content} @ {self._timestamp}'

    @property
    def content(self):
        return self._content

    @property
    def fresh(self):
        return self._timestamp + RESPONSE_VALID_DURATION > datetime.utcnow()


class SparkCommander():

    def __init__(self, loop: asyncio.BaseEventLoop):
        self._loop = loop or asyncio.get_event_loop()
        self._requests = defaultdict(TimestampedQueue)
        self._cleanup_task: asyncio.Task = None

        # TODO(Bob): handle events
        self._conduit = communication.SparkConduit(
            on_data=self._on_data)

    def __str__(self):
        return f'<{type(self).__name__} for {self._conduit}>'

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
            try:

                await asyncio.sleep(CLEANUP_INTERVAL_S)
                stale = [k for k, queue in self._requests.items() if not queue.fresh]

                if stale:
                    LOGGER.info(f'Cleaning stale queues: {stale}')

                for key in stale:
                    del self._requests[key]

            except CancelledError:  # pragma: no cover
                LOGGER.info(f'{self} cleanup task shutdown')
                break

            except Exception as ex:  # pragma: no cover
                LOGGER.warn(f'{self} cleanup task error: {ex}')

    async def _on_data(self, conduit, msg: str):
        try:
            LOGGER.info(f'Data message received: {msg}')
            raw_request, raw_response = [
                unhexlify(part)
                for part in msg.replace(' ', '').split(RESPONSE_SEPARATOR)]
            LOGGER.info(f'raw request={raw_request} response={raw_response}')

            converter = commands.ResponseConverter(raw_request, raw_response)

            # Match the request queue
            # key is the raw request
            # If the call failed, it is resolved with the exception
            # Otherwise the parsed response
            queue = self._requests[raw_request].queue
            content = converter.error or converter.response
            LOGGER.info(content)
            await queue.put(TimestampedResponse(content))

        except Exception as ex:
            LOGGER.error(f'On data error in {self} : {ex}')

    async def do(self, name: str, data: dict):
        converter = commands.RequestConverter(name, data)

        raw_request = converter.raw_request
        assert await self._conduit.write_encoded(codecs.encode(raw_request, 'hex'))

        while True:
            # Wait for a request resolution (matched by request)
            queue = self._requests[raw_request].queue
            response = await asyncio.wait_for(queue.get(), timeout=REQUEST_TIMEOUT.seconds)

            if not response.fresh:
                LOGGER.warn(f'Discarding stale response: {response}')
                continue

            if isinstance(response.content, Exception):
                raise response.content

            return response.content

    async def write(self, data: str):
        LOGGER.info(f'Writing {data}')
        return await self._conduit.write(data)
