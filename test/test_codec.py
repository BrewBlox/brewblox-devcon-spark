import importlib
import json
from base64 import b64decode, b64encode
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from brewblox_devcon_spark import codec, exceptions
from brewblox_devcon_spark.codec import Codec, NeedFullRead, descriptors, lookup, pb2
from brewblox_devcon_spark.models import (
    DecodedPayload,
    EncodedPayload,
    ErrorCode,
    IntermediateRequest,
    IntermediateResponse,
    Opcode,
    ReadMode,
)
from test.fixtures.messages import add_zero_members, populate

TEMP_SENSOR_TYPE_INT = 302
GOLDEN = json.loads((Path(__file__).parent / 'fixtures' / 'logged_golden.json').read_text())

ActuatorLogic = pb2.ActuatorLogic_pb2
Balancer = pb2.Balancer_pb2
# pb2.py puts proto-compiled/ on sys.path: not every module is imported there
Constraints = importlib.import_module('Constraints_pb2')
DigitalActuator = pb2.DigitalActuator_pb2
GpioModule = pb2.GpioModule_pb2
Pid = pb2.Pid_pb2
Sequence = pb2.Sequence_pb2
Spark3Pins = pb2.Spark3Pins_pb2
SysInfo = pb2.SysInfo_pb2
TempSensorCombi = pb2.TempSensorCombi_pb2


@pytest.fixture(autouse=True)
def app() -> FastAPI:
    codec.setup()
    return FastAPI()


def encoded(message: Message) -> EncodedPayload:
    impl = next(v for v in lookup.CV_OBJECTS.get() if v.message_cls is type(message))
    return EncodedPayload(
        blockId=100,
        blockType=impl.type_int,
        content=b64encode(message.SerializeToString()).decode(),
    )


def decode(message: Message, mode: ReadMode = ReadMode.DEFAULT) -> dict:
    payload = codec.CV.get().decode_payload(encoded(message), mode=mode)
    assert payload.blockType != 'ErrorObject', payload.content
    return payload.content


def parsed(payload: EncodedPayload, cls: type[Message]) -> Message:
    message = cls()
    message.ParseFromString(b64decode(payload.content))
    return message


def _copy_covered(src: Message, dst: Message):
    for key, node in descriptors.coverage(src.DESCRIPTOR).items():
        field = node.field
        if field.label == FieldDescriptor.LABEL_REPEATED:
            getattr(dst, key).extend(getattr(src, key))
        elif not field.has_presence:
            setattr(dst, key, getattr(src, key))
        elif not src.HasField(key):
            continue
        elif node.children is not None:
            _copy_covered(getattr(src, key), getattr(dst, key))
        elif field.message_type:
            getattr(dst, key).CopyFrom(getattr(src, key))
        else:
            setattr(dst, key, getattr(src, key))


def changed(full: Message, *written: str) -> Message:
    """
    The CHANGED read of a block in state `full`, as the firmware sends it:
    the covered fields (complete list elements included),
    and the firmware-written stored fields named in `written`.
    """
    out = type(full)()
    _copy_covered(full, out)
    for key in written:
        if full.DESCRIPTOR.fields_by_name[key].message_type:
            getattr(out, key).CopyFrom(getattr(full, key))
        else:
            setattr(out, key, getattr(full, key))
    return out


def assert_merges(t0: Message, t1: Message, *written: str):
    """merge(DEFAULT(t0), CHANGED(t1)) == DEFAULT(t1)"""
    cdc = codec.CV.get()
    block_type = encoded(t0).blockType
    block_type = lookup.BlockType.Name(block_type)

    cached = decode(t0)
    expected = decode(t1)
    partial = decode(changed(t1, *written), ReadMode.CHANGED)

    assert cdc.merge_changed(block_type, cached, partial) == (decode(t0) != expected)
    assert cached == expected
    assert cdc.merge_changed(block_type, cached, partial) is False


async def test_encode_system_objects():
    cdc = codec.CV.get()

    types = [
        'SysInfo',
        'DisplaySettings',
    ]

    encoded = [
        cdc.encode_payload(
            DecodedPayload(
                blockId=1,
                blockType=t,
                content={},
            )
        )
        for t in types
    ]

    assert encoded


async def test_transcode_commands():
    cdc = codec.CV.get()

    request = IntermediateRequest(
        msgId=1,
        opcode=Opcode.BLOCK_READ_ALL,
        mode=ReadMode.CHANGED,
        payload=EncodedPayload(blockId=100, blockType='TempSensorOneWire', name='sensor', content='CAE='),
    )
    assert cdc.decode_request(cdc.encode_request(request)) == request

    response = IntermediateResponse(
        msgId=1,
        error=ErrorCode.OK,
        mode=ReadMode.CHANGED,
        payload=[EncodedPayload(blockId=100, blockType='TempSensorOneWire', name='sensor', content='CAE=')],
    )
    assert cdc.decode_response(cdc.encode_response(response)) == response

    # Identity-only payloads are not encoded
    payload = cdc.encode_payload(DecodedPayload(blockId=100, name='sensor'))
    assert payload == EncodedPayload(blockId=100, name='sensor')


async def test_encode_errors():
    cdc = codec.CV.get()

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_request({})

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_response({})

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_payload(DecodedPayload(blockId=1, blockType='MAGIC'))

    # TouchSettings only exist as deprecated BlockType name,
    # and no longer has an associated message
    with pytest.raises(exceptions.EncodeException):
        cdc.encode_payload(
            DecodedPayload(
                blockId=1,
                blockType='TouchSettings',
                content={},
            )
        )

    with pytest.raises(exceptions.EncodeException):
        cdc.encode_payload(
            DecodedPayload(blockId=1, blockType='TempSensorOneWire', content={'Galileo': 'thunderbolts and lightning'})
        )


async def test_decode_errors():
    cdc = codec.CV.get()

    with pytest.raises(exceptions.DecodeException):
        cdc.decode_request('Is this just fantasy?')

    with pytest.raises(exceptions.DecodeException):
        cdc.decode_response('Caught in a landslide')

    error_object = cdc.decode_payload(
        EncodedPayload(
            blockId=1,
            blockType=TEMP_SENSOR_TYPE_INT,
            content='Galileo, Figaro - magnificoo',
        )
    )
    assert error_object.blockType == 'ErrorObject'
    assert error_object.content['error']

    error_object = cdc.decode_payload(
        EncodedPayload(
            blockId=1,
            blockType=1e6,
        )
    )
    assert error_object.blockType == 'UnknownType'


async def test_deprecated_object():
    cdc = codec.CV.get()

    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='Deprecated',
            content={'bytes': 'ZAA='},
        )
    )
    assert payload.blockType == 65533
    assert payload.content == 'ZAA='

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'Deprecated'
    assert payload.content == {'bytes': 'ZAA='}


async def test_encode_constraint():
    cdc = codec.CV.get()

    assert cdc.decode_payload(
        EncodedPayload(
            blockId=1,
            blockType='ActuatorPwm',
            content='\x00',
        )
    )
    assert cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='ActuatorPwm',
            content={
                'constrainedBy': {
                    'constraints': [
                        {'min': -100},
                        {'max': 100},
                    ],
                },
            },
        )
    )


async def test_encode_delta_sec():
    cdc = codec.CV.get()

    # Check whether [delta_temperature / time] can be converted
    payload = cdc.encode_payload(DecodedPayload(blockId=1, blockType='EdgeCase', content={'deltaV': 100}))
    payload = cdc.decode_payload(payload, filter_values=False)
    assert payload.content['deltaV']['value'] == pytest.approx(100, 0.1)
    assert payload.content['deltaV']['unit'] == 'delta_degC / second'


async def test_encode_submessage():
    cdc = codec.CV.get()

    payload = cdc.encode_payload(DecodedPayload(blockId=1, blockType='EdgeCase', content={}))
    assert payload.blockType == 9001

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'EdgeCase'

    # Interface encoding
    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='EdgeCase',
        )
    )
    assert payload.blockType == 9001

    payload = cdc.decode_payload(payload)
    assert payload.blockType == 'EdgeCase'


async def test_transcode_interfaces():
    cdc = codec.CV.get()

    for type in [
        'EdgeCase',
        'BalancerInterface',
        'SetpointSensorPair',
        'SetpointSensorPairInterface',
    ]:
        payload = cdc.encode_payload(
            DecodedPayload(
                blockId=1,
                blockType=type,
            )
        )
        payload = cdc.decode_payload(payload)
        assert payload.blockType == type


async def test_postfixed_encoding():
    cdc = codec.CV.get()

    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='EdgeCase',
            content={'link<ActuatorAnalogInterface>': 10, 'state': {'value[degF]': 50}},
        )
    )
    payload = cdc.decode_payload(payload, filter_values=False)
    assert payload.content['link'] == {'__bloxtype': 'Link', 'type': 'ActuatorAnalogInterface', 'id': 10}
    assert payload.content['state']['value']['value'] == pytest.approx(10, 0.01)
    assert payload.content['state']['value']['unit'] == 'degC'


async def test_ipv4_encoding():
    cdc = codec.CV.get()

    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='EdgeCase',
            content={'ip': '192.168.0.1'},
        )
    )
    payload = cdc.decode_payload(payload)
    assert payload.content['ip'] == '192.168.0.1'


async def test_point_presence():
    cdc = codec.CV.get()

    present_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='SetpointProfile',
            content={
                'points': [
                    {'time[s]': 0, 'temperature[degC]': 0},
                    {'time[s]': 10, 'temperature[degC]': 10},
                ]
            },
        )
    )

    absent_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='SetpointProfile',
            content={
                'points': [
                    {'time[s]': 10, 'temperature[degC]': 10},
                ]
            },
        )
    )

    assert present_payload.content != absent_payload.content

    present_payload = cdc.decode_payload(present_payload)
    absent_payload = cdc.decode_payload(absent_payload)
    assert present_payload.content['points'][0]['time']['value'] == 0


async def test_enum_decoding():
    cdc = codec.CV.get()

    encoded_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='DigitalActuator',
            content={
                'storedState': 'STATE_ACTIVE',
            },
        )
    )

    encoded_int_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='DigitalActuator',
            content={
                'storedState': 1,
            },
        )
    )

    # String and int enums are both valid input
    assert encoded_payload.content == encoded_int_payload.content

    payload = cdc.decode_payload(encoded_payload)
    assert payload.content['storedState'] == 'STATE_ACTIVE'

    payload = cdc.decode_payload(encoded_payload, mode=ReadMode.STORED)
    assert payload.content['storedState'] == 1

    # Enum value 0 is present when given
    zero_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='DigitalActuator',
            content={
                'storedState': 'STATE_INACTIVE',
            },
        )
    )
    assert parsed(zero_payload, DigitalActuator.Block).HasField('storedState')
    assert zero_payload.content != cdc.encode_payload(DecodedPayload(blockId=1, blockType='DigitalActuator')).content


async def test_invalid_if_decoding():
    cdc = codec.CV.get()

    encoded_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='EdgeCase',
            content={
                # omit if zero, None and typed None dropped on encode
                'listValues': [0, 10, None, {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': None}],
                'deltaV': 0,  # null if zero
                'logged': 0,  # omit if zero
            },
        )
    )

    payload = cdc.decode_payload(encoded_payload)
    assert len(payload.content['listValues']) == 1
    assert payload.content['listValues'][0]['value'] == pytest.approx(10)
    assert payload.content['deltaV']['value'] is None
    assert 'logged' not in payload.content


async def test_map_fields():
    cdc = codec.CV.get()

    encoded_payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='Variables',
            content={
                'variables': {
                    'k1': {'digital': 'STATE_ACTIVE'},
                    'k2': {'temp[degC]': 20},
                    'k3': {'duration[s]': 10},
                },
            },
        )
    )
    payload = cdc.decode_payload(encoded_payload)
    assert payload.content == {
        'variables': {
            'k1': {'digital': 'STATE_ACTIVE'},
            'k2': {
                'temp': {
                    '__bloxtype': 'Quantity',
                    'unit': 'degC',
                    'value': pytest.approx(20),
                },
            },
            'k3': {
                'duration': {'__bloxtype': 'Quantity', 'unit': 'second', 'value': 10},
            },
        }
    }


# Presence fill: MessageToDict leaves out every unset optional field


async def test_fill_default():
    content = decode(Pid.Block())

    # Absent optional readonly fields are invalid: None, or a typed object with None
    assert content['outputValue'] is None
    assert content['inputValue'] == {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': None, 'readonly': True}

    # Absent optional writable fields get their default
    assert content['enabled'] is False
    assert content['integralReset'] == 0
    assert content['derivativeFilterChoice'] == 'FILTER_NONE'
    assert content['kp'] == {'__bloxtype': 'Quantity', 'unit': '1 / degC', 'value': 0}
    assert content['inputId'] == {'__bloxtype': 'Link', 'type': 'SetpointSensorPairInterface', 'id': 0}

    # Non-optional fields are always present
    assert content['active'] is False
    assert content['derivativeFilter'] == 'FILTER_NONE'

    # Explicit values are kept
    content = decode(Pid.Block(outputValue=0, enabled=True, derivativeFilterChoice=2))
    assert content['outputValue'] == 0
    assert content['enabled'] is True
    assert content['derivativeFilterChoice'] == 'SETTLE_IN_47_SAMPLES'

    # Present singular messages are filled too
    block = DigitalActuator.Block()
    block.constraints.minOff.enabled = True
    for mode in [ReadMode.DEFAULT, ReadMode.STORED]:
        content = decode(block, mode)
        assert content['constraints']['minOff']['enabled'] is True
        assert content['constraints']['minOff']['duration'] == {'__bloxtype': 'Quantity', 'unit': 'second', 'value': 0}


async def test_fill_stored():
    content = decode(Pid.Block(kp=4096), ReadMode.STORED)

    # Readonly fields are filtered, writable fields filled, enums as numbers
    assert 'outputValue' not in content
    assert 'inputValue' not in content
    assert content['enabled'] is False
    assert content['derivativeFilterChoice'] == 0
    assert content['kp']['value'] == pytest.approx(1)

    # Wrappers are flattened, and an absent wrapper is an empty list
    content = decode(Sequence.Block(), ReadMode.STORED)
    assert content['instructions'] == []


async def test_fill_changed():
    # Absent optional writable fields are left absent: unchanged
    content = decode(Pid.Block(), ReadMode.CHANGED)
    assert 'enabled' not in content
    assert 'kp' not in content
    assert content['outputValue'] is None
    assert content['inputValue']['value'] is None
    assert content['active'] is False

    # Present ones are decoded, zero included
    content = decode(Pid.Block(enabled=False), ReadMode.CHANGED)
    assert content['enabled'] is False


async def test_changed_list_elements():
    # A CHANGED read has complete list elements: zero fields decode as in DEFAULT
    block = ActuatorLogic.Block()
    block.digital.items.add(id=5)
    block.analog.items.add(id=6)

    default = decode(block)
    content = decode(block, ReadMode.CHANGED)

    assert content['digital'] == default['digital']
    assert content['digital'] == [
        {
            'id': {'__bloxtype': 'Link', 'type': 'DigitalInterface', 'id': 5},
            'op': 'OP_VALUE_IS',
            'result': 'RESULT_FALSE',
            'rhs': 'STATE_INACTIVE',
        }
    ]
    assert content['analog'] == default['analog']

    block = Balancer.Block()
    block.clients.add(id=1)
    content = decode(block, ReadMode.CHANGED)
    assert content['clients'] == [
        {
            'id': {'__bloxtype': 'Link', 'type': 'Any', 'id': 1},
            'requested': 0,
            'granted': 0,
        }
    ]


async def test_changed_wrappers():
    # Covered wrappers are an empty list when absent
    content = decode(ActuatorLogic.Block(), ReadMode.CHANGED)
    assert content['digital'] == []
    assert content['analog'] == []
    assert decode(GpioModule.Block(), ReadMode.CHANGED)['channels'] == []

    # Uncovered wrappers stay absent in CHANGED reads, and are empty in DEFAULT reads
    for message, key, empty in [
        (Sequence.Block(), 'instructions', []),
        (pb2.SetpointProfile_pb2.Block(), 'points', []),
        (pb2.TempSensorCombi_pb2.Block(), 'sensors', []),
        (pb2.TempSensorMock_pb2.Block(), 'fluctuations', []),
        (pb2.DisplaySettings_pb2.Block(), 'widgets', []),
        (pb2.Variables_pb2.Block(), 'variables', {}),
    ]:
        assert key not in decode(message, ReadMode.CHANGED)
        assert decode(message)[key] == empty

    # A wrapper the firmware does send in a CHANGED read is decoded
    block = pb2.TempSensorCombi_pb2.Block()
    block.sensors.items.append(10)
    assert decode(block, ReadMode.CHANGED)['sensors'] == [
        {'__bloxtype': 'Link', 'type': 'TempSensorInterface', 'id': 10},
    ]


async def test_changed_traversed_messages():
    # A disabled constraint is absent from a CHANGED read.
    # Its covered state is zero, and decodes as typed defaults.
    content = decode(DigitalActuator.Block(), ReadMode.CHANGED)
    assert content['constraints']['minOff'] == {
        'limiting': False,
        'remaining': {'__bloxtype': 'Quantity', 'unit': 'second', 'value': 0, 'readonly': True},
    }
    assert content['constraints']['mutexed']['hasLock'] is False
    assert 'constrainedBy' not in content

    # In DEFAULT reads, absent messages stay absent
    assert 'constraints' not in decode(DigitalActuator.Block())


async def test_changed_skip_changed():
    # skip_changed fields are not in a CHANGED read: decoded as zero, and ignored by the merge
    cdc = codec.CV.get()
    cached = decode(SysInfo.Block(uptime=1000, memoryFree=2000, version='v1'))
    partial = decode(SysInfo.Block(version='v2'), ReadMode.CHANGED)
    assert partial['uptime']['value'] == 0

    assert cdc.merge_changed('SysInfo', cached, partial) is True
    assert cached['uptime']['value'] == 1
    assert cached['memoryFree'] == 2000
    assert cached['version'] == 'v2'


# merge_changed: merging CHANGED(t1) into DEFAULT(t0) gives DEFAULT(t1)


def _logic(result: int, digital_result: int, analog_rhs: int) -> Message:
    block = ActuatorLogic.Block(targetId=7, enabled=True, expression='a|b', result=result)
    block.digital.items.add(id=5, op=0, rhs=0, result=digital_result)
    block.analog.items.add(id=6, op=1, rhs=analog_rhs, result=0)
    return block


async def test_merge_actuator_logic():
    assert_merges(_logic(1, 1, 4096), _logic(0, 0, 4096), 'enabled')
    assert_merges(_logic(0, 0, 4096), _logic(1, 1, 8192), 'enabled')

    # Lists are replaced whole
    t1 = ActuatorLogic.Block(targetId=7, enabled=True, expression='a|b')
    t1.digital.SetInParent()
    assert_merges(_logic(1, 1, 4096), t1, 'enabled')


def _gpio(claimed: int, pressure: int, fault: int, resistance: int) -> Message:
    block = GpioModule.Block(modulePosition=1, useExternalPower=True, baroPressure=pressure)
    block.channels.items.add(id=1, deviceType=1, pinsMask=3, width=2, name='left', capabilities=7, claimedBy=claimed)
    block.channels.items.add(id=2, capabilities=7)
    block.status.moduleStatus = 1
    block.status.overCurrent = fault
    block.analogChannels.add(id=1, sensorType=2, resistance=resistance)
    block.analogChannels.add(id=2)
    return block


async def test_merge_gpio_module():
    assert_merges(_gpio(0, 4096, 0, 0), _gpio(10, 8192, 1, 16384))
    # omit_if_zero values leave the key out: absent from the partial is zero
    assert_merges(_gpio(10, 8192, 1, 16384), _gpio(0, 0, 0, 0))


def _pins(claimed: int) -> Message:
    block = Spark3Pins.Block(enableIoSupply5V=True, voltage5=5000, voltage12=12000)
    block.channels.add(id=1, capabilities=3, claimedBy=claimed)
    block.channels.add(id=2, capabilities=3)
    return block


async def test_merge_pins():
    # skip_changed voltages are kept: they do not change between the reads here
    assert_merges(_pins(0), _pins(10))
    assert_merges(_pins(10), _pins(0))


async def test_merge_balancer():
    t0 = Balancer.Block()
    t0.clients.add(id=1, requested=4096, granted=4096)
    t1 = Balancer.Block()
    t1.clients.add(id=1)
    t1.clients.add(id=2, requested=2048, granted=1024)
    assert_merges(t0, t1)
    assert_merges(t1, Balancer.Block())


def _pid(value: int | None, active: bool) -> Message:
    block = Pid.Block(
        inputId=1,
        outputId=2,
        enabled=True,
        active=active,
        kp=4096,
        ti=100,
        td=10,
        integral=0 if value is None else 256,
        derivativeFilter=0 if value is None else 2,
    )
    if value is not None:
        block.inputValue = value
        block.inputSetting = value + 4096
        block.outputValue = value
        block.p = 1
        block.i = 0
        block.error = -4096
    return block


async def test_merge_pid():
    assert_merges(_pid(20 * 4096, True), _pid(21 * 4096, True), 'enabled')
    # Invalid values are absent: None
    assert_merges(_pid(21 * 4096, True), _pid(None, False), 'enabled')
    assert_merges(_pid(None, False), _pid(0, True), 'enabled')


def _actuator(state: int | None, min_off: Message | None) -> Message:
    block = DigitalActuator.Block(hwDevice=19, channel=1, storedState=1, settingMode=0, claimedBy=0)
    if state is not None:
        block.state = state
        block.desiredState = state
    if min_off is not None:
        block.constraints.minOff.CopyFrom(min_off)
    return block


async def test_merge_constrained_actuator():
    cdc = codec.CV.get()
    enabled = Constraints.DurationConstraint(duration=60000, enabled=True, limiting=True, remaining=30000)
    counting = Constraints.DurationConstraint(duration=60000, enabled=True, limiting=True, remaining=20000)
    released = Constraints.DurationConstraint(duration=60000, enabled=True, limiting=False, remaining=0)
    disabled = Constraints.DurationConstraint(duration=60000, enabled=False)

    # Enabled: the constraint counts down, and releases
    assert_merges(_actuator(1, enabled), _actuator(1, counting), 'storedState', 'settingMode')
    assert_merges(_actuator(1, counting), _actuator(0, released), 'storedState', 'settingMode')

    # Disabled (by a write, which replaced the cache): the CHANGED read leaves it out,
    # and its covered state is zero
    t1 = _actuator(1, disabled)
    cached = decode(t1)
    partial = decode(DigitalActuator.Block(state=1, desiredState=1, storedState=1), ReadMode.CHANGED)
    assert cdc.merge_changed('DigitalActuator', cached, partial) is False
    assert cached == decode(t1)

    # Disabled with zero settings: absent from the DEFAULT read.
    # The traversed messages in the partial are all default, and skipped.
    assert_merges(_actuator(1, None), _actuator(0, None), 'storedState', 'settingMode')

    # Only an uncovered, firmware-written field changed
    t1 = _actuator(1, None)
    t1.storedState = 0
    assert_merges(_actuator(1, None), t1, 'storedState')

    # Enabled by a writer the cache did not see: can not be merged
    cached = decode(_actuator(1, None))
    partial = decode(changed(_actuator(1, enabled)), ReadMode.CHANGED)
    with pytest.raises(NeedFullRead):
        cdc.merge_changed('DigitalActuator', cached, partial)

    # The same, one level down: another constraint is cached
    t0 = _actuator(1, None)
    t0.constraints.minOn.CopyFrom(disabled)
    t1 = deepcopy(t0)
    t1.state = 0
    assert_merges(t0, t1, 'storedState', 'settingMode')

    cached = decode(t0)
    t1.constraints.minOff.CopyFrom(enabled)
    partial = decode(changed(t1), ReadMode.CHANGED)
    with pytest.raises(NeedFullRead, match='minOff'):
        cdc.merge_changed('DigitalActuator', cached, partial)


async def test_merge_sequence():
    t0 = Sequence.Block(enabled=True, activeInstruction=1, status=4, elapsed=1000)
    t0.instructions.items.add().WAIT.SetInParent()
    t0.instructions.items.add().RESTART.SetInParent()
    t1 = Sequence.Block()
    t1.CopyFrom(t0)
    t1.activeInstruction = 0
    t1.status = 3
    t1.elapsed = 0

    # Instructions are never in a CHANGED read, and are kept
    assert_merges(t0, t1, 'enabled', 'activeInstruction')
    partial = decode(changed(t1, 'enabled', 'activeInstruction'), ReadMode.CHANGED)
    assert 'instructions' not in partial


async def test_merge_uncovered_wrapper():
    # An uncovered wrapper is only in a CHANGED read when the firmware sent it, and then it is complete
    t0 = TempSensorCombi.Block()
    t0.sensors.items.append(1)
    t1 = TempSensorCombi.Block()
    t1.sensors.items.append(2)
    assert_merges(t0, t1, 'sensors')


async def test_merge_edge_cases():
    cdc = codec.CV.get()

    # Stub types are replaced, never merged
    cached = {'error': 'old'}
    assert cdc.merge_changed('ErrorObject', cached, {'error': 'new'}) is True
    assert cached == {'error': 'new'}
    assert cdc.merge_changed('ErrorObject', cached, {'error': 'new'}) is False

    cached = {'bytes': 'ZAA='}
    assert cdc.merge_changed('Deprecated', cached, {'bytes': 'ZAE='}) is True
    assert cached == {'bytes': 'ZAE='}

    # A traversed message the partial does not hold is left alone
    cached = decode(_actuator(1, Constraints.DurationConstraint(duration=1000, enabled=True, limiting=True)))
    expected = deepcopy(cached)
    partial = decode(DigitalActuator.Block(state=1, desiredState=1), ReadMode.CHANGED)
    del partial['constraints']
    assert cdc.merge_changed('DigitalActuator', cached, partial) is False
    assert cached == expected

    # An absent covered value is deleted from the cache
    cached = decode(pb2.TempSensorAnalog_pb2.Block(resistance=16384))
    partial = decode(pb2.TempSensorAnalog_pb2.Block(), ReadMode.CHANGED)
    assert 'resistance' in cached
    assert cdc.merge_changed('TempSensorAnalog', cached, partial) is True
    assert 'resistance' not in cached
    assert cdc.merge_changed('TempSensorAnalog', cached, partial) is False


# Logged view: the history format, derived from the DEFAULT decode


@pytest.mark.parametrize('case', GOLDEN, ids=[f'{c["blockType"]}-{c["variant"]}' for c in GOLDEN])
async def test_logged_view_golden(case: dict):
    """
    DEFAULT decode + logged_view matches the removed LOGGED decode,
    which is stored in fixtures/logged_golden.json.
    """
    cdc = codec.CV.get()
    block_type = case['blockType']
    payload = EncodedPayload(blockId=100, blockType=block_type, content=case['payload'])
    content = cdc.decode_payload(payload).content
    view = cdc.logged_view(block_type, content, full=True)

    expected = deepcopy(case['logged'])
    desc = next(v for v in lookup.CV_OBJECTS.get() if v.type_str == block_type).message_cls.DESCRIPTOR

    # Intended differences, only for fields that are absent from the payload (the 'empty' variant).
    # The old LOGGED decode left the key out. Now:
    # - an absent optional readonly field is None: invalid.
    # - an absent optional writable field has its default value.
    #   The firmware sets every stored field in DEFAULT reads, and no logged field is write-only,
    #   so real reads never take this path.
    for key in set(view) - set(expected):
        name = key.split('[')[0].split('<')[0]
        field = desc.fields_by_name[name]
        assert case['variant'] == 'empty', key
        assert descriptors.is_optional(field), key
        if descriptors.options(field).readonly:
            assert view[key] is None, key
        else:
            assert view[key] == 0, key
        expected[key] = view[key]

    assert view == expected


async def test_logged_view():
    cdc = codec.CV.get()

    # skip_changed fields are only in the full view
    content = decode(SysInfo.Block(uptime=1000, memoryFree=100, version='v1'))
    assert cdc.logged_view('SysInfo', content, full=True)['uptime[second]'] == 1
    assert cdc.logged_view('SysInfo', content, full=True)['memoryFree'] == 100
    assert cdc.logged_view('SysInfo', content, full=False) == {}

    content = decode(pb2.WiFiSettings_pb2.Block(signal=-40))
    assert cdc.logged_view('WiFiSettings', content, full=True) == {'signal': -40}
    assert cdc.logged_view('WiFiSettings', content, full=False) == {}

    # Enum names become numbers, and list elements keep their position
    content = decode(_actuator(1, None))
    assert cdc.logged_view('DigitalActuator', content, full=False) == {
        'desiredState': 1,
        'state': 1,
    }
    content = decode(_gpio(0, 0, 0, 0))
    assert cdc.logged_view('GpioModule', content, full=False) == {'analogChannels': [{}, {}]}

    # Links
    assert cdc.logged_view('EdgeCase', {'logged': 1, 'link': {'__bloxtype': 'Link', 'id': 1}}, full=True) == {
        'logged': 1,
    }

    # Logged links and singular messages: no proto has them yet.
    # These branches of _logged are there for future protos, so the nodes are built by hand.
    # No logged field is a link or a datetime today.
    fields = pb2.EdgeCase_pb2.Block.DESCRIPTOR.fields_by_name
    external = pb2.TempSensorExternal_pb2.Block.DESCRIPTOR.fields_by_name
    nodes = {
        'link': descriptors.LoggedNode(fields['link'], None, skip_changed=False),
        'lastUpdated': descriptors.LoggedNode(external['lastUpdated'], None, skip_changed=False),
        'state': descriptors.LoggedNode(
            fields['state'],
            {
                'connected': descriptors.LoggedNode(
                    fields['state'].message_type.fields_by_name['connected'], None, False
                )
            },
            skip_changed=False,
        ),
    }
    data = {
        'link': {'__bloxtype': 'Link', 'type': 'ActuatorAnalogInterface', 'id': 'actuator'},
        'lastUpdated': '2023-11-14T22:13:20Z',
        'state': {'connected': True, 'value': {'__bloxtype': 'Quantity', 'unit': 'degC', 'value': 20}},
    }
    assert codec._logged(nodes, data, full=True) == {
        'link<ActuatorAnalogInterface>': 'actuator',
        'lastUpdated': 1_700_000_000,
        'state': {'connected': True},
    }

    # Stub types and interfaces have no logged fields
    assert cdc.logged_view('ErrorObject', {'error': 'boo'}, full=True) == {}
    assert cdc.logged_view('SetpointSensorPairInterface', {}, full=True) == {}


# Writes by presence


async def test_encode_presence():
    cdc = codec.CV.get()

    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='Pid',
            content={
                'enabled': False,
                'boilMinOutput': 0,
                'derivativeFilterChoice': 'FILTER_NONE',
                'outputValue': 50,  # readonly: stripped
                'drivenOutputId': 1,  # ignored: stripped
            },
        )
    )
    message = parsed(payload, Pid.Block)

    # Explicit zero, false, and enum 0 are present
    assert message.HasField('enabled')
    assert message.HasField('boilMinOutput')
    assert message.HasField('derivativeFilterChoice')

    # Absent keys are absent: the controller keeps their value
    assert not message.HasField('ti')
    assert not message.HasField('outputValue')
    assert not message.drivenOutputId

    # Dates are encoded as seconds
    payload = cdc.encode_payload(
        DecodedPayload(blockId=1, blockType='SetpointProfile', content={'start': '2023-11-14T22:13:20Z'})
    )
    assert parsed(payload, pb2.SetpointProfile_pb2.Block).start == 1_700_000_000

    # A nested patch only sets the given leaves
    payload = cdc.encode_payload(
        DecodedPayload(
            blockId=1,
            blockType='DigitalActuator',
            content={'constraints': {'minOff': {'enabled': True}}},
        )
    )
    message = parsed(payload, DigitalActuator.Block)
    assert message.constraints.minOff.HasField('enabled')
    assert not message.constraints.minOff.HasField('duration')
    assert not message.constraints.HasField('minOn')
    assert not message.HasField('storedState')

    # An empty list sends a present, empty wrapper: it clears the list
    payload = cdc.encode_payload(DecodedPayload(blockId=1, blockType='Sequence', content={'instructions': []}))
    message = parsed(payload, Sequence.Block)
    assert message.HasField('instructions')
    assert len(message.instructions.items) == 0


def _encode(block_type: str, content: dict, cdc: Codec | None = None) -> Message:
    cdc = cdc or codec.CV.get()
    payload = cdc.encode_payload(DecodedPayload(blockId=1, blockType=block_type, content=content))
    impl = next(v for v in lookup.CV_OBJECTS.get() if v.type_str == block_type)
    return parsed(payload, impl.message_cls)


async def test_encode_null_leaves():
    """A null resets a writable leaf: it is sent present with its default"""
    message = _encode(
        'Pid',
        {
            'enabled': None,  # bool
            'boilMinOutput': None,  # number
            'derivativeFilterChoice': None,  # enum
            'kp': {'__bloxtype': 'Quantity', 'unit': '1 / degC', 'value': None},
            'td[s]': None,
            'inputId': {'__bloxtype': 'Link', 'type': 'SetpointSensorPairInterface', 'id': None},
            'outputId<>': None,
            'outputValue': None,  # readonly: stripped
        },
    )
    for key in ['enabled', 'boilMinOutput', 'derivativeFilterChoice', 'kp', 'td', 'inputId', 'outputId']:
        assert message.HasField(key), key
        assert getattr(message, key) == 0, key
    assert not message.HasField('outputValue')
    assert not message.HasField('ti')  # Absent: kept

    # Strings and datetimes
    assert _encode('DisplaySettings', {'name': None}).HasField('name')
    assert _encode('DisplaySettings', {'name': None}).name == ''
    message = _encode('SetpointProfile', {'start': None})
    assert message.HasField('start')
    assert message.start == 0

    # A zero override means the spec default
    message = _encode('TempSensorAnalog', {'spec_a_override': None})
    assert message.HasField('spec_a_override')
    assert message.spec_a_override == 0

    # Readonly fields are only encoded without filtering: a null one is invalid, and left out
    message = _encode('Pid', {'outputValue': None, 'enabled': None}, Codec(filter_values=False))
    assert not message.HasField('outputValue')
    assert message.HasField('enabled')


async def test_encode_null_messages():
    """A null singular message is sent present, with every writable leaf reset: a constraint is disabled and zeroed"""
    message = _encode('ActuatorPwm', {'constraints': {'max': None}})
    assert message.HasField('constraints')
    assert message.constraints.HasField('max')
    assert message.constraints.max.HasField('enabled')
    assert message.constraints.max.enabled is False
    assert message.constraints.max.HasField('value')
    assert message.constraints.max.value == 0
    assert not message.constraints.HasField('min')  # Absent: kept

    # Recursively, links included
    message = _encode('ActuatorPwm', {'constraints': None})
    assert message.constraints.HasField('min')
    assert message.constraints.HasField('max')
    assert message.constraints.balanced.HasField('balancerId')
    assert message.constraints.balanced.balancerId == 0
    assert message.constraints.balanced.HasField('enabled')

    message = _encode('DigitalActuator', {'constraints': {'mutexed': None}})
    mutexed = message.constraints.mutexed
    assert [f.name for f, _ in mutexed.ListFields()] == ['mutexId', 'extraHoldTime', 'enabled']
    assert not mutexed.enabled

    # A null leaf in a message
    message = _encode('ActuatorPwm', {'constraints': {'min': {'enabled': True, 'value': None}}})
    assert message.constraints.min.enabled is True
    assert message.constraints.min.HasField('value')
    assert message.constraints.min.value == 0

    # Members of a oneof are left out: none of them is the default
    assert descriptors.reset_value(pb2.EdgeCase_pb2.Block.DESCRIPTOR.fields_by_name['settings']) == {
        'address': 0,
        'offset': 0,
    }
    variable = pb2.Variables_pb2.VariableMap.DESCRIPTOR.fields_by_name['items'].message_type.fields_by_name['value']
    assert descriptors.reset_value(variable) == {}


async def test_encode_null_lists():
    """A null list wrapper is sent present and empty: the list is cleared"""
    message = _encode('SetpointProfile', {'points': None})
    assert message.HasField('points')
    assert len(message.points.items) == 0

    message = _encode('Sequence', {'instructions': None})
    assert message.HasField('instructions')
    assert len(message.instructions.items) == 0

    # The Variables map is present and empty. The firmware merges it by key: this changes nothing.
    message = _encode('Variables', {'variables': None})
    assert message.HasField('variables')
    assert len(message.variables.items) == 0

    # A null map value is an empty message. For Variables, the firmware deletes that key.
    message = _encode('Variables', {'variables': {'a': None, 'b': {'analog': 2}}})
    assert set(message.variables.items) == {'a', 'b'}
    assert message.variables.items['a'].WhichOneof('var') is None
    assert message.variables.items['b'].analog == 2 * 4096

    # List elements are complete: a null field there is left out, and has its default
    message = _encode(
        'DisplaySettings',
        {'widgets': [{'pos': 1, 'name': None, 'color': 'aa0088', 'tempSensor<>': 3}]},
    )
    [widget] = message.widgets.items
    assert widget.pos == 1
    assert widget.name == ''
    assert widget.color == b'\xaa\x00\x88'

    # A repeated field without wrapper has no presence: empty is not sent
    message = _encode('EdgeCase', {'listValues': None, 'additionalLinks': None})
    assert len(message.listValues) == 0
    assert len(message.additionalLinks) == 0


async def test_encode_null_members():
    """
    In list elements and map values, a null member of a oneof is sent present at its default:
    leaving it out would unset the oneof, and the firmware deletes a Variables entry without a value.
    """
    # A zero timestamp reads as null
    message = _encode('Variables', {'variables': {'ts': {'timestamp': None}, 'a': {'analog': 1}}})
    assert message.variables.items['ts'].WhichOneof('var') == 'timestamp'
    assert message.variables.items['ts'].timestamp == 0
    assert message.variables.items['a'].analog == 4096

    # Typed nulls and postfixed keys
    message = _encode(
        'Variables',
        {
            'variables': {
                'temp': {'temp[degC]': None},
                'link': {'link': {'__bloxtype': 'Link', 'type': 'Any', 'id': None}},
                'duration': {'duration': {'__bloxtype': 'Quantity', 'unit': 'second', 'value': None}},
            }
        },
    )
    assert {k: v.WhichOneof('var') for k, v in message.variables.items.items()} == {
        'temp': 'temp',
        'link': 'link',
        'duration': 'duration',
    }

    # In list elements, nested in a oneof member message too
    message = _encode(
        'DisplaySettings',
        {'widgets': [{'pos': 1, 'name': 'w', 'tempSensor<>': None}]},
    )
    [widget] = message.widgets.items
    assert widget.WhichOneof('WidgetType') == 'tempSensor'
    assert widget.tempSensor == 0

    message = _encode('Sequence', {'instructions': [{'WAIT_UNTIL': {'__raw__time': None}}]})
    [instruction] = message.instructions.items
    assert instruction.WAIT_UNTIL.WhichOneof('time') == '__raw__time'
    assert instruction.WAIT_UNTIL.__getattribute__('__raw__time') == 0

    # Another member given with a value is sent: the null member is left out
    message = _encode('Variables', {'variables': {'a': {'timestamp': None, 'analog': 2}}})
    assert message.variables.items['a'].WhichOneof('var') == 'analog'
    message = _encode('Variables', {'variables': {'a': {'analog': 2, 'timestamp': None}}})
    assert message.variables.items['a'].WhichOneof('var') == 'analog'

    # Of two null members, the first is sent
    message = _encode('Variables', {'variables': {'a': {'timestamp': None, 'temp[degC]': None}}})
    assert message.variables.items['a'].WhichOneof('var') == 'timestamp'

    # A null map value is still an empty message: the firmware deletes that key
    message = _encode('Variables', {'variables': {'a': None}})
    assert message.variables.items['a'].WhichOneof('var') is None


def _nested_nulls(data: dict) -> set[tuple[str, str]]:
    """The nulls below the top level of `data`, as (top-level key, key of the null)"""

    def walk(value: Any, key: str) -> Iterator[str]:
        if codec.processor.is_null(value):
            yield key
        elif isinstance(value, list):
            for v in value:
                yield from walk(v, key)
        elif isinstance(value, dict):
            for k, v in value.items():
                yield from walk(v, k)

    return {(top, key) for top, value in data.items() if not codec.processor.is_null(value) for key in walk(value, top)}


@pytest.mark.parametrize('variant', ['full', 'empty', 'zero_members'])
async def test_encode_null_round_trip(variant: str):
    """
    Writing what a DEFAULT read returned writes the same values.
    A DEFAULT read has nulls in writable fields only for no link, a zero datetime, and null_if_zero values:
    the reset writes the same zero.
    """
    cdc = codec.CV.get()
    is_null = codec.processor.is_null

    def writable(desc, data: dict) -> dict:
        out = {}
        for key, value in data.items():
            field = desc.fields_by_name[key]
            if not descriptors.is_writable(field):
                continue
            field = descriptors.list_wrapper(field) or field
            msg = descriptors.value_type(field)
            if msg is None:
                out[key] = value
            elif descriptors.is_map(field):
                out[key] = {k: writable(msg, v) for k, v in value.items()}
            elif isinstance(value, list):
                out[key] = [writable(msg, v) for v in value]
            else:
                out[key] = writable(msg, value)
        return out

    messages = {
        'full': lambda cls: populate(cls()),
        'empty': lambda cls: cls(),
        # List elements and map values with each oneof member at zero
        'zero_members': lambda cls: add_zero_members(populate(cls())),
    }

    nulls = set()
    nested = set()
    for entry in lookup.CV_OBJECTS.get():
        message = messages[variant](entry.message_cls)
        first = decode(message)
        payload = cdc.encode_payload(DecodedPayload(blockId=1, blockType=entry.type_str, content=first))
        second = cdc.decode_payload(payload).content

        desc = entry.message_cls.DESCRIPTOR
        assert writable(desc, second) == writable(desc, first), entry.type_str
        nulls |= {(entry.type_str, k) for k, v in writable(desc, first).items() if is_null(v)}
        nested |= {(entry.type_str, *p) for p in _nested_nulls(writable(desc, first))}

    # Links decode as id 0: the API shows no link as id None, and writes it as 0
    if variant == 'empty':
        assert nulls == {('SetpointProfile', 'start'), ('SysInfo', 'systemTime'), ('EdgeCase', 'deltaV')}
    else:
        assert nulls == set()

    # A zero datetime in a map value and in a list element reads as null
    if variant == 'zero_members':
        assert nested == {
            ('Variables', 'variables', 'timestamp'),
            ('Sequence', 'instructions', '__raw__time'),
        }
    else:
        assert nested == set()


def _wrappers() -> list[tuple[lookup.ObjectLookup, str]]:
    return [
        (entry, field.name)
        for entry in lookup.CV_OBJECTS.get()
        for field in entry.message_cls.DESCRIPTOR.fields
        if descriptors.list_wrapper(field)
    ]


async def test_wrapper_round_trips():
    rw_cdc = Codec(filter_values=False)
    wrappers = _wrappers()
    assert len(wrappers) == 9

    for entry, key in wrappers:
        value = rw_cdc.decode_payload(encoded(populate(entry.message_cls()))).content[key]
        assert value, key
        empty = {} if isinstance(value, dict) else []

        # A value round trips in API shape
        payload = rw_cdc.encode_payload(DecodedPayload(blockId=1, blockType=entry.type_str, content={key: value}))
        assert len(getattr(parsed(payload, entry.message_cls), key).items) == 1
        assert rw_cdc.decode_payload(payload).content[key] == value

        # An empty list is a present, empty wrapper
        payload = rw_cdc.encode_payload(DecodedPayload(blockId=1, blockType=entry.type_str, content={key: empty}))
        assert parsed(payload, entry.message_cls).HasField(key)
        assert rw_cdc.decode_payload(payload).content[key] == empty

        # An absent key is an absent wrapper
        payload = rw_cdc.encode_payload(DecodedPayload(blockId=1, blockType=entry.type_str, content={}))
        assert not parsed(payload, entry.message_cls).HasField(key)
