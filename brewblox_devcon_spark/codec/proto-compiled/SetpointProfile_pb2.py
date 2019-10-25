# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: SetpointProfile.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
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
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x15SetpointProfile.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\x89\x02\n\x0fSetpointProfile\x12+\n\x06points\x18\x01 \x03(\x0b\x32\x1b.blox.SetpointProfile.Point\x12\x0f\n\x07\x65nabled\x18\x03 \x01(\x08\x12\x1d\n\x08targetId\x18\x04 \x01(\rB\x0b\x9a?\x03\x18\xaf\x02\x92?\x02\x38\x10\x12-\n\x0e\x64rivenTargetId\x18\x05 \x01(\rB\x15\x9a?\x03\x18\xaf\x02\x9a?\x02@\x01\x92?\x02\x38\x10\x9a?\x02(\x01\x12\r\n\x05start\x18\x06 \x01(\r\x1aS\n\x05Point\x12\x0c\n\x04time\x18\x01 \x01(\r\x12\'\n\x0btemperature\x18\x02 \x01(\x05\x42\x10\x9a?\x02\x08\x01\x9a?\x03\x10\x80 \x92?\x02\x38 H\x00\x42\x13\n\x11temperature_oneof:\x06\x9a?\x03\x18\xb7\x02\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_SETPOINTPROFILE_POINT = _descriptor.Descriptor(
  name='Point',
  full_name='blox.SetpointProfile.Point',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='time', full_name='blox.SetpointProfile.Point.time', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='temperature', full_name='blox.SetpointProfile.Point.temperature', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\232?\002\010\001\232?\003\020\200 \222?\0028 '), file=DESCRIPTOR),
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
      index=0, containing_type=None, fields=[]),
  ],
  serialized_start=236,
  serialized_end=319,
)

_SETPOINTPROFILE = _descriptor.Descriptor(
  name='SetpointProfile',
  full_name='blox.SetpointProfile',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='points', full_name='blox.SetpointProfile.points', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='enabled', full_name='blox.SetpointProfile.enabled', index=1,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='targetId', full_name='blox.SetpointProfile.targetId', index=2,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\232?\003\030\257\002\222?\0028\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='drivenTargetId', full_name='blox.SetpointProfile.drivenTargetId', index=3,
      number=5, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\232?\003\030\257\002\232?\002@\001\222?\0028\020\232?\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='start', full_name='blox.SetpointProfile.start', index=4,
      number=6, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_SETPOINTPROFILE_POINT, ],
  enum_types=[
  ],
  serialized_options=_b('\232?\003\030\267\002'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=62,
  serialized_end=327,
)

_SETPOINTPROFILE_POINT.containing_type = _SETPOINTPROFILE
_SETPOINTPROFILE_POINT.oneofs_by_name['temperature_oneof'].fields.append(
  _SETPOINTPROFILE_POINT.fields_by_name['temperature'])
_SETPOINTPROFILE_POINT.fields_by_name['temperature'].containing_oneof = _SETPOINTPROFILE_POINT.oneofs_by_name['temperature_oneof']
_SETPOINTPROFILE.fields_by_name['points'].message_type = _SETPOINTPROFILE_POINT
DESCRIPTOR.message_types_by_name['SetpointProfile'] = _SETPOINTPROFILE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

SetpointProfile = _reflection.GeneratedProtocolMessageType('SetpointProfile', (_message.Message,), dict(

  Point = _reflection.GeneratedProtocolMessageType('Point', (_message.Message,), dict(
    DESCRIPTOR = _SETPOINTPROFILE_POINT,
    __module__ = 'SetpointProfile_pb2'
    # @@protoc_insertion_point(class_scope:blox.SetpointProfile.Point)
    ))
  ,
  DESCRIPTOR = _SETPOINTPROFILE,
  __module__ = 'SetpointProfile_pb2'
  # @@protoc_insertion_point(class_scope:blox.SetpointProfile)
  ))
_sym_db.RegisterMessage(SetpointProfile)
_sym_db.RegisterMessage(SetpointProfile.Point)


_SETPOINTPROFILE_POINT.fields_by_name['temperature']._options = None
_SETPOINTPROFILE.fields_by_name['targetId']._options = None
_SETPOINTPROFILE.fields_by_name['drivenTargetId']._options = None
_SETPOINTPROFILE._options = None
# @@protoc_insertion_point(module_scope)
