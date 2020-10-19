"""
Command-based device communication.
Requests are matched with responses here.
"""

import asyncio
from typing import Dict

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

from brewblox_devcon_spark import commands, connection, exceptions

LOGGER = brewblox_logger(__name__)


# Spark protocol is to echo the request in the response
# To prevent decoding ambiguity, a non-hexadecimal character separates the request and response
RESPONSE_SEPARATOR = '|'


class SparkCommander(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._timeout = app['config']['command_timeout']
        self._requests: Dict[str, asyncio.Future] = {}
        self._conn: connection.SparkConnection = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._conn} at {hex(id(self))}>'

    async def startup(self, app: web.Application):
        self._requests.clear()
        self._conn = connection.fget(app)
        self._conn.data_callbacks.add(self.data_callback)

    async def shutdown(self, app: web.Application):
        if self._conn:
            await self._conn.shutdown(app)
            self._conn.data_callbacks.discard(self.data_callback)
            self._conn = None

    def data_callback(self, msg: str):
        try:
            raw_request, raw_response = msg.upper().replace(' ', '').split(RESPONSE_SEPARATOR)

            # Get the Future object awaiting this request
            # key is the encoded request
            fut: asyncio.Future = self._requests.get(raw_request)
            if fut is None:
                raise ValueError('Unexpected message')
            fut.set_result(raw_response)

        except Exception as ex:
            LOGGER.error(f'Error parsing message `{msg}` : {strex(ex)}')

    def add_request(self, request: str) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self._requests[request] = fut
        return fut

    def remove_request(self, request: str):
        del self._requests[request]

    async def execute(self, command: commands.Command) -> dict:
        encoded_request = command.encoded_request.upper()
        resp_future = self.add_request(encoded_request)

        try:
            await self._conn.write(encoded_request)
            message = await asyncio.wait_for(resp_future, timeout=self._timeout)

            # Create a new command of the same type to contain response
            response_cmd = type(command).from_encoded(encoded_request, message)
            decoded = response_cmd.decoded_response

            # If the call failed, its response will be an exception
            # We can raise it here
            if isinstance(decoded, BaseException):
                raise decoded

        except asyncio.CancelledError:  # pragma: no cover
            raise

        except asyncio.TimeoutError:
            raise exceptions.CommandTimeout(f'{type(command).__name__}')

        finally:
            self.remove_request(encoded_request)

        return decoded

    async def start_reconnect(self):
        if self._conn:
            await self._conn.start_reconnect()


def setup(app: web.Application):
    features.add(app, SparkCommander(app))


def fget(app: web.Application) -> SparkCommander:
    return features.get(app, SparkCommander)
