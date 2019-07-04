"""
Command-based device communication
"""

import asyncio
import warnings
from collections import defaultdict
from concurrent.futures import CancelledError, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler, strex

from brewblox_devcon_spark import commands, communication, exceptions, status

LOGGER = brewblox_logger(__name__)

WELCOME_PREFIX = 'BREWBLOX'

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
REQUEST_TIMEOUT = timedelta(seconds=60)


def setup(app: web.Application):
    features.add(app, SparkCommander(app))


def get_commander(app: web.Application):
    return features.get(app, SparkCommander)


class ResetReason(Enum):
    NONE = '00'
    UNKNOWN = '0A'
    # Hardware
    PIN_RESET = '14'
    POWER_MANAGEMENT = '1E'
    POWER_DOWN = '28'
    POWER_BROWNOUT = '32'
    WATCHDOG = '3C'
    # Software
    UPDATE = '46'
    UPDATE_ERROR = '50'
    UPDATE_TIMEOUT = '5A'
    FACTORY_RESET = '64'
    SAFE_MODE = '6E'
    DFU_MODE = '78'
    PANIC = '82'
    USER = '8C'


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
    reset_reason: str = field(init=False)

    def __post_init__(self):
        self.reset_reason = ResetReason(self.reset_reason_hex.upper()).name


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


class SparkCommander(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._requests = defaultdict(TimestampedQueue)
        self._conduit: communication.SparkConduit = None
        self._cleanup_task: asyncio.Task = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._conduit} at {hex(id(self))}>'

    async def _cleanup(self):
        while True:
            try:

                await asyncio.sleep(CLEANUP_INTERVAL.seconds)
                stale = [k for k, queue in self._requests.items()
                         if not queue.fresh]

                if stale:
                    LOGGER.debug(f'Cleaning stale queues: {stale}')

                for key in stale:
                    del self._requests[key]

            except CancelledError:
                LOGGER.debug(f'{self} cleanup task shutdown')
                break

            except Exception as ex:
                warnings.warn(f'{self} cleanup task error: {strex(ex)}')

    async def _on_welcome(self, msg: str):
        state = status.get_status(self.app)

        welcome = HandshakeMessage(*msg.split(','))
        LOGGER.info(welcome)

        app_ini = self.app['ini']
        service_proto_version = app_ini['proto_version']
        service_proto_date = app_ini['proto_date']
        service_firmware_version = app_ini['firmware_version']
        service_firmware_date = app_ini['firmware_date']

        info = [
            f'Firmware version (service): {service_firmware_version}'
            f'Firmware version (controller): {welcome.firmware_version}',
            f'Firmware date (service): {welcome.firmware_date}',
            f'Firmware date (controller): {service_firmware_date}'
            f'Protocol version (service): {service_proto_version}',
            f'Protocol version (controller): {welcome.proto_version}',
            f'Protocol date (service): {service_proto_date}',
            f'Protocol date (controller): {welcome.proto_date}',
            f'System version (controller): {welcome.system_version}',
        ]
        version_compatible = service_proto_version == welcome.proto_version
        version_latest = service_firmware_version == welcome.firmware_version

        state.info = info
        await state.on_handshake(version_compatible, version_latest)

    async def _on_event(self, conduit, msg: str):
        if msg.startswith(WELCOME_PREFIX):
            await self._on_welcome(msg)
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
            LOGGER.error(f'Response error in {self} : {ex}', exc_info=True)

    async def execute(self, command: commands.Command) -> dict:
        encoded_request = command.encoded_request.upper()
        await self._conduit.write(encoded_request)

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

    async def resume(self):
        if self._conduit:
            await self._conduit.resume()

    async def startup(self, app: web.Application):
        await self.shutdown()
        self._conduit = communication.get_conduit(app)
        self._conduit.data_callbacks.add(self._on_data)
        self._conduit.event_callbacks.add(self._on_event)
        self._cleanup_task = await scheduler.create_task(app, self._cleanup())

    async def shutdown(self, *_):
        if self._conduit:
            self._conduit.data_callbacks.discard(self._on_data)
            self._conduit.event_callbacks.discard(self._on_event)
            self._conduit = None

        await scheduler.cancel_task(self.app, self._cleanup_task)
        self._cleanup_task = None
