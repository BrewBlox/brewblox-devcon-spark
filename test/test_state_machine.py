"""
Tests brewblox_devcon_spark.state_machine
"""

import pytest

from brewblox_devcon_spark import state_machine, utils
from brewblox_devcon_spark.models import (ControllerDescription,
                                          DeviceDescription,
                                          FirmwareDescription, ResetReason)

TESTED = state_machine.__name__


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
    state = state_machine.StateMachine()
    state.set_connected('MOCK', 'Narnia')
    assert state.is_connected()
    assert not state.is_enabled()
    assert not state.is_acknowledged()
    assert not state.is_synchronized()
    assert not state.is_updating()
    assert not state.is_disconnected()
    assert await state.wait_connected()

    # Error: acknowledge description should not change after sync
    with pytest.raises(RuntimeError):
        state.set_synchronized()

    # By itself, different firmware version does not cause a warning
    desc = make_desc()
    desc.firmware.firmware_version = 'outdated'
    state.set_acknowledged(desc)
    assert state.is_acknowledged()
    assert state.desc().firmware_error == 'MISMATCHED'

    # If proto version differs, firmware is incompatible
    desc = make_desc()
    desc.firmware.proto_version = ''
    state.set_acknowledged(desc)
    assert state.is_acknowledged()
    assert state.desc().firmware_error == 'INCOMPATIBLE'

    # If device_id is set and different, identity is incompatible
    desc = make_desc()
    desc.device.device_id = '007'
    state.set_acknowledged(desc)
    assert state.is_acknowledged()
    assert state.desc().identity_error == 'INCOMPATIBLE'

    # Disconnect halfway
    state.set_disconnected()
    assert not state.is_connected()
    assert not state.is_enabled()
    assert not state.is_acknowledged()
    assert not state.is_synchronized()
    assert not state.is_updating()
    assert state.is_disconnected()
    assert await state.wait_disconnected()

    # Reconnect, re-acknowledge
    state.set_connected('MOCK', 'Narnia')
    state.set_acknowledged(make_desc())
    assert state.is_connected()
    assert state.is_acknowledged()
    assert not state.is_synchronized()
    assert not state.is_updating()
    assert not state.is_disconnected()
    assert await state.wait_acknowledged()

    # Synchronize
    state.set_synchronized()
    assert state.is_connected()
    assert state.is_acknowledged()
    assert state.is_synchronized()
    assert not state.is_updating()
    assert not state.is_disconnected()
    assert await state.wait_synchronized()

    # noop - controller may acknowledge multiple times
    state.set_acknowledged(make_desc())
    assert state.is_synchronized()

    # Set updating state.
    state.set_updating()
    assert state.is_connected()
    assert state.is_acknowledged()
    assert state.is_synchronized()
    assert state.is_updating()
    assert not state.is_disconnected()
    assert await state.wait_updating()

    # Disconnect again
    state.set_disconnected()
    assert not state.is_connected()
    assert not state.is_enabled()
    assert not state.is_acknowledged()
    assert not state.is_synchronized()
    assert not state.is_updating()
    assert state.is_disconnected()
    assert await state.wait_disconnected()


async def test_wildcard_error(client):
    config = utils.get_config()
    config.device_id = ''

    state = state_machine.StateMachine()

    # Wildcard ID in service is not a hard error
    # but does set identity_error field
    state.set_connected('MOCK', 'Narnia')
    state.set_acknowledged(make_desc())
    assert state.is_acknowledged()
    assert state.desc().identity_error == 'WILDCARD_ID'
