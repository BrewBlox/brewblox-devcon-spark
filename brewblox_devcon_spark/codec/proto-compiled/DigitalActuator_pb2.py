# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: DigitalActuator.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import Constraints_pb2 as Constraints__pb2
import IoArray_pb2 as IoArray__pb2
import Claims_pb2 as Claims__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15\x44igitalActuator.proto\x12\x14\x62lox.DigitalActuator\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x11\x43onstraints.proto\x1a\rIoArray.proto\x1a\x0c\x43laims.proto\"\x81\x05\n\x05\x42lock\x12\x1d\n\x08hwDevice\x18\x01 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\n\x12\x16\n\x07\x63hannel\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12\x37\n\x0bstoredState\x18\x0b \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateB\x06\x8a\xb5\x18\x02\x30\x01\x12:\n\x0c\x64\x65siredState\x18\x06 \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateB\x08\x8a\xb5\x18\x04(\x01\x30\x01\x12\x33\n\x05state\x18\x03 \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateB\x08\x8a\xb5\x18\x04(\x01\x30\x01\x12\x0e\n\x06invert\x18\x04 \x01(\x08\x12\x45\n\rconstrainedBy\x18\x05 \x01(\x0b\x32..blox.Constraints.DeprecatedDigitalConstraints\x12\x39\n\x0b\x63onstraints\x18\r \x01(\x0b\x32$.blox.Constraints.DigitalConstraints\x12H\n\x18transitionDurationPreset\x18\x07 \x01(\x0e\x32&.blox.IoArray.TransitionDurationPreset\x12,\n\x19transitionDurationSetting\x18\x08 \x01(\rB\t\x8a\xb5\x18\x05\x08\x03\x10\xe8\x07\x12,\n\x17transitionDurationValue\x18\t \x01(\rB\x0b\x8a\xb5\x18\x07\x08\x03\x10\xe8\x07(\x01\x12!\n\tclaimedBy\x18\n \x01(\rB\x0e\x92?\x02\x38\x10\x8a\xb5\x18\x05\x18\xff\x01(\x01\x12-\n\x0bsettingMode\x18\x0c \x01(\x0e\x32\x18.blox.Claims.SettingMode:\r\x8a\xb5\x18\t\x18\xbe\x02J\x04\x06\x15\x10\x11\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'DigitalActuator_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['hwDevice']._options = None
  _BLOCK.fields_by_name['hwDevice']._serialized_options = b'\222?\0028\020\212\265\030\002\030\n'
  _BLOCK.fields_by_name['channel']._options = None
  _BLOCK.fields_by_name['channel']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['storedState']._options = None
  _BLOCK.fields_by_name['storedState']._serialized_options = b'\212\265\030\0020\001'
  _BLOCK.fields_by_name['desiredState']._options = None
  _BLOCK.fields_by_name['desiredState']._serialized_options = b'\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['state']._options = None
  _BLOCK.fields_by_name['state']._serialized_options = b'\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['transitionDurationSetting']._options = None
  _BLOCK.fields_by_name['transitionDurationSetting']._serialized_options = b'\212\265\030\005\010\003\020\350\007'
  _BLOCK.fields_by_name['transitionDurationValue']._options = None
  _BLOCK.fields_by_name['transitionDurationValue']._serialized_options = b'\212\265\030\007\010\003\020\350\007(\001'
  _BLOCK.fields_by_name['claimedBy']._options = None
  _BLOCK.fields_by_name['claimedBy']._serialized_options = b'\222?\0028\020\212\265\030\005\030\377\001(\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\t\030\276\002J\004\006\025\020\021'
  _globals['_BLOCK']._serialized_start=126
  _globals['_BLOCK']._serialized_end=767
# @@protoc_insertion_point(module_scope)
