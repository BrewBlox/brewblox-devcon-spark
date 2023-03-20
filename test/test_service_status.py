"""
Tests brewblox_devcon_spark.service_status
"""

import pytest

from brewblox_devcon_spark import service_status
from brewblox_devcon_spark.models import (ControllerDescription,
                                          DeviceDescription,
                                          FirmwareDescription, ResetReason,
                                          ServiceConfig, ServiceFirmwareIni)

TESTED = service_status.__name__


def make_desc(app) -> ControllerDescription:
    config: ServiceConfig = app['config']
    ini: ServiceFirmwareIni = app['ini']

    return ControllerDescription(
        system_version='1.23',
        platform='mock',
        reset_reason=ResetReason.NONE.value,
        firmware=FirmwareDescription(
            firmware_version=ini['firmware_version'],
            proto_version=ini['proto_version'],
            firmware_date=ini['firmware_date'],
            proto_date=ini['proto_date'],
        ),
        device=DeviceDescription(
            device_id=config['device_id'],
        ),
    )


@pytest.fixture
def app(app):
    service_status.setup(app)
    return app


async def test_state_machine(app, client):
    service_status.set_connected(app, 'MOCK', 'Narnia')
    assert service_status.is_connected(app)
    assert not service_status.is_enabled(app)
    assert not service_status.is_acknowledged(app)
    assert not service_status.is_synchronized(app)
    assert not service_status.is_updating(app)
    assert not service_status.is_disconnected(app)
    assert await service_status.wait_connected(app)

    # Error: acknowledge description should not change after sync
    with pytest.raises(RuntimeError):
        service_status.set_synchronized(app)

    # By itself, different firmware version does not cause a warning
    desc = make_desc(app)
    desc.firmware.firmware_version = 'outdated'
    service_status.set_acknowledged(app, desc)
    assert service_status.is_acknowledged(app)
    assert service_status.desc(app).firmware_error == 'MISMATCHED'

    # If proto version differs, firmware is incompatible
    desc = make_desc(app)
    desc.firmware.proto_version = ''
    with pytest.warns(UserWarning, match='incompatible firmware'):
        service_status.set_acknowledged(app, desc)
    assert service_status.is_acknowledged(app)
    assert service_status.desc(app).firmware_error == 'INCOMPATIBLE'

    # If device_id is set and different, identity is incompatible
    desc = make_desc(app)
    desc.device.device_id = '007'
    with pytest.warns(UserWarning, match='incompatible device ID'):
        service_status.set_acknowledged(app, desc)
    assert service_status.is_acknowledged(app)
    assert service_status.desc(app).identity_error == 'INCOMPATIBLE'

    # Disconnect halfway
    service_status.set_disconnected(app)
    assert not service_status.is_connected(app)
    assert not service_status.is_enabled(app)
    assert not service_status.is_acknowledged(app)
    assert not service_status.is_synchronized(app)
    assert not service_status.is_updating(app)
    assert service_status.is_disconnected(app)
    assert await service_status.wait_disconnected(app)

    # Reconnect, re-acknowledge
    service_status.set_connected(app, 'MOCK', 'Narnia')
    service_status.set_acknowledged(app, make_desc(app))
    assert service_status.is_connected(app)
    assert service_status.is_acknowledged(app)
    assert not service_status.is_synchronized(app)
    assert not service_status.is_updating(app)
    assert not service_status.is_disconnected(app)
    assert await service_status.wait_acknowledged(app)

    # Synchronize
    service_status.set_synchronized(app)
    assert service_status.is_connected(app)
    assert service_status.is_acknowledged(app)
    assert service_status.is_synchronized(app)
    assert not service_status.is_updating(app)
    assert not service_status.is_disconnected(app)
    assert await service_status.wait_synchronized(app)

    # noop - controller may acknowledge multiple times
    service_status.set_acknowledged(app, make_desc(app))
    assert service_status.is_synchronized(app)

    # Set updating status.
    service_status.set_updating(app)
    assert service_status.is_connected(app)
    assert service_status.is_acknowledged(app)
    assert service_status.is_synchronized(app)
    assert service_status.is_updating(app)
    assert not service_status.is_disconnected(app)
    assert await service_status.wait_updating(app)

    # Disconnect again
    service_status.set_disconnected(app)
    assert not service_status.is_connected(app)
    assert not service_status.is_enabled(app)
    assert not service_status.is_acknowledged(app)
    assert not service_status.is_synchronized(app)
    assert not service_status.is_updating(app)
    assert service_status.is_disconnected(app)
    assert await service_status.wait_disconnected(app)


async def test_wildcard_error(app):
    service_status.fget(app).status_desc.service.device.device_id = ''

    # Wildcard ID in service is not a hard error
    # but does set identity_error field
    service_status.set_connected(app, 'MOCK', 'Narnia')
    service_status.set_acknowledged(app, make_desc(app))
    assert service_status.is_acknowledged(app)
    assert service_status.desc(app).identity_error == 'WILDCARD_ID'
