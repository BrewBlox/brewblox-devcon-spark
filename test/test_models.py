import pytest

from brewblox_devcon_spark.models import (
    CROSS_PLATFORM_RESET_REASON_DATE,
    HandshakeMessage,
    parse_reset_reason,
)

BEFORE = '2026-07-06'
CUTOFF = CROSS_PLATFORM_RESET_REASON_DATE.isoformat()


@pytest.mark.parametrize(
    'firmware_date,reset_reason_hex,expected',
    [
        # Particle firmware: native codes
        (BEFORE, '00', 'NONE'),
        (BEFORE, '14', 'PIN_RESET'),
        (BEFORE, '0A', 'UNKNOWN'),
        # Cross-platform firmware, from the cutoff date itself
        (CUTOFF, '00', 'UNKNOWN'),
        (CUTOFF, '01', 'POWER_ON'),
        (CUTOFF, '16', 'USER_REQUESTED'),
        # The firmware sends lowercase hex
        (CUTOFF, '0a', 'SDIO'),
        # Same value, different meaning: the date resolves the overlap
        (BEFORE, '0a', 'UNKNOWN'),
        # Unknown values never fail the handshake
        (BEFORE, '01', 'UNKNOWN'),
        (CUTOFF, 'ff', 'UNKNOWN'),
        (CUTOFF, 'zz', 'UNKNOWN'),
        # A date old firmware could not have produced is treated as current
        ('not-a-date', '01', 'POWER_ON'),
    ],
)
def test_parse_reset_reason(firmware_date: str, reset_reason_hex: str, expected: str):
    assert parse_reset_reason(firmware_date, reset_reason_hex) == expected


def handshake(firmware_date: str, reset_reason_hex: str) -> HandshakeMessage:
    return HandshakeMessage(
        name='BREWBLOX',
        firmware_version='ba1913ef',
        proto_version='845a4c25',
        firmware_date=firmware_date,
        proto_date=firmware_date,
        system_version='5.5.0',
        platform='esp32',
        reset_reason_hex=reset_reason_hex,
        reset_data_hex='00',
        device_id='a8032af2fda0',
    )


def test_handshake_reset_reason_by_firmware_date():
    assert handshake(BEFORE, '78').reset_reason == 'DFU_MODE'
    assert handshake(CUTOFF, '01').reset_reason == 'POWER_ON'
    assert handshake(CUTOFF, '01').reset_data == 'NOT_SPECIFIED'


def test_handshake_never_fails_on_reset_reason():
    # The old parser raised here, and the handshake was dropped
    assert handshake(CUTOFF, 'ff').reset_reason == 'UNKNOWN'
