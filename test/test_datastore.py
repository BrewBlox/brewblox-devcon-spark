"""
Tests brewblox_devcon_spark.datastore
"""

import asyncio

import pytest
from brewblox_service import scheduler
from mock import AsyncMock

from brewblox_devcon_spark import const, datastore

TESTED = datastore.__name__


def read_objects():
    return datastore.SYS_OBJECTS[:1] + [
        {'keys': [f'key{i}', i+const.USER_NID_START], 'data': {}}
        for i in range(10)
    ]


@pytest.fixture
def m_check(mocker):
    m = mocker.patch(TESTED + '.couchdb.check_remote', AsyncMock())
    return m


@pytest.fixture
def m_read(mocker):
    m = mocker.patch(TESTED + '.couchdb.read',
                     AsyncMock(return_value=('rev_read', read_objects())))
    return m


@pytest.fixture
def m_write(mocker):
    m = mocker.patch(TESTED + '.couchdb.write',
                     AsyncMock(return_value='rev_write'))
    return m


@pytest.fixture
def app(app, m_check, m_read, m_write, mocker):
    mocker.patch(TESTED + '.FLUSH_DELAY_S', 0.01)
    app['config']['volatile'] = False
    scheduler.setup(app)
    datastore.setup(app)
    return app


@pytest.fixture
def store(app):
    return datastore.get_block_store(app)


@pytest.fixture
def config(app):
    return datastore.get_service_store(app)


async def test_non_volatile(app, loop):
    class VolatileTester():
        def __init__(self, volatile: bool):
            self.volatile = volatile

        @datastore.non_volatile
        async def func(self, val):
            return val

    assert await VolatileTester(True).func('testey') is None
    assert await VolatileTester(False).func('testey') == 'testey'


async def test_store(app, client, store, m_read, m_write):
    assert store.active
    assert not store.volatile
    assert store.rev is None

    default_length = len(datastore.SYS_OBJECTS)
    read_length = default_length + len(read_objects()) - 1  # overlapping item is merged

    assert len(store.items()) == default_length
    await datastore.check_remote(app)
    await store.read('doc')
    assert len(store.items()) == read_length
    assert store.rev == 'rev_read'

    # Defaults were added to read objects, so those were flushed
    await asyncio.sleep(0.05)
    assert m_write.call_count == 1
    assert store.rev == 'rev_write'

    # write on add
    store['inserted', 9001] = 'val'
    await asyncio.sleep(0.05)
    assert m_write.call_count == 2
    assert len(store.items()) == read_length + 1

    # write on delete
    del store['inserted', 9001]
    assert len(store.items()) == read_length
    await asyncio.sleep(0.05)
    assert m_write.call_count == 3

    # handle read error
    m_read.side_effect = [
        RuntimeError,
        ('rev_read', read_objects())
    ]
    with pytest.warns(UserWarning, match='read error'):
        await store.read('doc')

    assert store.rev is None
    assert store.document is None
    with pytest.warns(UserWarning, match='flush error'):
        await asyncio.sleep(0.05)

    # reset to normal
    await store.read('doc')

    # continue on write error
    with pytest.warns(UserWarning, match='flush error'):
        m_write.side_effect = [
            RuntimeError,
            'rev_write',
            'rev_write',
            'rev_write',
            'rev_write',
        ]
        store['inserted2', 9002] = 'val'
        await asyncio.sleep(0.05)
    assert m_write.call_count == 5

    # write on shutdown
    store['inserted3', 9003] = 'val'
    await store.shutdown(app)
    assert m_write.call_count == 6


async def test_store_read_error(app, client, store, m_read):
    m_read.side_effect = RuntimeError

    await store.startup(app)
    with pytest.warns(UserWarning, match='read error'):
        await store.read('doc')

    # Reset store regardless of read result
    assert len(store.items()) == len(datastore.SYS_OBJECTS)


async def test_config(app, client, config, m_read, m_write):
    def vals():
        return {'k1': 1, 'k2': 2}
    m_read.return_value = ('rev_read', vals())

    assert config.active
    assert config.rev is None

    with config.open() as cfg:
        cfg['key'] = 'val'

    with config.open() as cfg:
        assert 'key' in cfg

    # values are cleared when reading
    await config.read()
    assert config.rev == 'rev_read'
    assert m_write.call_count == 0

    with config.open() as cfg:
        assert cfg == vals()
        cfg['key'] = 'val'

    await asyncio.sleep(0.05)
    assert config.rev == 'rev_write'
    assert m_write.call_count == 1

    # handle read error
    m_read.side_effect = [
        RuntimeError,
        ('rev_read', vals())
    ]
    with pytest.warns(UserWarning, match='read error'):
        await config.read()

    assert config.rev is None
    assert config.document is None

    with config.open() as cfg:
        assert cfg == {}
        cfg['key'] = 'val'

    with pytest.warns(UserWarning, match='flush error'):
        await asyncio.sleep(0.05)

    # reset to normal
    await config.read()

    # continue on write error
    with pytest.warns(UserWarning, match='flush error'):
        m_write.side_effect = [
            RuntimeError,
            'rev_write',
            'rev_write'
        ]
        with config.open() as cfg:
            cfg['insert'] = 'outsert'
        await asyncio.sleep(0.05)
    assert m_write.call_count == 3
