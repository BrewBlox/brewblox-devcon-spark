# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: IoArray.proto

from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='IoArray.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=b'\n\rIoArray.proto\x12\x04\x62lox\"S\n\tIoChannel\x12#\n\x06\x63onfig\x18\x01 \x01(\x0e\x32\x13.blox.ChannelConfig\x12!\n\x05state\x18\x02 \x01(\x0e\x32\x12.blox.DigitalState*G\n\x0c\x44igitalState\x12\x12\n\x0eSTATE_INACTIVE\x10\x00\x12\x10\n\x0cSTATE_ACTIVE\x10\x01\x12\x11\n\rSTATE_UNKNOWN\x10\x02*}\n\rChannelConfig\x12\x12\n\x0e\x43HANNEL_UNUSED\x10\x00\x12\x16\n\x12\x43HANNEL_ACTIVE_LOW\x10\x01\x12\x17\n\x13\x43HANNEL_ACTIVE_HIGH\x10\x02\x12\x11\n\rCHANNEL_INPUT\x10\n\x12\x14\n\x0f\x43HANNEL_UNKNOWN\x10\xff\x01\x62\x06proto3'
)

_DIGITALSTATE = _descriptor.EnumDescriptor(
  name='DigitalState',
  full_name='blox.DigitalState',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='STATE_INACTIVE', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STATE_ACTIVE', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STATE_UNKNOWN', index=2, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=108,
  serialized_end=179,
)
_sym_db.RegisterEnumDescriptor(_DIGITALSTATE)

DigitalState = enum_type_wrapper.EnumTypeWrapper(_DIGITALSTATE)
_CHANNELCONFIG = _descriptor.EnumDescriptor(
  name='ChannelConfig',
  full_name='blox.ChannelConfig',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='CHANNEL_UNUSED', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHANNEL_ACTIVE_LOW', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHANNEL_ACTIVE_HIGH', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHANNEL_INPUT', index=3, number=10,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHANNEL_UNKNOWN', index=4, number=255,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=181,
  serialized_end=306,
)
_sym_db.RegisterEnumDescriptor(_CHANNELCONFIG)

ChannelConfig = enum_type_wrapper.EnumTypeWrapper(_CHANNELCONFIG)
STATE_INACTIVE = 0
STATE_ACTIVE = 1
STATE_UNKNOWN = 2
CHANNEL_UNUSED = 0
CHANNEL_ACTIVE_LOW = 1
CHANNEL_ACTIVE_HIGH = 2
CHANNEL_INPUT = 10
CHANNEL_UNKNOWN = 255



_IOCHANNEL = _descriptor.Descriptor(
  name='IoChannel',
  full_name='blox.IoChannel',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='config', full_name='blox.IoChannel.config', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='state', full_name='blox.IoChannel.state', index=1,
      number=2, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
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
  serialized_start=23,
  serialized_end=106,
)

_IOCHANNEL.fields_by_name['config'].enum_type = _CHANNELCONFIG
_IOCHANNEL.fields_by_name['state'].enum_type = _DIGITALSTATE
DESCRIPTOR.message_types_by_name['IoChannel'] = _IOCHANNEL
DESCRIPTOR.enum_types_by_name['DigitalState'] = _DIGITALSTATE
DESCRIPTOR.enum_types_by_name['ChannelConfig'] = _CHANNELCONFIG
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

IoChannel = _reflection.GeneratedProtocolMessageType('IoChannel', (_message.Message,), {
  'DESCRIPTOR' : _IOCHANNEL,
  '__module__' : 'IoArray_pb2'
  # @@protoc_insertion_point(class_scope:blox.IoChannel)
  })
_sym_db.RegisterMessage(IoChannel)


# @@protoc_insertion_point(module_scope)
