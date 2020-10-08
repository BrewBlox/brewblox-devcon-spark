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

        self._updating = False
        self._timeout = app['config']['command_timeout']
        self._requests: Dict[str, asyncio.Future] = {}
        self._comms: connection.SparkConnection = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._comms} at {hex(id(self))}>'

    @property
    def updating(self) -> bool:
        return self._updating

    async def startup(self, app: web.Application):
        self._requests.clear()
        self._comms = connection.fget(app)
        self._comms.data_callbacks.add(self._on_message)

    async def shutdown(self, app: web.Application):
        if self._comms:
            await self._comms.shutdown(app)
            self._comms.data_callbacks.discard(self._on_message)
            self._comms = None

    def _on_message(self, msg: str):
        try:
            raw_request, raw_response = msg.upper().replace(' ', '').split(RESPONSE_SEPARATOR)

            # Get the Future object awaiting this request
            # key is the encoded request
            fut: asyncio.Future = self._requests.get(raw_request)
            if fut is None:
                raise ValueError('Unexpected message')
            fut.set_result(raw_response)

        except Exception as ex:
            LOGGER.error(f'Response error parsing message `{msg}` : {strex(ex)}')

    async def execute(self, command: commands.Command) -> dict:
        if self.updating and not isinstance(command, commands.FirmwareUpdateCommand):
            raise exceptions.UpdateInProgress('Update is in progress')

        encoded_request = command.encoded_request.upper()
        resp_future = asyncio.get_running_loop().create_future()
        self._requests[encoded_request] = resp_future

        try:
            await self._comms.write(encoded_request)
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
            del self._requests[encoded_request]

        return decoded

    async def start_update(self, flush_period: float):
        self._updating = True
        await asyncio.sleep(max(flush_period, 0.01))
        await self.execute(commands.FirmwareUpdateCommand.from_args())
        LOGGER.info('Shutting down normal communication')
        await self.shutdown(self.app)

    async def start_reconnect(self):
        if self._comms:
            await self._comms.start_reconnect()


def setup(app: web.Application):
    features.add(app, SparkCommander(app))


def fget(app: web.Application) -> SparkCommander:
    return features.get(app, SparkCommander)
