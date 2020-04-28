"""
Launches the firmware simulator in a subprocess
"""


import subprocess
from pathlib import Path
from platform import machine

from aiohttp import web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)


class FirmwareSimulator():

    def __init__(self):
        self.proc: subprocess.Popen = None

    @property
    def arm(self) -> bool:
        return machine().startswith('arm')

    def start(self, device_id):
        self.stop()

        arch = 'arm' if self.arm else 'amd'
        workdir = Path('simulator/').resolve()
        workdir.mkdir(mode=0o777, exist_ok=True)
        workdir.joinpath('device_key.der').touch(mode=0o777, exist_ok=True)
        workdir.joinpath('server_key.der').touch(mode=0o777, exist_ok=True)
        workdir.joinpath('eeprom.bin').touch(mode=0o777, exist_ok=True)

        self.proc = subprocess.Popen([f'../binaries/brewblox-{arch}', '--device_id', device_id], cwd=workdir)
        LOGGER.info(f'Firmware simulator start ok: {self.proc.poll() is None}')

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


def get_simulator(app: web.Application) -> SimulatorFeature:
    return features.get(app, SimulatorFeature)
