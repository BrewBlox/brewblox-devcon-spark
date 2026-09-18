"""
Guards for the manual step in adding a block type or unit.

`invoke compile-proto` writes a _pb2.py file, but the codec lookup table is
built from the import list in codec/pb2.py. Forgetting that second step is
invisible until runtime, where it surfaces as a 400 'No codec entry found'.
The proto submodule is not checked out in CI, so these checks are derived
from the compiled descriptors rather than the .proto sources.
"""

import importlib
from pathlib import Path

import pytest

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import lookup, pb2, unit_conversion
from brewblox_devcon_spark.models import CrossPlatformResetReason

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
