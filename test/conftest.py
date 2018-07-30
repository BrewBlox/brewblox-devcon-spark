"""
Master file for pytest fixtures.
Any fixtures declared here are available to all test functions in this directory.
"""


import logging
from tempfile import NamedTemporaryFile

import pytest
from brewblox_service import brewblox_logger, features, service

from brewblox_devcon_spark.__main__ import create_parser

LOGGER = brewblox_logger(__name__)


@pytest.fixture(scope='session', autouse=True)
def log_enabled():
    """Sets log level to DEBUG for all test functions.
    Allows all logged messages to be captured during pytest runs"""
    logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture(autouse=True)
def test_db():
    """
    Creates a temporary database file that will be automatically removed.
    """
    f = NamedTemporaryFile(mode='w+t', encoding='utf8')
    f.write('[]')
    f.flush()
    yield f.name


@pytest.fixture
def app_config(test_db) -> dict:
    return {
        'name': 'test_app',
        'host': 'localhost',
        'port': 1234,
        'debug': True,
        'database': test_db,
        'system_database': 'config/brewblox_sys_db.json',
        'device_port': '/dev/TESTEH',
        'device_id': '1234',
        'simulation': False,
        'broadcast_interval': 5,
        'broadcast_exchange': 'brewcast',
        'unit_system_file': 'config/celsius_system.txt',
        'sync_exchange': 'syncast',
    }


@pytest.fixture
def sys_args(app_config) -> list:
    return [str(v) for v in [
        'app_name',
        '--debug',
        '--name', app_config['name'],
        '--host', app_config['host'],
        '--port', app_config['port'],
        '--database', app_config['database'],
        '--system-database', app_config['system_database'],
        '--device-port', app_config['device_port'],
        '--device-id', app_config['device_id'],
        '--broadcast-interval', app_config['broadcast_interval'],
        '--broadcast-exchange', app_config['broadcast_exchange'],
        '--unit-system-file', app_config['unit_system_file'],
        '--sync-exchange', app_config['sync_exchange'],
    ]]


@pytest.fixture
def app(sys_args):
    parser = create_parser('default')
    app = service.create_app(parser=parser, raw_args=sys_args[1:])
    return app


@pytest.fixture
def client(app, aiohttp_client, loop):
    """Allows patching the app or aiohttp_client before yielding it.

    Any tests wishing to add custom behavior to app can override the fixture
    """
    LOGGER.debug('Available features:')
    for name, impl in app.get(features.FEATURES_KEY, {}).items():
        LOGGER.debug(f'Feature "{name}" = {impl}')
    LOGGER.debug(app.on_startup)

    return loop.run_until_complete(aiohttp_client(app))
