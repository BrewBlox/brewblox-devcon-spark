import asyncio
import logging
import socket
import traceback
from configparser import ConfigParser
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from functools import lru_cache
from typing import Awaitable, Callable, Coroutine, Generator

from httpx import Response

from .models import FirmwareConfig, ServiceConfig

LOGGER = logging.getLogger(__name__)


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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', 0))
        portnum = s.getsockname()[1]

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


async def httpx_retry(func: Callable[[], Awaitable[Response]],
                      interval: timedelta = timedelta(seconds=1),
                      max_interval: timedelta = timedelta(minutes=1),
                      backoff: float = 1.1) -> Response:
    while True:
        resp = None

        try:
            resp = await func()
            if resp.is_success:
                return resp
        except Exception as ex:
            LOGGER.debug(strex(ex), exc_info=True)

        if interval.total_seconds() > 10:
            LOGGER.warn(f'Retrying after failed request: {resp}')

        await asyncio.sleep(interval.total_seconds())
        interval = min(interval * backoff, max_interval)


def add_logging_level(level_name: str, level_num: int, method_name: str | None = None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `level_name` becomes an attribute of the `logging` module with the value
    `level_num`. `method_name` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `method_name` is not specified, `level_name.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> add_logging_level('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    Source (2023/12/11):
    https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility
    """
    if not method_name:
        method_name = level_name.lower()

    if hasattr(logging, level_name):
        raise AttributeError(f'{level_name} already defined in logging module')
    if hasattr(logging, method_name):
        raise AttributeError(f'{method_name} already defined in logging module')
    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError(f'{method_name} already defined in logger class')

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def log_for_level(self: logging.Logger, message, *args, **kwargs):
        if self.isEnabledFor(level_num):
            self._log(level_num, message, args, **kwargs)

    def log_to_root(message, *args, **kwargs):
        logging.log(level_num, message, *args, **kwargs)

    logging.addLevelName(level_num, level_name)
    setattr(logging, level_name, level_num)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)
