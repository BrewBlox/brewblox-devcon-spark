"""
Tests brewblox_devcon_spark.broadcaster
"""

from unittest.mock import AsyncMock

import pytest
from brewblox_service import repeater, scheduler

from brewblox_devcon_spark import (backup_storage, block_store, codec,
                                   commander, connection, controller,
                                   global_store, service_status, service_store,
                                   synchronization)
from brewblox_devcon_spark.models import Backup, BackupIdentity, ServiceConfig

TESTED = backup_storage.__name__


@pytest.fixture(autouse=True)
def m_backup_dir(mocker, tmp_path):
    mocker.patch(TESTED + '.BASE_BACKUP_DIR', tmp_path)


@pytest.fixture
async def setup(app):
    config = utils.get_config()
    config.backup_interval = 0.01
    config.backup_retry_interval = 0.01

    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    block_store.setup(app)
    global_store.setup(app)
    service_store.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)
    backup_storage.setup(app)

    backup_storage.fget(app)._autostart = False


@pytest.fixture
async def synchronized(app, client):
    await service_status.wait_synchronized(app)


async def test_inactive(app, client, synchronized):
    config = utils.get_config()
    config.backup_interval = -2
    config.backup_retry_interval = -1

    storage = backup_storage.BackupStorage(app)
    with pytest.raises(repeater.RepeaterCancelled):
        await storage.prepare()

    assert storage.retry_interval_s == -2
    assert not storage.enabled
    assert not storage.active


async def test_autosave(app, client, mocker, synchronized):
    storage = backup_storage.fget(app)
    await storage.prepare()
    await storage.run()

    stored = await storage.all()
    assert len(stored) == 1
    assert isinstance(stored[0], BackupIdentity)

    data = await storage.read(stored[0])
    assert isinstance(data, Backup)

    mocker.patch.object(controller.fget(app), 'make_backup', AsyncMock(side_effect=RuntimeError))
    with pytest.raises(RuntimeError):
        await storage.run()

    # Synchronized is checked before controller call
    # run() exits before the RuntimeError is raised
    service_status.set_disconnected(app)
    await service_status.wait_disconnected(app)
    await storage.run()

    # No new entries were added
    stored = await storage.all()
    assert len(stored) == 1
