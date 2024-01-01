"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""

import asyncio
import logging
from datetime import timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import Mock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pytest_docker.plugin import Services as DockerServices

from brewblox_devcon_spark import app_factory, utils
from brewblox_devcon_spark.models import Block, FirmwareConfig, ServiceConfig

LOGGER = logging.getLogger(__name__)


class TestConfig(ServiceConfig):
    """
    An override for ServiceConfig that only uses
    settings provided to __init__()

    This makes tests independent from env values
    and the content of .appenv
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


@pytest.fixture(scope='session')
def docker_compose_file():
    return Path('./test/docker-compose.yml').resolve()


@pytest.fixture(autouse=True)
def config(monkeypatch: pytest.MonkeyPatch,
           docker_services: DockerServices,
           tmp_path: Path,
           ) -> Generator[ServiceConfig, None, None]:
    cfg = TestConfig(
        name='sparkey',
        debug=True,
        trace=True,
        mqtt_host='localhost',
        mqtt_port=docker_services.port_for('eventbus', 1883),
        http_client_interval=timedelta(milliseconds=100),
        datastore_host='localhost',
        datastore_port=docker_services.port_for('history', 5000),
        mock=True,
        simulation=True,
        simulation_workdir=tmp_path / 'simulator',
        simulation_port=utils.get_free_port(),
        simulation_display_port=utils.get_free_port(),
        device_id='1234',
        connect_interval=timedelta(milliseconds=10),
        connect_interval_max=timedelta(milliseconds=100),
        discovery_interval=timedelta(milliseconds=10),
        discovery_timeout=timedelta(seconds=10),
        handshake_timeout=timedelta(seconds=20),
        handshake_ping_interval=timedelta(milliseconds=20),
        backup_root_dir=tmp_path / 'backup',
    )
    print(cfg)
    monkeypatch.setattr(utils, 'get_config', lambda: cfg)
    yield cfg


@pytest.fixture(autouse=True)
def fw_config(monkeypatch: pytest.MonkeyPatch,
              ) -> Generator[FirmwareConfig, None, None]:
    cfg = FirmwareConfig(
        firmware_version='f27f141c',
        firmware_date='2023-12-06',
        firmware_sha='f27f141cb66c348afb6735ed08a60d1814791b71',
        proto_version='0fa3f6b2',
        proto_date='2023-12-06',
        system_version='3.2.0',
    )
    monkeypatch.setattr(utils, 'get_fw_config', lambda: cfg)
    yield cfg


@pytest.fixture(autouse=True)
def setup_logging(config: ServiceConfig):
    app_factory.setup_logging(True, True)


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    # caplog must be explicitly set to the desired level
    # https://stackoverflow.com/questions/59875983/why-is-caplog-text-empty-even-though-the-function-im-testing-is-logging
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture(autouse=True)
def m_kill(monkeypatch: pytest.MonkeyPatch) -> Generator[Mock, None, None]:
    m = Mock(spec=utils.os.kill)
    monkeypatch.setattr(utils.os, 'kill', m)
    yield m


@pytest.fixture(autouse=True)
def m_sleep(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """
    Allows keeping track of calls to asyncio sleep.
    For tests, we want to reduce all sleep durations.
    Set a breakpoint in the wrapper to track all calls.
    """
    real_func = asyncio.sleep

    async def wrapper(delay: float, *args, **kwargs):
        if delay > 0:
            print(f'asyncio.sleep({delay}) in {request.node.name}')
        return await real_func(delay, *args, **kwargs)
    monkeypatch.setattr('asyncio.sleep', wrapper)
    yield


@pytest.fixture
def app() -> FastAPI:
    """
    Override this in test modules to bootstrap required dependencies.

    IMPORTANT: This must NOT be an async fixture.
    Contextvars assigned in async fixtures are invisible to test functions.
    """
    app = FastAPI()
    return app


@pytest.fixture
async def manager(app: FastAPI) -> Generator[LifespanManager, None, None]:
    """
    AsyncClient does not automatically send ASGI lifespan events to the app
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html

    For testing, this ensures that lifespan() functions are handled.
    If you don't need to make HTTP requests, you can use the manager
    without the `client` fixture.
    """
    async with LifespanManager(app) as mgr:
        yield mgr


@pytest.fixture
async def client(manager: LifespanManager) -> Generator[AsyncClient, None, None]:
    async with AsyncClient(app=manager.app, base_url='http://test') as ac:
        yield ac


@pytest.fixture
def spark_blocks() -> list[Block]:
    return [
        Block(
            id='balancer-1',
            nid=200,
            type='Balancer',
            data={}
        ),
        Block(
            id='mutex-1',
            nid=300,
            type='Mutex',
            data={
                'differentActuatorWait': 43
            }
        ),
        Block(
            id='profile-1',
            nid=201,
            type='SetpointProfile',
            data={
                'points': [
                    {
                        'time': 1540376829,
                        'temperature[degC]': 0
                    },
                    {
                        'time': 1540376839,
                        'temperature[degC]': 50
                    },
                    {
                        'time': 1540376849,
                        'temperature[degC]': 100
                    }
                ],
                'targetId<>': 'setpoint-sensor-pair-2'
            }
        ),
        Block(
            id='sensor-1',
            nid=202,
            type='TempSensorMock',
            data={
                'value[celsius]': 20.89789201,
                'connected': True
            }
        ),
        Block(
            id='sensor-onewire-1',
            nid=203,
            type='TempSensorOneWire',
            data={
                'value[celsius]': 20.89789201,
                'offset[delta_degC]': 9,
                'address': 'DEADBEEF'
            }
        ),
        Block(
            id='setpoint-sensor-pair-1',
            nid=204,
            type='SetpointSensorPair',
            data={
                'sensorId<>': 'sensor-1',
                'setting': 0,
                'value': 0,
                'enabled': True,
                'filter': 1,  # FILTER_15s
                'filterThreshold': 2
            }
        ),
        Block(
            id='setpoint-sensor-pair-2',
            nid=205,
            type='SetpointSensorPair',
            data={
                'sensorId<>': 0,
                'setting': 0,
                'value': 0,
                'enabled': True
            }
        ),
        Block(
            id='actuator-1',
            nid=206,
            type='ActuatorAnalogMock',
            data={
                'setting': 20,
                'minSetting': 10,
                'maxSetting': 30,
                'value': 50,
                'minValue': 40,
                'maxValue': 60
            }
        ),
        Block(
            id='actuator-pwm-1',
            nid=207,
            type='ActuatorPwm',
            data={
                'constrainedBy': {
                    'constraints': [
                        {
                            'min': 5
                        },
                        {
                            'max': 50
                        },
                        {
                            'balanced': {
                                'balancerId<>': 'balancer-1'
                            }
                        }
                    ]
                },
                'period': 4000,
                'actuatorId<>': 'actuator-digital-1'
            }
        ),
        Block(
            id='actuator-digital-1',
            nid=208,
            type='DigitalActuator',
            data={
                'channel': 1,
                'constrainedBy': {
                    'constraints': [
                        {
                            'mutex<>': 'mutex-1'
                        },
                        {
                            'mutexed': {
                                'mutexId<>': 'mutex-1',
                                'extraHoldTime[s]': 5,
                                'hasCustomHoldTime': True,
                            },
                            'limiting': True,
                        }
                    ]
                }
            }
        ),
        Block(
            id='offset-1',
            nid=209,
            type='ActuatorOffset',
            data={
                'targetId<>': 'setpoint-sensor-pair-1',
                'referenceId<>': 'setpoint-sensor-pair-1'
            }
        ),
        Block(
            id='pid-1',
            nid=210,
            type='Pid',
            data={
                'inputId<>': 'setpoint-sensor-pair-1',
                'outputId<>': 'actuator-pwm-1',
                'enabled': True,
                'active': True,
                'kp': 20,
                'ti': 3600,
                'td': 60
            }
        ),
        Block(
            id='DisplaySettings',
            nid=7,
            type='DisplaySettings',
            data={
                'widgets': [
                    {
                        'pos': 1,
                        'color': '0088aa',
                        'name': 'pwm1',
                        'actuatorAnalog<>': 'actuator-pwm-1'
                    },
                    {
                        'pos': 2,
                        'color': '00aa88',
                        'name': 'pair1',
                        'setpointSensorPair<>': 'setpoint-sensor-pair-1'
                    },
                    {
                        'pos': 3,
                        'color': 'aa0088',
                        'name': 'sensor1',
                        'tempSensor<>': 'sensor-1'
                    },
                    {
                        'pos': 4,
                        'color': 'aa8800',
                        'name': 'pid',
                        'pid<>': 'pid-1'
                    }
                ],
                'name': 'test'
            }
        ),
        Block(
            id='ds2413-hw-1',
            nid=211,
            type='DS2413',
            data={
                'address': '4444444444444444'
            }
        ),
        Block(
            id='ow-act',
            nid=212,
            type='DigitalActuator',
            data={
                'channel': 1,
                'invert': True,
                'hwDevice<DS2413>': 'ds2413-hw-1'
            }
        )
    ]
