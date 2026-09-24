"""
Guards for the manual step in adding a block type or unit.

`invoke compile-proto` writes a _pb2.py file, but the codec lookup table is
built from the import list in codec/pb2.py. Forgetting that second step is
invisible until runtime, where it surfaces as a 400 'No codec entry found'.
The proto submodule is not checked out in CI, so these checks are derived
from the compiled descriptors rather than the .proto sources.
"""

import importlib
import re
from base64 import b64encode
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from google.protobuf import descriptor_pb2
from google.protobuf.descriptor import Descriptor, FieldDescriptor

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import descriptors, lookup, pb2, unit_conversion
from brewblox_devcon_spark.models import CrossPlatformResetReason, EncodedPayload
from test.fixtures.messages import populate

BLOCK_OPTS = pb2.brewblox_pb2.msg
FIELD_OPTS = pb2.brewblox_pb2.field


@pytest.fixture(autouse=True)
def setup_codec():
    # Populates the lookup and unit conversion context vars
    codec.setup()


def compiled_modules() -> list[str]:
    """Names of every _pb2 module present in proto-compiled/"""
    compiled_dir = Path(pb2.__file__).parent / 'proto-compiled'
    return sorted(p.stem for p in compiled_dir.glob('*_pb2.py'))


def defines_block_type(module) -> bool:
    return any(
        desc.GetOptions().Extensions[BLOCK_OPTS].objtype for desc in module.DESCRIPTOR.message_types_by_name.values()
    )


def test_all_block_types_are_registered():
    """
    Every compiled proto that declares an objtype must be imported in pb2.py,
    or its blocks cannot be encoded or decoded.
    """
    # pb2.py extends sys.path with proto-compiled/, so these import by bare name
    unregistered = [
        name
        for name in compiled_modules()
        if defines_block_type(importlib.import_module(name)) and name not in pb2.__all__
    ]

    assert not unregistered, f'add these to brewblox_devcon_spark/codec/pb2.py: {unregistered}'


def test_block_types_are_uniquely_mapped():
    """Two messages claiming the same objtype would silently shadow each other."""
    type_ints = [v.type_int for v in lookup.CV_OBJECTS.get()]
    duplicates = {i for i in type_ints if type_ints.count(i) > 1}
    assert not duplicates, f'duplicate block type values: {duplicates}'


def test_unit_formats_cover_the_proto_enum():
    """
    Units are looked up by protobuf enum name, so FORMATS and UnitType must
    agree exactly. A missing key raises KeyError for every field using it.
    """
    enum_names = set(pb2.brewblox_pb2.UnitType.keys())
    format_names = set(unit_conversion.FORMATS)

    assert enum_names - format_names == set(), 'missing from FORMATS'
    assert format_names - enum_names == set(), 'not a UnitType value'


def test_field_units_resolve():
    """Every unit actually used by a registered block field must convert."""
    converter = unit_conversion.CV.get()

    for entry in lookup.CV_OBJECTS.get():
        for field in entry.message_cls.DESCRIPTOR.fields:
            unit = field.GetOptions().Extensions[FIELD_OPTS].unit
            if unit:
                # Raises KeyError if the enum name has no FORMATS entry
                converter.to_user_unit(pb2.brewblox_pb2.UnitType.Name(unit))


def test_unit_formats_are_valid_units():
    """Each FORMATS value must be a unit pint can construct and convert."""
    converter = unit_conversion.UnitConverter()
    converter.temperature = 'degF'
    converter.temperature = 'degC'


def test_cross_platform_reset_reason_matches_proto():
    """
    The handshake parser keeps its own copy of SysInfo.proto's ResetReason,
    as models.py cannot import the compiled proto. They must not drift.
    """
    proto = {name.removeprefix('RESET_REASON_'): value for name, value in pb2.SysInfo_pb2.ResetReason.items()}
    ours = {member.name: member.value for member in CrossPlatformResetReason}
    assert ours == proto


# Guards for the descriptor rules that the CHANGED read and writes by presence rely on.
# EdgeCase is a test-only message, and is left out.


def block_descriptors() -> dict[str, Descriptor]:
    return {v.type_str: v.message_cls.DESCRIPTOR for v in lookup.CV_OBJECTS.get() if v.type_str != 'EdgeCase'}


def walk_fields(desc: Descriptor, path: tuple[str, ...] = (), in_list=False) -> Iterator[tuple]:
    """Yields (path, field, in_list) for every field below `desc`, list elements and map values included"""
    for field in desc.fields:
        yield (*path, field.name), field, in_list
        msg = descriptors.value_type(field)
        if msg is not None:
            nested = in_list or field.label == FieldDescriptor.LABEL_REPEATED
            yield from walk_fields(msg, (*path, field.name), nested)


def test_list_wrappers():
    """The API flattens exactly these wrappers to their bare list or map"""
    wrappers = {
        (block_type, field.name): descriptors.list_wrapper(field).full_name
        for block_type, desc in block_descriptors().items()
        for field in desc.fields
        if descriptors.list_wrapper(field)
    }
    assert wrappers == {
        ('ActuatorLogic', 'digital'): 'blox.ActuatorLogic.DigitalCompareList.items',
        ('ActuatorLogic', 'analog'): 'blox.ActuatorLogic.AnalogCompareList.items',
        ('DisplaySettings', 'widgets'): 'blox.DisplaySettings.WidgetList.items',
        ('GpioModule', 'channels'): 'blox.GpioModule.ChannelList.items',
        ('Sequence', 'instructions'): 'blox.Sequence.InstructionList.items',
        ('SetpointProfile', 'points'): 'blox.SetpointProfile.PointList.items',
        ('TempSensorCombi', 'sensors'): 'blox.TempSensorCombi.SensorList.items',
        ('TempSensorMock', 'fluctuations'): 'blox.TempSensorMock.FluctuationList.items',
        ('Variables', 'variables'): 'blox.Variables.VariableMap.items',
    }

    # Only these three have covered descendants: the others never appear in a CHANGED read
    covered = {k for k in wrappers if k[1] in descriptors.coverage(block_descriptors()[k[0]])}
    assert covered == {('ActuatorLogic', 'digital'), ('ActuatorLogic', 'analog'), ('GpioModule', 'channels')}


def test_optional_matches_descriptor_proto():
    """
    is_optional() recognizes proto3 `optional` fields by their synthetic oneof:
    the upb FieldDescriptor does not expose `proto3_optional`, but its DescriptorProto does.
    """
    for block_type, desc in block_descriptors().items():
        for path, field, _ in walk_fields(desc):
            proto = descriptor_pb2.DescriptorProto()
            field.containing_type.CopyToProto(proto)
            proto3_optional = next(f.proto3_optional for f in proto.field if f.name == field.name)
            expected = proto3_optional and field.message_type is None
            assert descriptors.is_optional(field) == expected, (block_type, *path)


def test_optional_detection():
    fields = pb2.Pid_pb2.Block.DESCRIPTOR.fields_by_name
    assert descriptors.is_optional(fields['inputValue'])
    assert descriptors.is_optional(fields['enabled'])
    assert not descriptors.is_optional(fields['active'])

    fields = pb2.Sequence_pb2.Block.DESCRIPTOR.fields_by_name
    assert not descriptors.is_optional(fields['instructions'])
    instruction = descriptors.list_wrapper(fields['instructions']).message_type
    assert not descriptors.is_optional(instruction.fields_by_name['COMMENT'])  # real oneof
    assert not descriptors.list_wrapper(fields['enabled'])
    assert not descriptors.list_wrapper(pb2.Pid_pb2.Block.DESCRIPTOR.fields_by_name['inputId'])


def test_deprecated_constraints_skip_changed():
    """
    The old `constrainedBy` settings hold readonly leaves the firmware never sends.
    `skip_changed` keeps them out of CHANGED coverage.
    They are not `ignored`: backups from before 2023-02 still carry them, and the firmware converts them.
    """
    deprecated = {}
    for block_type, desc in block_descriptors().items():
        for path, field, _ in walk_fields(desc):
            msg = descriptors.value_type(field)
            if msg is not None and msg.name.startswith('Deprecated') and len(path) == 1:
                deprecated[(block_type, *path)] = field

    assert set(deprecated) == {
        ('ActuatorAnalogMock', 'constrainedBy'),
        ('ActuatorOffset', 'constrainedBy'),
        ('ActuatorPwm', 'constrainedBy'),
        ('DigitalActuator', 'constrainedBy'),
        ('FastPwm', 'constrainedBy'),
        ('MotorValve', 'constrainedBy'),
    }

    for key, field in deprecated.items():
        opts = descriptors.options(field)
        assert not opts.ignored, key
        assert opts.skip_changed, key
        readonly_leaves = [
            path
            for path, leaf, _ in walk_fields(field.message_type)
            if not leaf.message_type and descriptors.options(leaf).readonly
        ]
        assert readonly_leaves, key
        assert not descriptors.is_covered(field), key


def test_traversed_messages_not_in_oneof():
    """A CHANGED decode sets traversed messages present: in a oneof, that would unset the member that was sent"""
    for block_type, desc in block_descriptors().items():
        for path in descriptors.traversed_messages(desc):
            msg = desc
            for name in path:
                field = msg.fields_by_name[name]
                assert field.containing_oneof is None, (block_type, *path)
                msg = field.message_type


def test_coverage_snapshot():
    """
    The merge tests build their CHANGED reads from coverage(): this pins it by hand.
    Covered are the readonly fields, the readonly state of the constraints,
    and lists with readonly element fields, unless ignored.
    """
    desc = block_descriptors()
    # digitalLegacy and analogLegacy have readonly element fields, but are ignored
    assert set(descriptors.coverage(desc['ActuatorLogic'])) == {'result', 'digital', 'analog', 'errorPos'}

    assert set(descriptors.coverage(desc['Pid'])) == {
        'inputValue',
        'inputSetting',
        'outputValue',
        'outputSetting',
        'active',
        'p',
        'i',
        'd',
        'error',
        'integral',
        'derivative',
        'boilModeActive',
        'derivativeFilter',
        'ff',
        'ambientValue',
        'ambientOffset',
        'smoothGain',
    }

    actuator = descriptors.coverage(desc['DigitalActuator'])
    assert set(actuator) == {'desiredState', 'state', 'constraints', 'transitionDurationValue', 'claimedBy'}
    assert actuator['state'].children is None
    assert {k: set(v.children) for k, v in actuator['constraints'].children.items()} == {
        'minOff': {'limiting', 'remaining'},
        'minOn': {'limiting', 'remaining'},
        'delayedOff': {'limiting', 'remaining'},
        'delayedOn': {'limiting', 'remaining'},
        'mutexed': {'hasLock', 'limiting', 'remaining'},
    }


def test_system_blocks_not_covered():
    """These blocks never appear in a CHANGED read"""
    for block_type in ['DisplaySettings', 'Variables', 'WiFiSettings']:
        assert not descriptors.coverage(block_descriptors()[block_type]), block_type


def test_uncovered_non_optional_leaves():
    """
    Outside list elements, the only uncovered leaves without presence are skip_changed.
    A CHANGED decode fills them with zero, and the merge ignores them.
    The merge applies every other uncovered leaf that is present: it has presence,
    so the firmware sent it. No skip_changed leaf may have presence.
    """
    found = set()
    for block_type, desc in block_descriptors().items():
        for path, field, in_list in walk_fields(desc):
            opts = descriptors.options(field)
            if in_list or field.message_type or field.label == FieldDescriptor.LABEL_REPEATED or opts.ignored:
                continue
            assert not (opts.skip_changed and field.has_presence), (block_type, *path)
            if not descriptors.is_optional(field) and not descriptors.is_covered(field):
                assert opts.skip_changed, (block_type, *path)
                found.add((block_type, *path))

    assert found == {
        ('SysInfo', 'uptime'),
        ('SysInfo', 'updatesPerSecond'),
        ('SysInfo', 'voltage5'),
        ('SysInfo', 'voltageExternal'),
        ('SysInfo', 'memoryFree'),
        ('SysInfo', 'memoryFreeContiguous'),
        ('SysInfo', 'memoryFreeLowest'),
        ('SysInfo', 'mainTaskStackFreeLowest'),
        ('Spark3Pins', 'voltage5'),
        ('Spark3Pins', 'voltage12'),
        ('WiFiSettings', 'signal'),
    }


def test_list_elements_have_no_presence():
    """
    The presence fill does not walk into list elements or map values:
    their fields have no presence, and there are no wrappers inside them.
    The deprecated `constrainedBy` settings are the exception, and the firmware never sends them.
    """
    for block_type, desc in block_descriptors().items():
        for path, field, in_list in walk_fields(desc):
            if not in_list or path[0] == 'constrainedBy':
                continue
            assert not descriptors.is_optional(field), (block_type, *path)
            assert not descriptors.list_wrapper(field), (block_type, *path)


def test_nullable_leaves_top_level():
    """Every nullable (optional + readonly) leaf sits at the top level of a block"""
    for block_type, desc in block_descriptors().items():
        for path, field, _ in walk_fields(desc):
            if len(path) > 1 and descriptors.is_optional(field) and path[0] != 'constrainedBy':
                assert not descriptors.options(field).readonly, (block_type, *path)


def logged_paths(desc: Descriptor, *, full: bool = True) -> list[tuple[str, ...]]:
    """
    Paths of the logged leaves of `desc`.
    With `full=False`, skip_changed leaves (and subtrees) are left out.
    """
    paths = []
    for name, node in descriptors.logged_fields(desc).items():
        if node.skip_changed and not full:
            continue
        if node.children is None:
            paths.append((name,))
        else:
            paths.extend((name, *sub) for sub in logged_paths(node.field.message_type, full=full))
    return paths


def view_leaves(view: dict, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Yields (path, value) for every leaf of a history view, with the unit and link type left out of the path"""
    for key, value in view.items():
        name = re.split(r'[\[<]', key)[0]
        if isinstance(value, dict):
            yield from view_leaves(value, (*path, name))
        elif isinstance(value, list):
            for element in value:
                yield from view_leaves(element, (*path, name))
        else:
            yield (*path, name), value


def test_logged_fields_are_plain():
    """
    No logged field is a list wrapper, a map, or a repeated leaf.
    logged_fields() and Codec.logged_view() do not handle them:
    a wrapper would need its `items` unwrapped, and a repeated Quantity or Link its metadata in the key.
    """
    for block_type, desc in block_descriptors().items():
        for path, field, _ in walk_fields(desc):
            if descriptors.options(field).logged:
                assert not descriptors.list_wrapper(field), (block_type, *path)
                assert not descriptors.is_map(field), (block_type, *path)
                assert field.message_type or field.label != FieldDescriptor.LABEL_REPEATED, (block_type, *path)


def test_logged_view_of_every_block_type():
    """
    The history view of a fully populated block has a number for every logged leaf.
    fixtures/logged_golden.json holds the block types that existed when it was made: this also covers new ones.
    """
    cdc = codec.CV.get()
    for entry in lookup.CV_OBJECTS.get():
        message = populate(entry.message_cls())
        payload = EncodedPayload(
            blockId=100,
            blockType=entry.type_int,
            content=b64encode(message.SerializeToString()).decode(),
        )
        content = cdc.decode_payload(payload).content
        leaves = dict(view_leaves(cdc.logged_view(entry.type_str, content, full=True)))
        assert set(leaves) == set(logged_paths(entry.message_cls.DESCRIPTOR)), entry.type_str
        for path, value in leaves.items():
            assert isinstance(value, int | float), (entry.type_str, *path, value)


def test_skip_changed_logged_paths():
    """History includes these only on full reads"""
    found = {
        (block_type, *path)
        for block_type, desc in block_descriptors().items()
        for path in set(logged_paths(desc)) - set(logged_paths(desc, full=False))
    }
    assert found == {
        ('SysInfo', 'uptime'),
        ('SysInfo', 'updatesPerSecond'),
        ('SysInfo', 'voltage5'),
        ('SysInfo', 'voltageExternal'),
        ('SysInfo', 'memoryFree'),
        ('SysInfo', 'memoryFreeContiguous'),
        ('SysInfo', 'memoryFreeLowest'),
        ('SysInfo', 'mainTaskStackFreeLowest'),
        ('WiFiSettings', 'signal'),
    }
    assert logged_paths(block_descriptors()['GpioModule']) == [
        ('analogChannels', 'resistance'),
        ('analogChannels', 'leadResistance'),
        ('analogChannels', 'bridgeResistance'),
        ('analogChannels', 'bridgeOutput'),
        ('baroPressure',),
    ]
