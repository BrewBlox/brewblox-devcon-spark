from abc import abstractmethod, abstractproperty
from typing import Awaitable, Callable, Literal, Union

ConnKind_ = Literal['MOCK', 'SIM', 'USB', 'TCP', 'MQTT']


async def _dummy_cb(*args):
    pass


class ConnectionCallbacks:

    @abstractmethod
    async def on_response(self, msg: str):
        pass

    @abstractmethod
    async def on_event(self, msg: str):
        pass


class BaseConnection(ConnectionCallbacks):

    def __init__(self, kind: ConnKind_, address: str, callbacks: ConnectionCallbacks) -> None:
        self._kind = kind
        self._address = address
        self._callbacks = callbacks
        self._response_cb: Callable[[str], Awaitable[None]] = None
        self._event_cb: Callable[[str], Awaitable[None]] = None
        self._disconnect_cb: Callable[[], Awaitable[None]] = None

    def __str__(self):
        return f'<{type(self).__name__} for {self._kind} {self._address}>'

    @property
    def kind(self) -> ConnKind_:
        return self._kind

    @property
    def address(self) -> str:
        return self._address

    async def on_response(self, msg: str):
        await self._callbacks.on_response(msg)

    async def on_event(self, msg: str):
        await self._callbacks.on_event(msg)

    @abstractproperty
    def connected(self) -> Awaitable[bool]:
        pass

    @abstractproperty
    def disconnected(self) -> Awaitable[bool]:
        pass

    @abstractmethod
    async def send_request(self, msg: Union[str, bytes]):
        pass

    @abstractmethod
    async def close(self):
        pass
