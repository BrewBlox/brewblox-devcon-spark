# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: EdgeCase.proto

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
  name='EdgeCase.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x0e\x45\x64geCase.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\xc3\x03\n\x08\x45\x64geCase\x12)\n\x08settings\x18\x01 \x01(\x0b\x32\x17.blox.EdgeCase.Settings\x12#\n\x05state\x18\x02 \x01(\x0b\x32\x14.blox.EdgeCase.State\x12\x14\n\x04link\x18\x03 \x01(\rB\x06\x8a\xb5\x18\x02\x18\x03\x12\x32\n\x0f\x61\x64\x64itionalLinks\x18\x04 \x03(\x0b\x32\x19.blox.EdgeCase.NestedLink\x12%\n\nlistValues\x18\x05 \x03(\x02\x42\x11\x8a\xb5\x18\x06\n\x04\x64\x65gC\x8a\xb5\x18\x03\x10\x80\x02\x12\x30\n\x06\x64\x65ltaV\x18\x06 \x01(\rB \x8a\xb5\x18\x15\n\x13\x64\x65lta_degC / second\x8a\xb5\x18\x03\x10\x80\x02\x1aL\n\x08Settings\x12\x17\n\x07\x61\x64\x64ress\x18\x01 \x01(\x06\x42\x06\x8a\xb5\x18\x02 \x01\x12\'\n\x06offset\x18\x02 \x01(\x11\x42\x17\x8a\xb5\x18\x0c\n\ndelta_degC\x8a\xb5\x18\x03\x10\x80\x02\x1a\x44\n\x05State\x12 \n\x05value\x18\x01 \x01(\x11\x42\x11\x8a\xb5\x18\x06\n\x04\x64\x65gC\x8a\xb5\x18\x03\x10\x80\x02\x12\x19\n\tconnected\x18\x02 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\x1a(\n\nNestedLink\x12\x1a\n\nconnection\x18\x01 \x01(\rB\x06\x8a\xb5\x18\x02\x18\x02:\x06\x92?\x03H\xa9\x46\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_EDGECASE_SETTINGS = _descriptor.Descriptor(
  name='Settings',
  full_name='blox.EdgeCase.Settings',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='address', full_name='blox.EdgeCase.Settings.address', index=0,
      number=1, type=6, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002 \001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='offset', full_name='blox.EdgeCase.Settings.offset', index=1,
      number=2, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\014\n\ndelta_degC\212\265\030\003\020\200\002'), file=DESCRIPTOR),
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
  ],
  serialized_start=310,
  serialized_end=386,
)

_EDGECASE_STATE = _descriptor.Descriptor(
  name='State',
  full_name='blox.EdgeCase.State',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='value', full_name='blox.EdgeCase.State.value', index=0,
      number=1, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\006\n\004degC\212\265\030\003\020\200\002'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='connected', full_name='blox.EdgeCase.State.connected', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002(\001'), file=DESCRIPTOR),
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
  ],
  serialized_start=388,
  serialized_end=456,
)

_EDGECASE_NESTEDLINK = _descriptor.Descriptor(
  name='NestedLink',
  full_name='blox.EdgeCase.NestedLink',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='connection', full_name='blox.EdgeCase.NestedLink.connection', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\002'), file=DESCRIPTOR),
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
  ],
  serialized_start=458,
  serialized_end=498,
)

_EDGECASE = _descriptor.Descriptor(
  name='EdgeCase',
  full_name='blox.EdgeCase',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='settings', full_name='blox.EdgeCase.settings', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='state', full_name='blox.EdgeCase.state', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='link', full_name='blox.EdgeCase.link', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\003'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='additionalLinks', full_name='blox.EdgeCase.additionalLinks', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='listValues', full_name='blox.EdgeCase.listValues', index=4,
      number=5, type=2, cpp_type=6, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\006\n\004degC\212\265\030\003\020\200\002'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='deltaV', full_name='blox.EdgeCase.deltaV', index=5,
      number=6, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\025\n\023delta_degC / second\212\265\030\003\020\200\002'), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_EDGECASE_SETTINGS, _EDGECASE_STATE, _EDGECASE_NESTEDLINK, ],
  enum_types=[
  ],
  serialized_options=_b('\222?\003H\251F'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=55,
  serialized_end=506,
)

_EDGECASE_SETTINGS.containing_type = _EDGECASE
_EDGECASE_STATE.containing_type = _EDGECASE
_EDGECASE_NESTEDLINK.containing_type = _EDGECASE
_EDGECASE.fields_by_name['settings'].message_type = _EDGECASE_SETTINGS
_EDGECASE.fields_by_name['state'].message_type = _EDGECASE_STATE
_EDGECASE.fields_by_name['additionalLinks'].message_type = _EDGECASE_NESTEDLINK
DESCRIPTOR.message_types_by_name['EdgeCase'] = _EDGECASE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

EdgeCase = _reflection.GeneratedProtocolMessageType('EdgeCase', (_message.Message,), dict(

  Settings = _reflection.GeneratedProtocolMessageType('Settings', (_message.Message,), dict(
    DESCRIPTOR = _EDGECASE_SETTINGS,
    __module__ = 'EdgeCase_pb2'
    # @@protoc_insertion_point(class_scope:blox.EdgeCase.Settings)
    ))
  ,

  State = _reflection.GeneratedProtocolMessageType('State', (_message.Message,), dict(
    DESCRIPTOR = _EDGECASE_STATE,
    __module__ = 'EdgeCase_pb2'
    # @@protoc_insertion_point(class_scope:blox.EdgeCase.State)
    ))
  ,

  NestedLink = _reflection.GeneratedProtocolMessageType('NestedLink', (_message.Message,), dict(
    DESCRIPTOR = _EDGECASE_NESTEDLINK,
    __module__ = 'EdgeCase_pb2'
    # @@protoc_insertion_point(class_scope:blox.EdgeCase.NestedLink)
    ))
  ,
  DESCRIPTOR = _EDGECASE,
  __module__ = 'EdgeCase_pb2'
  # @@protoc_insertion_point(class_scope:blox.EdgeCase)
  ))
_sym_db.RegisterMessage(EdgeCase)
_sym_db.RegisterMessage(EdgeCase.Settings)
_sym_db.RegisterMessage(EdgeCase.State)
_sym_db.RegisterMessage(EdgeCase.NestedLink)


_EDGECASE_SETTINGS.fields_by_name['address']._options = None
_EDGECASE_SETTINGS.fields_by_name['offset']._options = None
_EDGECASE_STATE.fields_by_name['value']._options = None
_EDGECASE_STATE.fields_by_name['connected']._options = None
_EDGECASE_NESTEDLINK.fields_by_name['connection']._options = None
_EDGECASE.fields_by_name['link']._options = None
_EDGECASE.fields_by_name['listValues']._options = None
_EDGECASE.fields_by_name['deltaV']._options = None
_EDGECASE._options = None
# @@protoc_insertion_point(module_scope)
