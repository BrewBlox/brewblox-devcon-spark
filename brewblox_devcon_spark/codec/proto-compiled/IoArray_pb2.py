# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: IoArray.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='IoArray.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\rIoArray.proto\x12\x04\x62lox\x1a\x0cnanopb.proto\"\x1e\n\tIoChannel\x12\x11\n\x02id\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08*\x85\x01\n\x0c\x44igitalState\x12\x12\n\x0eSTATE_INACTIVE\x10\x00\x12\x10\n\x0cSTATE_ACTIVE\x10\x01\x12\x11\n\rSTATE_UNKNOWN\x10\x02\x12\x11\n\rSTATE_REVERSE\x10\x03\x12\x0c\n\x08Inactive\x10\x00\x12\n\n\x06\x41\x63tive\x10\x01\x12\x0b\n\x07Unknown\x10\x02\x1a\x02\x10\x01\x62\x06proto3'
  ,
  dependencies=[nanopb__pb2.DESCRIPTOR,])

_DIGITALSTATE = _descriptor.EnumDescriptor(
  name='DigitalState',
  full_name='blox.DigitalState',
  filename=None,
  file=DESCRIPTOR,
  create_key=_descriptor._internal_create_key,
  values=[
    _descriptor.EnumValueDescriptor(
      name='STATE_INACTIVE', index=0, number=0,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='STATE_ACTIVE', index=1, number=1,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='STATE_UNKNOWN', index=2, number=2,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='STATE_REVERSE', index=3, number=3,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='Inactive', index=4, number=0,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='Active', index=5, number=1,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='Unknown', index=6, number=2,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
  ],
  containing_type=None,
  serialized_options=b'\020\001',
  serialized_start=70,
  serialized_end=203,
)
_sym_db.RegisterEnumDescriptor(_DIGITALSTATE)

DigitalState = enum_type_wrapper.EnumTypeWrapper(_DIGITALSTATE)
STATE_INACTIVE = 0
STATE_ACTIVE = 1
STATE_UNKNOWN = 2
STATE_REVERSE = 3
Inactive = 0
Active = 1
Unknown = 2



_IOCHANNEL = _descriptor.Descriptor(
  name='IoChannel',
  full_name='blox.IoChannel',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='blox.IoChannel.id', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\222?\0028\010', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=37,
  serialized_end=67,
)

DESCRIPTOR.message_types_by_name['IoChannel'] = _IOCHANNEL
DESCRIPTOR.enum_types_by_name['DigitalState'] = _DIGITALSTATE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

IoChannel = _reflection.GeneratedProtocolMessageType('IoChannel', (_message.Message,), {
  'DESCRIPTOR' : _IOCHANNEL,
  '__module__' : 'IoArray_pb2'
  # @@protoc_insertion_point(class_scope:blox.IoChannel)
  })
_sym_db.RegisterMessage(IoChannel)


_DIGITALSTATE._options = None
_IOCHANNEL.fields_by_name['id']._options = None
# @@protoc_insertion_point(module_scope)
