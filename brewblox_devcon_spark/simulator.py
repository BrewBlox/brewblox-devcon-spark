"""
Launches the firmware simulator in a subprocess
"""


import subprocess
from os import getcwd, path
from pathlib import Path

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


class FirmwareSimulator(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.proc: subprocess.Popen = None

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        workdir = path.join(getcwd(), 'simulator/')
        device_id = app['config']['device_id']

        Path(workdir).mkdir(mode=0o777, exist_ok=True)
        Path(path.join(workdir, 'device_key.der')).touch(mode=0o777, exist_ok=True)
        Path(path.join(workdir, 'server_key.der')).touch(mode=0o777, exist_ok=True)
        Path(path.join(workdir, 'eeprom.bin')).touch(mode=0o777, exist_ok=True)

        self.proc = subprocess.Popen(['../binaries/brewblox-amd', '--device_id', device_id], cwd=workdir)
        LOGGER.info(f'Firmware simulator start ok: {self.proc.poll() is None}')

    async def shutdown(self, app: web.Application):
        if self.proc:
            self.proc.terminate()
            self.proc = None


def setup(app: web.Application):
    features.add(app, FirmwareSimulator(app))


def get_simulator(app: web.Application) -> FirmwareSimulator:
    return features.get(app, FirmwareSimulator)
