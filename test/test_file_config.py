"""
Tests brewblox_devcon_spark.file_config
"""

import asyncio
import json
from unittest.mock import mock_open

import pytest
from brewblox_service import features, scheduler

from brewblox_devcon_spark import file_config

TESTED = file_config.__name__


@pytest.fixture
def items():
    return {
        'key1': 'val',
        'nested': {
            'key': 'nestval'
        }
    }


@pytest.fixture
async def app(app, loop, mocker, items, test_cfg):
    mocker.patch(TESTED + '.open', mock_open(read_data=json.dumps(items)))
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    scheduler.setup(app)
    features.add(app, file_config.FileConfig(app, test_cfg))
    return app


@pytest.fixture
async def config(app) -> file_config.FileConfig:
    return features.get(app, file_config.FileConfig)


async def test_read_write(app, client, items, mocker, config):
    save_spy = mocker.spy(config, 'write_file')

    with config.open() as cfg:
        assert cfg == items
    assert not config._changed_event.is_set()

    with config.open() as cfg:
        cfg['nested']['key'] = 'updated'

    with config.open() as cfg:
        assert cfg['nested']['key'] == 'updated'
    assert config._changed_event.is_set()

    await asyncio.sleep(0.02)
    assert save_spy.call_count == 1


async def test_load_error(app, client, mocker):
    open_mock = mocker.patch(TESTED + '.open')

    open_mock.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        file_config.FileConfig(app, 'filey')

    # Ok if file not found
    open_mock.side_effect = FileNotFoundError
    file_config.FileConfig(app, 'filey')


async def test_write_error(app, client, config, mocker):
    save_mock = mocker.patch.object(config, 'write_file')
    save_mock.side_effect = RuntimeError

    with config.open() as cfg:
        cfg['entry'] = ''

    await asyncio.sleep(0.1)
    assert save_mock.call_count > 0
    assert config.active
