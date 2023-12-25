import asyncio
import logging
import re
import socket
import traceback
from configparser import ConfigParser
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from functools import lru_cache
from ipaddress import ip_address
from typing import Awaitable, Callable, Coroutine, Generator

from dns.exception import DNSException
from dns.resolver import Resolver as DNSResolver
from httpx import Response

from .models import FirmwareConfig, ServiceConfig

LOGGER = logging.getLogger(__name__)


@lru_cache
def get_config() -> ServiceConfig:  # pragma: no cover
    config = ServiceConfig()

    if not config.device_id and (config.simulation or config.mock):
        config.device_id = '123456789012345678901234'

    if not config.name:
        config.name = autodetect_service_name()

    return config


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


def autodetect_service_name() -> str:  # pragma: no cover
    """
    Automatically detects the Docker Compose service name of the running
    container.

    Compose bridge networks implement DNS resolution to resolve the service name
    to the IP address of one of the containers for the service.
    By default, the generated container names for Compose services include the
    service name.
    Typically, this is formatted as `{project_name}-{service_name}-{container_num}`.
    If we resolve the container IP address to its container name,
    we can extract the service name from this known format.
    """
    resolver = DNSResolver()
    ip = str(ip_address(socket.gethostbyname(socket.gethostname())))
    answer = resolver.resolve_address(ip)
    host = str(answer[0]).split('.')[0]

    # We can first apply a basic sanity check: does the hostname match the format?
    match = re.fullmatch(r'.+[_-].+([_-])\d+', host)
    if not match:
        raise ValueError('Failed to autodetect service name. ' +
                         f'"{host}" is not formatted as a Compose container name.')

    # We need to identify the separactor character.
    # Depending on the Compose version, the separator character is either _ or -.
    # We know that the service name is always postfixed with a separator.
    # The last found _ or - must then be the separator.
    compose_name_sep = match[1]

    # Separating project name and service name is harder.
    # Both the service and the project may include the separator character.
    # For example, if the container name is `first_second_third_1`,
    # we don't know if this is service `third` in project `first_second`,
    # or service `second_third` in project `first`.
    #
    # The solution is to query all options
    # until we get a result matching the known IP address for this host.
    sections = host.split(compose_name_sep)[1:-1]
    candidates = [compose_name_sep.join(sections[i:]) for i in range(len(sections))]

    for c in candidates:
        with suppress(DNSException):
            answer = resolver.resolve(c, 'A')
            if ip in [str(r) for r in answer]:
                return c

    raise RuntimeError(f'No service name found for {host=}, {ip=}, {candidates=}')


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
        await asyncio.wait([task], timeout=5)


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
            LOGGER.warning(f'Retrying after failed request: {resp}')

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

    if hasattr(logging, level_name) and getattr(logging, level_name) == level_num:
        # Already set, no need to replicate
        return

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
