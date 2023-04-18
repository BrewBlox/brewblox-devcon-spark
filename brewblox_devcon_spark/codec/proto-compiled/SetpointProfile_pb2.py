# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: SetpointProfile.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='SetpointProfile.proto',
  package='blox.SetpointProfile',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x15SetpointProfile.proto\x12\x14\x62lox.SetpointProfile\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"b\n\x05Point\x12\x19\n\x04time\x18\x01 \x01(\rB\x0b\x8a\xb5\x18\x02\x08\x03\x92?\x02\x38 \x12)\n\x0btemperature\x18\x02 \x01(\x05\x42\x12\x8a\xb5\x18\x02\x08\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 H\x00\x42\x13\n\x11temperature_oneof\"\xe6\x01\n\x05\x42lock\x12+\n\x06points\x18\x01 \x03(\x0b\x32\x1b.blox.SetpointProfile.Point\x12\x0f\n\x07\x65nabled\x18\x03 \x01(\x08\x12\x1e\n\x08targetId\x18\x04 \x01(\rB\x0c\x8a\xb5\x18\x03\x18\xaf\x02\x92?\x02\x38\x10\x12/\n\x07setting\x18\x05 \x01(\x11\x42\x1e\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x02\x08\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x8a\xb5\x18\x02(\x01\x12\x1a\n\x05start\x18\x06 \x01(\rB\x0b\x8a\xb5\x18\x02X\x01\x92?\x02\x38 \x12#\n\x0e\x64rivenTargetId\x18Z \x01(\x08\x42\x0b\x8a\xb5\x18\x02H\x01\x92?\x02\x18\x03:\r\x8a\xb5\x18\x03\x18\xb7\x02\x8a\xb5\x18\x02H\x0f\x62\x06proto3'
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_POINT = _descriptor.Descriptor(
  name='Point',
  full_name='blox.SetpointProfile.Point',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='time', full_name='blox.SetpointProfile.Point.time', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='temperature', full_name='blox.SetpointProfile.Point.temperature', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\001\212\265\030\003\020\200 \222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
    _descriptor.OneofDescriptor(
      name='temperature_oneof', full_name='blox.SetpointProfile.Point.temperature_oneof',
      index=0, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
  ],
  serialized_start=77,
  serialized_end=175,
)


_BLOCK = _descriptor.Descriptor(
  name='Block',
  full_name='blox.SetpointProfile.Block',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='points', full_name='blox.SetpointProfile.Block.points', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='enabled', full_name='blox.SetpointProfile.Block.enabled', index=1,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='targetId', full_name='blox.SetpointProfile.Block.targetId', index=2,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\003\030\257\002\222?\0028\020', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='setting', full_name='blox.SetpointProfile.Block.setting', index=3,
      number=5, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\001\212\265\030\002\010\001\212\265\030\003\020\200 \222?\0028 \212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='start', full_name='blox.SetpointProfile.Block.start', index=4,
      number=6, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002X\001\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='drivenTargetId', full_name='blox.SetpointProfile.Block.drivenTargetId', index=5,
      number=90, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002H\001\222?\002\030\003', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\212\265\030\003\030\267\002\212\265\030\002H\017',
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=178,
  serialized_end=408,
)

_POINT.oneofs_by_name['temperature_oneof'].fields.append(
  _POINT.fields_by_name['temperature'])
_POINT.fields_by_name['temperature'].containing_oneof = _POINT.oneofs_by_name['temperature_oneof']
_BLOCK.fields_by_name['points'].message_type = _POINT
DESCRIPTOR.message_types_by_name['Point'] = _POINT
DESCRIPTOR.message_types_by_name['Block'] = _BLOCK
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Point = _reflection.GeneratedProtocolMessageType('Point', (_message.Message,), {
  'DESCRIPTOR' : _POINT,
  '__module__' : 'SetpointProfile_pb2'
  # @@protoc_insertion_point(class_scope:blox.SetpointProfile.Point)
  })
_sym_db.RegisterMessage(Point)

Block = _reflection.GeneratedProtocolMessageType('Block', (_message.Message,), {
  'DESCRIPTOR' : _BLOCK,
  '__module__' : 'SetpointProfile_pb2'
  # @@protoc_insertion_point(class_scope:blox.SetpointProfile.Block)
  })
_sym_db.RegisterMessage(Block)


_POINT.fields_by_name['time']._options = None
_POINT.fields_by_name['temperature']._options = None
_BLOCK.fields_by_name['targetId']._options = None
_BLOCK.fields_by_name['setting']._options = None
_BLOCK.fields_by_name['start']._options = None
_BLOCK.fields_by_name['drivenTargetId']._options = None
_BLOCK._options = None
# @@protoc_insertion_point(module_scope)
