import asyncio
from abc import abstractmethod

from brewblox_devcon_spark.models import ConnectionKind_


class ConnectionCallbacks:

    @abstractmethod
    async def on_response(self, msg: str):
        """
        Should handle calls that contain proto+B64 encoded Response objects.
        This will only be called once per response.
        If the message was chunked, B64 chunks will be separated by commas.
        """

    @abstractmethod
    async def on_event(self, msg: str):
        """
        Should handle calls that contain plaintext messages or cbox events.
        """


class ConnectionImplBase(ConnectionCallbacks):

    def __init__(self,
                 kind: ConnectionKind_,
                 address: str,
                 callbacks: ConnectionCallbacks,
                 ) -> None:
        self._kind = kind
        self._address = address
        self._callbacks = callbacks
        self._connected = asyncio.Event()
        self._disconnected = asyncio.Event()

    def __str__(self):
        return f'<{type(self).__name__} for {self._kind} {self._address}>'

    @property
    def kind(self) -> ConnectionKind_:
        return self._kind

    @property
    def address(self) -> str:
        return self._address

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    @property
    def disconnected(self) -> asyncio.Event:
        return self._disconnected

    async def on_response(self, msg: str):
        await self._callbacks.on_response(msg)

    async def on_event(self, msg: str):
        await self._callbacks.on_event(msg)

    @abstractmethod
    async def send_request(self, msg: str):
        """
        Connection-specific implementation for
        writing the encoded request to the transport layer.
        """

    @abstractmethod
    async def close(self):
        """
        Connection-specific implementation for closing the connection.
        It is not required that the `disconnected` event is set during this function.
        """
