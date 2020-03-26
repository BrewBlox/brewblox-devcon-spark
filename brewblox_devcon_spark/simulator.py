"""
Launches the firmware simulator in a subprocess
"""


import os
import subprocess

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


class FirmwareSimulator(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.proc: subprocess.Popen = None

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        subprocess.check_call('touch device_key.der server_key.der eeprom.bin', shell=True)
        self.proc = subprocess.Popen(
            ['binaries/brewblox-amd', '--device_id', app['config']['device_id']],
            cwd=os.getcwd())
        LOGGER.info(f'Firmware simulator start ok: {self.proc.poll() is None}')

    async def shutdown(self, app: web.Application):
        if self.proc:
            self.proc.terminate()
            self.proc = None


def setup(app: web.Application):
    features.add(app, FirmwareSimulator(app))


def get_simulator(app: web.Application) -> FirmwareSimulator:
    return features.get(app, FirmwareSimulator)
