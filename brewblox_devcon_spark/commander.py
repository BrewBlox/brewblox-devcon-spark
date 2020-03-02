"""
Command-based device communication
"""

import asyncio
import warnings
from asyncio import TimeoutError
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater, strex

from brewblox_devcon_spark import commands, communication, exceptions, state

LOGGER = brewblox_logger(__name__)

WELCOME_PREFIX = 'BREWBLOX'
UPDATER_PREFIX = 'FIRMWARE_UPDATER'
CBOX_ERR_PREFIX = 'CBOXERROR'
SETUP_MODE_PREFIX = 'SETUP_MODE'

# Spark protocol is to echo the request in the response
# To prevent decoding ambiguity, a non-hexadecimal character separates the request and response
RESPONSE_SEPARATOR = '|'

# As requests are matched on request code + arguments, they may cause bloating in the matcher
# This would happen if the same request is made often with different arguments
#
# There is no functional danger here - we just need to curb this equivalent of a memory leak
QUEUE_VALID_DURATION = timedelta(seconds=120)
CLEANUP_INTERVAL = timedelta(seconds=60)

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
REQUEST_TIMEOUT = timedelta(seconds=10)


@dataclass
class HandshakeMessage:
    name: str
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str
    system_version: str
    platform: str
    reset_reason_hex: str
    reset_data_hex: str
    device_id: str = field(default='')
    reset_reason: str = field(init=False)

    def __post_init__(self):
        self.reset_reason = commands.ResetReason(self.reset_reason_hex.upper()).name


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


class SparkCommander(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._requests = defaultdict(TimestampedQueue)
        self._conduit: communication.SparkConduit = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._conduit} at {hex(id(self))}>'

    async def startup(self, app: web.Application):
        await super().startup(app)
        self._conduit = communication.get_conduit(app)
        self._conduit.data_callbacks.add(self._on_data)
        self._conduit.event_callbacks.add(self._on_event)

    async def shutdown(self, app: web.Application):
        await super().shutdown(app)
        if self._conduit:
            self._conduit.data_callbacks.discard(self._on_data)
            self._conduit.event_callbacks.discard(self._on_event)
            self._conduit = None

    async def prepare(self):
        pass

    async def run(self):
        await asyncio.sleep(CLEANUP_INTERVAL.seconds)
        stale = [k for k, queue in self._requests.items()
                 if not queue.fresh]

        if stale:
            LOGGER.debug(f'Cleaning stale queues: {stale}')

        for key in stale:
            del self._requests[key]

    async def _on_welcome(self, msg: str):
        welcome = HandshakeMessage(*msg.split(','))
        LOGGER.info(welcome)

        device = state.DeviceInfo(
            welcome.firmware_version,
            welcome.proto_version,
            welcome.firmware_date,
            welcome.proto_date,
            welcome.device_id,
            welcome.system_version,
            welcome.platform,
            welcome.reset_reason,
        )
        await state.on_handshake(self.app, device)

    async def _on_event(self, conduit, msg: str):
        if msg.startswith(WELCOME_PREFIX):
            await self._on_welcome(msg)

        elif msg.startswith(UPDATER_PREFIX):
            LOGGER.error('Update protocol was activated by another connection.')
            await self.pause()
            await self.disconnect()

        elif msg.startswith(CBOX_ERR_PREFIX):
            try:
                LOGGER.error('Spark CBOX error: ' + commands.Errorcode(int(msg[-2:], 16)).name)
            except ValueError:
                LOGGER.error('Unknown Spark CBOX error: ' + msg)

        elif msg.startswith(SETUP_MODE_PREFIX):
            LOGGER.error('Controller entered listening mode. Exiting service now.')
            raise SystemExit(1)

        else:
            LOGGER.info(f'Spark event: "{msg}"')

    async def _on_data(self, conduit, msg: str):
        try:
            raw_request, raw_response = msg.upper().replace(' ', '').split(RESPONSE_SEPARATOR)

            # Match the request queue
            # key is the encoded request
            queue = self._requests[raw_request].queue
            await queue.put(TimestampedResponse(raw_response))

        except Exception as ex:
            LOGGER.error(f'Response error parsing message `{msg}` : {strex(ex)}')

    async def execute(self, command: commands.Command) -> dict:
        encoded_request = command.encoded_request.upper()
        ignore_pause = isinstance(command, commands.FirmwareUpdateCommand)
        await self._conduit.write(encoded_request, ignore_pause)

        while True:
            # Wait for a request resolution (matched by request)
            # Request will be resolved with a timestamped response
            queue = self._requests[encoded_request].queue

            try:
                response = await asyncio.wait_for(queue.get(), timeout=REQUEST_TIMEOUT.seconds)
            except TimeoutError:
                raise exceptions.CommandTimeout(f'{type(command).__name__}')

            if not response.fresh:
                warnings.warn(f'Discarding stale response: {response}')
                continue

            # Create a new command of the same type to contain response
            response_cmd = type(command).from_encoded(encoded_request, response.content)
            decoded = response_cmd.decoded_response

            # If the call failed, its response will be an exception
            # We can raise it here
            if isinstance(decoded, BaseException):
                raise decoded

            return decoded

    async def pause(self):
        if self._conduit:
            await self._conduit.pause()

    async def disconnect(self):
        if self._conduit:
            await self._conduit.disconnect()

    async def resume(self):
        if self._conduit:
            await self._conduit.resume()


def setup(app: web.Application):
    features.add(app, SparkCommander(app))


def get_commander(app: web.Application) -> SparkCommander:
    return features.get(app, SparkCommander)
