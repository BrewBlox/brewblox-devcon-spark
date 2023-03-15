from abc import abstractmethod, abstractproperty
from typing import Awaitable, Callable, Union


async def _dummy_cb(*args):
    pass


class BaseConnection:

    def __init__(self, address: str) -> None:
        self._address = address
        self._response_cb: Callable[[str], Awaitable[None]] = None
        self._event_cb: Callable[[str], Awaitable[None]] = None
        self._disconnect_cb: Callable[[], Awaitable[None]] = None

    @property
    def address(self) -> str:
        return self._address

    @property
    def on_response(self) -> Callable[[str], Awaitable[None]]:
        return self._response_cb or _dummy_cb

    @on_response.setter
    def on_response(self, cb: Callable[[str], Awaitable[None]]):
        self._response_cb = cb

    @property
    def on_event(self) -> Callable[[str], Awaitable[None]]:
        return self._event_cb or _dummy_cb

    @on_event.setter
    def on_event(self, cb: Callable[[str], Awaitable[None]]):
        self._event_cb = cb

    @property
    def on_disconnect(self) -> Callable[[], Awaitable[None]]:
        return self._disconnect_cb or _dummy_cb

    @on_disconnect.setter
    def on_disconnect(self, cb: Callable[[], Awaitable[None]]):
        self._disconnect_cb = cb

    @abstractproperty
    def connected(self) -> bool:
        return False

    @abstractmethod
    async def send_request(self, msg: Union[str, bytes]):
        pass

    @abstractmethod
    async def drain(self):
        pass

    @abstractmethod
    async def close(self):
        pass
