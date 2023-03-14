from abc import ABC, abstractmethod, abstractproperty


class ConnectionBase(ABC):

    @abstractproperty
    def connected(self) -> bool:
        return False

    @abstractmethod
    async def send_request(self, data: str):
        pass

    @abstractmethod
    def on_response(self, cb):
        pass

    @abstractmethod
    def on_event(self, cb):
        pass

    @abstractmethod
    def on_disconnect(self, cb):
        pass

    @abstractmethod
    async def drain(self):
        pass

    @abstractmethod
    async def close(self):
        pass


class DiscoveryAbortedError(Exception):
    def __init__(self, reboot_required: bool, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reboot_required = reboot_required
