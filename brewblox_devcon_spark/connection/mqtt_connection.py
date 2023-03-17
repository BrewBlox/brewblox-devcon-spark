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

DISCOVERY_DELAY_S = 0.5


class MqttConnection(ConnectionImpl):

    def __init__(self,
                 app: web.Application,
                 device_id: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        super().__init__('MQTT', device_id, callbacks)

        self.app = app
        self._device_id = device_id

    async def _on_handshake_message(self, topic: str, msg: str):
        if not msg:
            self.disconnected.set()

    async def _on_resp_message(self, topic: str, msg: str):
        await self.on_response(msg)

    async def _on_log_message(self, topic: str, msg: str):
        await self.on_event(msg)

    async def send_request(self, msg: Union[str, bytes]):
        if isinstance(msg, bytes):
            msg = msg.decode()
        await mqtt.publish(self.app, REQUEST_TOPIC + self._device_id, msg)

    async def connect(self):
        await mqtt.listen(self.app,
                          HANDSHAKE_TOPIC + self._device_id,
                          self._on_handshake_message)
        await mqtt.listen(self.app,
                          RESPONSE_TOPIC + self._device_id,
                          self._on_resp_message)
        await mqtt.listen(self.app,
                          LOG_TOPIC + self._device_id,
                          self._on_log_message)

        await mqtt.subscribe(self.app, HANDSHAKE_TOPIC + self._device_id)
        await mqtt.subscribe(self.app, RESPONSE_TOPIC + self._device_id)
        await mqtt.subscribe(self.app, LOG_TOPIC + self._device_id)

        self.connected.set()

    async def close(self):
        await mqtt.unsubscribe(self.app, HANDSHAKE_TOPIC + self._device_id)
        await mqtt.unsubscribe(self.app, RESPONSE_TOPIC + self._device_id)
        await mqtt.unsubscribe(self.app, LOG_TOPIC + self._device_id)

        await mqtt.unlisten(self.app,
                            HANDSHAKE_TOPIC + self._device_id,
                            self._on_handshake_message)
        await mqtt.unlisten(self.app,
                            RESPONSE_TOPIC + self._device_id,
                            self._on_resp_message)
        await mqtt.unlisten(self.app,
                            LOG_TOPIC + self._device_id,
                            self._on_log_message)

        self.disconnected.set()


class MqttDeviceTracker(features.ServiceFeature):
    def __init__(self, app: web.Application):
        super().__init__(app)
        self._devices: set[str] = set()
        self._volatile = app['config']['volatile']

    async def _on_handshake_message(self, topic: str, msg: str):
        device = topic.removeprefix(HANDSHAKE_TOPIC)
        if msg:
            LOGGER.info(f'MQTT device published: {device}')
            self._devices.add(device)
        else:
            LOGGER.debug(f'MQTT device removed: {device}')
            self._devices.remove(device)

    async def startup(self, app: web.Application):
        if not self._volatile:
            await mqtt.listen(app,
                              HANDSHAKE_TOPIC + '+',
                              self._on_handshake_message)
            await mqtt.subscribe(app, HANDSHAKE_TOPIC + '+')

    async def before_shutdown(self, app: web.Application):
        if not self._volatile:
            await mqtt.unsubscribe(app, HANDSHAKE_TOPIC + '+')
            await mqtt.unlisten(app,
                                HANDSHAKE_TOPIC + '+',
                                self._on_handshake_message)

    async def discover(self, callbacks: ConnectionCallbacks) -> Optional[ConnectionImpl]:
        await asyncio.sleep(DISCOVERY_DELAY_S)

        device_id = self.app['config']['device_id']
        if device_id in self._devices:
            conn = MqttConnection(self.app, device_id, callbacks)
            await conn.connect()
            return conn

        return None
