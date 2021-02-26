"""
Launches the firmware simulator in a subprocess
"""


import subprocess
from pathlib import Path
from platform import machine

from aiohttp import web
from brewblox_service import brewblox_logger, features, strex

LOGGER = brewblox_logger(__name__)


class FirmwareSimulator():

    def __init__(self):
        self.proc: subprocess.Popen = None

    @property
    def binary(self) -> str:
        arch = machine()
        if arch == 'armv7l':
            return 'brewblox-arm'
        if arch == 'x86_64':
            return 'brewblox-amd'
        if arch == 'aarch64':
            return None  # Not yet supported
        return None

    def start(self, device_id):
        self.stop()

        if not self.binary:
            LOGGER.error(f'No simulator available for architecture {machine()}')
            return

        workdir = Path('simulator/').resolve()
        workdir.mkdir(mode=0o777, exist_ok=True)
        workdir.joinpath('device_key.der').touch(mode=0o777, exist_ok=True)
        workdir.joinpath('server_key.der').touch(mode=0o777, exist_ok=True)
        workdir.joinpath('eeprom.bin').touch(mode=0o777, exist_ok=True)

        try:
            self.proc = subprocess.Popen([f'../binaries/{self.binary}', '--device_id', device_id], cwd=workdir)
            LOGGER.info(f'Firmware simulator start ok: {self.proc.poll() is None}')
        except OSError as ex:  # pragma: no cover
            LOGGER.error(strex(ex))

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None


class SimulatorFeature(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        self.sim = FirmwareSimulator()

    async def startup(self, app: web.Application):
        self.sim.start(app['config']['device_id'])

    async def shutdown(self, app: web.Application):
        self.sim.stop()


def setup(app: web.Application):
    features.add(app, SimulatorFeature(app))


def fget(app: web.Application) -> SimulatorFeature:
    return features.get(app, SimulatorFeature)
