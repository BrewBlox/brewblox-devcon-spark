"""
MQTT-based connection to the Spark.
Messages are published to and read from the relevant topics on the eventbus.
"""


import asyncio
from typing import Optional, Union

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt

from .base_connection import BaseConnection

LOGGER = brewblox_logger(__name__)

HANDSHAKE_TOPIC = 'brewcast/cbox/handshake/'
LOG_TOPIC = 'brewcast/cbox/log/'
REQUEST_TOPIC = 'brewcast/cbox/req/'
RESPONSE_TOPIC = 'brewcast/cbox/resp/'


class MqttConnection(BaseConnection):

    def __init__(self,
                 app: web.Application,
                 device_id: str) -> None:
        super().__init__(f'mqtt/{device_id}')

        self.app = app
        self._device_id = device_id
        self._subscribed = False
        self._close_evt: asyncio.Event = None

    async def async_init(self):
        self._close_evt = asyncio.Event()

    @property
    def connected(self) -> bool:
        return not self._close_evt.is_set()

    async def _on_handshake_message(self, topic: str, msg: Optional[str]):
        if bool(msg):
            self._close_evt.clear()
        else:
            self._close_evt.set()

    async def _on_resp_message(self, topic: str, msg: str):
        await self.on_response(msg)

    async def _on_log_message(self, topic: str, msg: str):
        await self.on_event(msg)

    async def send_request(self, msg: Union[str, bytes]):
        if isinstance(msg, bytes):
            msg = msg.decode()
        await mqtt.publish(self.app, REQUEST_TOPIC + self._device_id, msg)

    async def drain(self):
        await self._close_evt.wait()

    async def subscribe(self):
        await mqtt.listen(self.app,
                          HANDSHAKE_TOPIC + self._device_id,
                          self._on_handshake_message)
        await mqtt.subscribe(self.app, HANDSHAKE_TOPIC + self._device_id)

        await mqtt.listen(self.app,
                          RESPONSE_TOPIC + self._device_id,
                          self._on_resp_message)
        await mqtt.subscribe(self.app, RESPONSE_TOPIC + self._device_id)

        await mqtt.listen(self.app,
                          LOG_TOPIC + self._device_id,
                          self._on_log_message)
        await mqtt.subscribe(self.app, LOG_TOPIC + self._device_id)

    async def close(self):
        await mqtt.unsubscribe(self.app, HANDSHAKE_TOPIC + self._device_id)
        await mqtt.unlisten(self.app,
                            HANDSHAKE_TOPIC + self._device_id,
                            self._on_handshake_message)

        await mqtt.unsubscribe(self.app, RESPONSE_TOPIC + self._device_id)
        await mqtt.unlisten(self.app,
                            RESPONSE_TOPIC + self._device_id,
                            self._on_resp_message)

        await mqtt.unsubscribe(self.app, LOG_TOPIC + self._device_id)
        await mqtt.unlisten(self.app,
                            LOG_TOPIC + self._device_id,
                            self._on_log_message)


class MqttDeviceTracker(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._devices: set[str] = []

    async def _on_handshake_message(self, topic: str, msg: Optional[str]):
        device = topic.removeprefix(HANDSHAKE_TOPIC)
        if msg:
            self._devices.add(device)
        else:
            self._devices.remove(device)

    async def startup(self, app: web.Application):
        await mqtt.listen(app,
                          HANDSHAKE_TOPIC + '*',
                          self._on_handshake_message)
        await mqtt.subscribe(app,
                             HANDSHAKE_TOPIC + '*',
                             self._on_handshake_message)

    async def before_shutdown(self, app: web.Application):
        await mqtt.unsubscribe(app, HANDSHAKE_TOPIC + '*')
        await mqtt.unlisten(app,
                            HANDSHAKE_TOPIC + '*',
                            self._on_handshake_message)

    async def discover(self) -> Optional[BaseConnection]:
        device_id = self.app['config']['device_id']
        if device_id in self._devices:
            conn = MqttConnection(self.app, device_id)
            await conn.async_init()
            await conn.subscribe()
            return conn
        return None
