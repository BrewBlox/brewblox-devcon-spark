"""
MQTT-based connection to the Spark.
Messages are published to and read from the relevant topics on the eventbus.
"""


import asyncio
import logging
from contextvars import ContextVar
from datetime import timedelta

from .. import mqtt, utils
from .connection_impl import ConnectionCallbacks, ConnectionImplBase

HANDSHAKE_TOPIC = 'brewcast/cbox/handshake/'
LOG_TOPIC = 'brewcast/cbox/log/'
REQUEST_TOPIC = 'brewcast/cbox/req/'
RESPONSE_TOPIC = 'brewcast/cbox/resp/'

DISCOVERY_TIMEOUT = timedelta(seconds=3)

_DEVICES: ContextVar[dict[str, asyncio.Event]] = ContextVar('mqtt_connection.devices')
LOGGER = logging.getLogger(__name__)


class MqttConnection(ConnectionImplBase):

    def __init__(self,
                 device_id: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        super().__init__('MQTT', device_id, callbacks)
        self._mqtt_client = mqtt.CV.get()
        self._device_id = device_id

        self._request_topic = REQUEST_TOPIC + device_id
        self._response_topic = RESPONSE_TOPIC + device_id
        self._handshake_topic = HANDSHAKE_TOPIC + device_id
        self._log_topic = LOG_TOPIC + device_id

    async def _handshake_cb(self, client, topic, payload, qos, properties):
        if not payload:
            self.disconnected.set()

    async def _resp_cb(self, client, topic, payload, qos, properties):
        await self.on_response(payload)

    async def _log_cb(self, client, topic, payload, qos, properties):
        await self.on_event(payload)

    async def send_request(self, msg: str):
        self._mqtt_client.publish(self._request_topic, msg)

    async def connect(self):
        self._mqtt_client.subscribe(self._handshake_topic)(self._handshake_cb)
        self._mqtt_client.subscribe(self._response_topic)(self._resp_cb)
        self._mqtt_client.subscribe(self._log_topic)(self._log_cb)
        self.connected.set()

    async def close(self):
        self._mqtt_client.unsubscribe(self._handshake_topic)
        self._mqtt_client.unsubscribe(self._response_topic)
        self._mqtt_client.unsubscribe(self._log_topic)
        self.disconnected.set()


async def _firmware_handshake_cb(client, topic: str, payload: str, qos, properties):
    devices = _DEVICES.get()
    device = topic.removeprefix(HANDSHAKE_TOPIC)
    if payload:
        LOGGER.debug(f'MQTT device published: {device}')
        devices.setdefault(device, asyncio.Event()).set()
    else:
        LOGGER.debug(f'MQTT device removed: {device}')
        devices.setdefault(device, asyncio.Event()).clear()


async def discover_mqtt(callbacks: ConnectionCallbacks) -> ConnectionImplBase | None:
    config = utils.get_config()
    if not config.device_id:
        return None

    try:
        devices = _DEVICES.get()
        evt = devices.setdefault(config.device_id, asyncio.Event())
        await asyncio.wait_for(evt.wait(), timeout=DISCOVERY_TIMEOUT.total_seconds())
        conn = MqttConnection(config.device_id, callbacks)
        await conn.connect()
        return conn

    except asyncio.TimeoutError:
        return None


def setup():
    mqtt_client = mqtt.CV.get()
    _DEVICES.set({})

    mqtt_client.subscribe(HANDSHAKE_TOPIC + '+')(_firmware_handshake_cb)
