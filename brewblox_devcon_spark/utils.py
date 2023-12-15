import os
import signal
import traceback
from configparser import ConfigParser
from functools import lru_cache

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
    os.kill(os.getpid(), signal.SIGINT)
