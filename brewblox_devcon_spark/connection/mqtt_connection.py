"""
MQTT-based connection to the Spark.
Messages are published to and read from the relevant topics on the eventbus.
"""


import asyncio
import logging
from contextvars import ContextVar

from .. import mqtt, utils
from .connection_impl import ConnectionCallbacks, ConnectionImplBase

HANDSHAKE_TOPIC = 'brewcast/cbox/handshake/'
LOG_TOPIC = 'brewcast/cbox/log/'
REQUEST_TOPIC = 'brewcast/cbox/req/'
RESPONSE_TOPIC = 'brewcast/cbox/resp/'

_DEVICES: ContextVar[dict[str, asyncio.Event]] = ContextVar('mqtt_connection.devices')
LOGGER = logging.getLogger(__name__)


class MqttConnection(ConnectionImplBase):

    def __init__(self,
                 device_id: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        super().__init__('MQTT', device_id, callbacks)
        self.mqtt_client = mqtt.CV.get()

        self._device_id = device_id
        self._request_topic = REQUEST_TOPIC + device_id
        self._response_topic = RESPONSE_TOPIC + device_id
        self._handshake_topic = HANDSHAKE_TOPIC + device_id
        self._log_topic = LOG_TOPIC + device_id

        self._recv_msg_id: int = 0
        self._recv_chunks: list[str]

    def _reset_recv_buffer(self, msg_id: int):
        self._recv_msg_id = msg_id
        self._recv_chunks = []

    async def _handshake_cb(self, client, topic, payload: bytes, qos, properties):
        if not payload:
            self.disconnected.set()

    async def _resp_cb(self, client, topic, payload: bytes, qos, properties):
        try:
            (msg_id, chunk_idx, chunk) = payload.decode().split(';')
            msg_id = int(msg_id)
            chunk_idx = int(chunk_idx)
        except ValueError as ex:
            LOGGER.error(f'Failed to parse MQTT payload "{payload}" with error {utils.strex(ex)}')
            self._reset_recv_buffer(0)
            return

        if msg_id != self._recv_msg_id:
            self._reset_recv_buffer(msg_id)

        if len(self._recv_chunks) != chunk_idx:
            LOGGER.error(f'Received unexpected MQTT message chunk with idx {chunk_idx}')
            self._reset_recv_buffer(0)
            return

        self._recv_chunks.append(chunk)

        # we found a message separator - message is done
        if '\n' in chunk:
            msg = ''.join(self._recv_chunks).rstrip()
            self._reset_recv_buffer(0)
            await self.on_response(msg)

    async def _log_cb(self, client, topic, payload: bytes, qos, properties):
        await self.on_event(payload.decode())

    async def send_request(self, msg: str):
        self.mqtt_client.publish(self._request_topic, msg)

    async def connect(self):
        self.mqtt_client.subscribe(self._handshake_topic)(self._handshake_cb)
        self.mqtt_client.subscribe(self._response_topic)(self._resp_cb)
        self.mqtt_client.subscribe(self._log_topic)(self._log_cb)
        self.connected.set()

    async def close(self):
        self.mqtt_client.unsubscribe(self._handshake_topic)
        self.mqtt_client.unsubscribe(self._response_topic)
        self.mqtt_client.unsubscribe(self._log_topic)
        self.disconnected.set()


async def discover_mqtt(callbacks: ConnectionCallbacks) -> ConnectionImplBase | None:
    config = utils.get_config()
    if not config.device_id:
        return None

    try:
        devices = _DEVICES.get()
        evt = devices.setdefault(config.device_id, asyncio.Event())
        await asyncio.wait_for(evt.wait(),
                               timeout=config.discovery_timeout_mqtt.total_seconds())
        conn = MqttConnection(config.device_id, callbacks)
        await conn.connect()
        return conn

    except asyncio.TimeoutError:
        return None


def setup():
    mqtt_client = mqtt.CV.get()
    devices: dict[str, asyncio.Event] = {}
    _DEVICES.set(devices)

    # We need to declare listened topics before connect
    # If we subscribe to topic/+ here, we still receive messages for topic/id

    @mqtt_client.subscribe(HANDSHAKE_TOPIC + '+')
    async def on_handshake(client, topic: str, payload: bytes, qos, properties):
        device = topic.removeprefix(HANDSHAKE_TOPIC)
        if payload:
            LOGGER.debug(f'MQTT device published: {device}')
            devices.setdefault(device, asyncio.Event()).set()
        else:
            LOGGER.debug(f'MQTT device removed: {device}')
            devices.setdefault(device, asyncio.Event()).clear()

    @mqtt_client.subscribe(LOG_TOPIC + '+')
    async def on_log(client, topic: str, payload: bytes, qos, properties):
        pass

    @mqtt_client.subscribe(REQUEST_TOPIC + '+')
    async def on_request(client, topic: str, payload: bytes, qos, properties):
        pass

    @mqtt_client.subscribe(RESPONSE_TOPIC + '+')
    async def on_response(client, topic: str, payload: bytes, qos, properties):
        pass
