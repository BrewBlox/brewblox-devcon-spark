import asyncio
import socket
import traceback
from configparser import ConfigParser
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
from typing import Coroutine, Generator

from .models import FirmwareConfig, ServiceConfig


@lru_cache
def get_config() -> ServiceConfig:  # pragma: no cover
    return ServiceConfig()


@lru_cache
def get_fw_config() -> FirmwareConfig:  # pragma: no cover
    parser = ConfigParser()
    parser.read('firmware/firmware.ini')
    raw = dict(parser['FIRMWARE'].items())
    config = FirmwareConfig(**raw)
    return config


def strex(ex: Exception, tb=False):
    """
    Generic formatter for exceptions.
    A formatted traceback is included if `tb=True`.
    """
    msg = f'{type(ex).__name__}({str(ex)})'
    if tb:
        trace = ''.join(traceback.format_exception(None, ex, ex.__traceback__))
        return f'{msg}\n\n{trace}'
    else:
        return msg


def graceful_shutdown():  # pragma: no cover
    # os.kill(os.getpid(), signal.SIGINT)
    asyncio.get_running_loop().stop()


def get_free_port() -> int:
    """
    Returns the next free port that is available on the OS
    This is a bit of a hack, it does this by creating a new socket, and calling
    bind with the 0 port. The operating system will assign a brand new port,
    which we can find out using getsockname(). Once we have the new port
    information we close the socket thereby returning it to the free pool.
    This means it is technically possible for this function to return the same
    port twice (for example if run in very quick succession), however operating
    systems return a random port number in the default range (1024 - 65535),
    and it is highly unlikely for two processes to get the same port number.
    In other words, it is possible to flake, but incredibly unlikely.
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 0))
    portnum = s.getsockname()[1]
    s.close()

    return portnum


@asynccontextmanager
async def task_context(coro: Coroutine) -> Generator[asyncio.Task, None, None]:
    task = asyncio.create_task(coro)
    try:
        yield task
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
