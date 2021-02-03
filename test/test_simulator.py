"""
Tests brewblox_devcon_spark.simulator
"""

from shutil import rmtree

import pytest

from brewblox_devcon_spark import service_status, simulator

TESTED = simulator.__name__


@pytest.fixture
async def app(app, loop):
    app['config']['simulation'] = True
    service_status.setup(app)
    simulator.setup(app)
    return app


@pytest.fixture
async def managed_dir():
    yield
    rmtree('simulator/', ignore_errors=True)


@pytest.fixture
def arm32_arch(mocker):
    m = mocker.patch(TESTED + '.machine')
    m.return_value = 'armv7l'
    return m


@pytest.fixture
def arm64_arch(mocker):
    m = mocker.patch(TESTED + '.machine')
    m.return_value = 'aarch64'
    return m


@pytest.fixture
def dummy_arch(mocker):
    m = mocker.patch(TESTED + '.machine')
    m.return_value = 'dummy'
    return m


async def test_sim(app, client, managed_dir):
    assert simulator.fget(app).sim.proc.poll() is None
    assert service_status.desc(app).connection_kind is None
    service_status.set_connected(app, 'localhost:8332')
    assert service_status.desc(app).connection_kind == 'simulation'


async def test_arm64(arm64_arch, app, client, managed_dir):
    # No simulator is available
    assert simulator.fget(app).sim.proc is None


async def test_arm32(arm32_arch, app, client, managed_dir):
    # Assuming AMD64 is used for development
    # Simulator will crash immediately with exec format error
    assert simulator.fget(app).sim.proc is None


async def test_dummy(dummy_arch, app, client, managed_dir):
    # Check whether unexpected archs are handled
    assert simulator.fget(app).sim.proc is None
