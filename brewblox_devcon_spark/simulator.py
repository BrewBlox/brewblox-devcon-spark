"""
Launches the firmware simulator in a subprocess
"""


import os
import subprocess

from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)


def start():  # pragma: no cover
    LOGGER.info(os.getcwd())
    subprocess.Popen(
        ['./brewblox-amd', '--device_id=123456789012345678901234'],
        cwd=f'{os.getcwd()}/binaries')
