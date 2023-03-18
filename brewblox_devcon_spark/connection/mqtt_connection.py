"""
MQTT-based connection to the Spark.
Messages are published to and read from the relevant topics on the eventbus.
"""


import asyncio
from typing import Optional, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt

from .connection_impl import ConnectionCallbacks, ConnectionImpl

LOGGER = brewblox_logger(__name__)

HANDSHAKE_TOPIC = 'brewcast/cbox/handshake/'
LOG_TOPIC = 'brewcast/cbox/log/'
REQUEST_TOPIC = 'brewcast/cbox/req/'
RESPONSE_TOPIC = 'brewcast/cbox/resp/'

DISCOVERY_TIMEOUT_S = 3


class MqttConnection(ConnectionImpl):

    def __init__(self,
                 app: web.Application,
                 device_id: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        super().__init__('MQTT', device_id, callbacks)

        self.app = app
        self._device_id = device_id

        self._request_topic = REQUEST_TOPIC + device_id
        self._response_topic = RESPONSE_TOPIC + device_id
        self._handshake_topic = HANDSHAKE_TOPIC + device_id
        self._log_topic = LOG_TOPIC + device_id

    async def _handshake_cb(self, topic: str, msg: str):
        if not msg:
            self.disconnected.set()

    async def _resp_cb(self, topic: str, msg: str):
        await self.on_response(msg)

    async def _log_cb(self, topic: str, msg: str):
        await self.on_event(msg)

    async def send_request(self, msg: Union[str, bytes]):
        await mqtt.publish(self.app, self._request_topic, msg)

    async def connect(self):
        await mqtt.listen(self.app, self._handshake_topic, self._handshake_cb)
        await mqtt.listen(self.app, self._response_topic, self._resp_cb)
        await mqtt.listen(self.app, self._log_topic, self._log_cb)

        await mqtt.subscribe(self.app, self._handshake_topic)
        await mqtt.subscribe(self.app, self._response_topic)
        await mqtt.subscribe(self.app, self._log_topic)

        self.connected.set()

    async def close(self):
        await mqtt.unsubscribe(self.app, self._handshake_topic)
        await mqtt.unsubscribe(self.app, self._response_topic)
        await mqtt.unsubscribe(self.app, self._log_topic)

        await mqtt.unlisten(self.app, self._handshake_topic, self._handshake_cb)
        await mqtt.unlisten(self.app, self._response_topic, self._resp_cb)
        await mqtt.unlisten(self.app, self._log_topic, self._log_cb)

        self.disconnected.set()


class MqttDeviceTracker(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._isolated = app['config']['isolated']
        self._handshake_topic = HANDSHAKE_TOPIC + '+'
        self._devices: dict[str, asyncio.Event] = {}

    async def _handshake_cb(self, topic: str, msg: str):
        device = topic.removeprefix(HANDSHAKE_TOPIC)
        if msg:
            LOGGER.info(f'MQTT device published: {device}')
            self._devices.setdefault(device, asyncio.Event()).set()
        else:
            LOGGER.debug(f'MQTT device removed: {device}')
            self._devices.setdefault(device, asyncio.Event()).clear()

    async def startup(self, app: web.Application):
        if not self._isolated:
            await mqtt.listen(app, self._handshake_topic, self._handshake_cb)
            await mqtt.subscribe(app, self._handshake_topic)

    async def before_shutdown(self, app: web.Application):
        if not self._isolated:
            await mqtt.unsubscribe(app, self._handshake_topic)
            await mqtt.unlisten(app, self._handshake_topic, self._handshake_cb)

    async def discover(self, callbacks: ConnectionCallbacks) -> Optional[ConnectionImpl]:
        if self._isolated:
            return None

        try:
            device_id = self.app['config']['device_id']
            evt = self._devices.setdefault(device_id, asyncio.Event())
            await asyncio.wait_for(evt.wait(), timeout=DISCOVERY_TIMEOUT_S)
            conn = MqttConnection(self.app, device_id, callbacks)
            await conn.connect()
            return conn

        except asyncio.TimeoutError:
            return None
