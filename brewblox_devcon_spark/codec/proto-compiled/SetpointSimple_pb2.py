# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: SetpointSimple.proto

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
  name='SetpointSimple.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x14SetpointSimple.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"=\n\x0eSetpointSimple\x12#\n\x07setting\x18\x01 \x01(\x11\x42\x12\x8a\xb5\x18\x02\x08\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 :\x06\x92?\x03H\xac\x02\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_SETPOINTSIMPLE = _descriptor.Descriptor(
  name='SetpointSimple',
  full_name='blox.SetpointSimple',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='setting', full_name='blox.SetpointSimple.setting', index=0,
      number=1, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\010\001\212\265\030\003\020\200 \222?\0028 '), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=_b('\222?\003H\254\002'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=60,
  serialized_end=121,
)

DESCRIPTOR.message_types_by_name['SetpointSimple'] = _SETPOINTSIMPLE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

SetpointSimple = _reflection.GeneratedProtocolMessageType('SetpointSimple', (_message.Message,), dict(
  DESCRIPTOR = _SETPOINTSIMPLE,
  __module__ = 'SetpointSimple_pb2'
  # @@protoc_insertion_point(class_scope:blox.SetpointSimple)
  ))
_sym_db.RegisterMessage(SetpointSimple)


_SETPOINTSIMPLE.fields_by_name['setting']._options = None
_SETPOINTSIMPLE._options = None
# @@protoc_insertion_point(module_scope)