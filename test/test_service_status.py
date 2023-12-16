"""
Tests brewblox_devcon_spark.service_status
"""

import pytest

from brewblox_devcon_spark import service_status, utils
from brewblox_devcon_spark.models import (ControllerDescription,
                                          DeviceDescription,
                                          FirmwareDescription, ResetReason)

TESTED = service_status.__name__


def make_desc() -> ControllerDescription:
    config = utils.get_config()
    fw_config = utils.get_fw_config()

    return ControllerDescription(
        system_version='1.23',
        platform='mock',
        reset_reason=ResetReason.NONE.value,
        firmware=FirmwareDescription(
            firmware_version=fw_config.firmware_version,
            proto_version=fw_config.proto_version,
            firmware_date=fw_config.firmware_date,
            proto_date=fw_config.proto_date,
        ),
        device=DeviceDescription(
            device_id=config.device_id,
        ),
    )


async def test_state_machine():
    status = service_status.ServiceStatus()
    status.set_connected('MOCK', 'Narnia')
    assert status.is_connected()
    assert not status.is_enabled()
    assert not status.is_acknowledged()
    assert not status.is_synchronized()
    assert not status.is_updating()
    assert not status.is_disconnected()
    assert await status.wait_connected()

    # Error: acknowledge description should not change after sync
    with pytest.raises(RuntimeError):
        status.set_synchronized()

    # By itself, different firmware version does not cause a warning
    desc = make_desc()
    desc.firmware.firmware_version = 'outdated'
    status.set_acknowledged(desc)
    assert status.is_acknowledged()
    assert status.desc().firmware_error == 'MISMATCHED'

    # If proto version differs, firmware is incompatible
    desc = make_desc()
    desc.firmware.proto_version = ''
    with pytest.warns(UserWarning, match='incompatible firmware'):
        status.set_acknowledged(desc)
    assert status.is_acknowledged()
    assert status.desc().firmware_error == 'INCOMPATIBLE'

    # If device_id is set and different, identity is incompatible
    desc = make_desc()
    desc.device.device_id = '007'
    with pytest.warns(UserWarning, match='incompatible device ID'):
        status.set_acknowledged(desc)
    assert status.is_acknowledged()
    assert status.desc().identity_error == 'INCOMPATIBLE'

    # Disconnect halfway
    status.set_disconnected()
    assert not status.is_connected()
    assert not status.is_enabled()
    assert not status.is_acknowledged()
    assert not status.is_synchronized()
    assert not status.is_updating()
    assert status.is_disconnected()
    assert await status.wait_disconnected()

    # Reconnect, re-acknowledge
    status.set_connected('MOCK', 'Narnia')
    status.set_acknowledged(make_desc())
    assert status.is_connected()
    assert status.is_acknowledged()
    assert not status.is_synchronized()
    assert not status.is_updating()
    assert not status.is_disconnected()
    assert await status.wait_acknowledged()

    # Synchronize
    status.set_synchronized()
    assert status.is_connected()
    assert status.is_acknowledged()
    assert status.is_synchronized()
    assert not status.is_updating()
    assert not status.is_disconnected()
    assert await status.wait_synchronized()

    # noop - controller may acknowledge multiple times
    status.set_acknowledged(make_desc())
    assert status.is_synchronized()

    # Set updating status.
    status.set_updating()
    assert status.is_connected()
    assert status.is_acknowledged()
    assert status.is_synchronized()
    assert status.is_updating()
    assert not status.is_disconnected()
    assert await status.wait_updating()

    # Disconnect again
    status.set_disconnected()
    assert not status.is_connected()
    assert not status.is_enabled()
    assert not status.is_acknowledged()
    assert not status.is_synchronized()
    assert not status.is_updating()
    assert status.is_disconnected()
    assert await status.wait_disconnected()


async def test_wildcard_error(client):
    config = utils.get_config()
    config.device_id = ''

    status = service_status.ServiceStatus()

    # Wildcard ID in service is not a hard error
    # but does set identity_error field
    status.set_connected('MOCK', 'Narnia')
    status.set_acknowledged(make_desc())
    assert status.is_acknowledged()
    assert status.desc().identity_error == 'WILDCARD_ID'
