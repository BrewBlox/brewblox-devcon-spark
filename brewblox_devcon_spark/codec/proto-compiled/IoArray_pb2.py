# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: IoArray.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import nanopb_pb2 as nanopb__pb2
import brewblox_pb2 as brewblox__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='IoArray.proto',
  package='blox.IoArray',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\rIoArray.proto\x12\x0c\x62lox.IoArray\x1a\x0cnanopb.proto\x1a\x0e\x62rewblox.proto\"A\n\tIoChannel\x12\x11\n\x02id\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08\x12!\n\x0c\x63\x61pabilities\x18\x02 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02P\x01*\x85\x01\n\x0c\x44igitalState\x12\x12\n\x0eSTATE_INACTIVE\x10\x00\x12\x10\n\x0cSTATE_ACTIVE\x10\x01\x12\x11\n\rSTATE_UNKNOWN\x10\x02\x12\x11\n\rSTATE_REVERSE\x10\x03\x12\x0c\n\x08Inactive\x10\x00\x12\n\n\x06\x41\x63tive\x10\x01\x12\x0b\n\x07Unknown\x10\x02\x1a\x02\x10\x01*U\n\x0fSoftTransitions\x12\n\n\x06ST_OFF\x10\x00\x12\x0b\n\x07ST_FAST\x10\x01\x12\r\n\tST_MEDIUM\x10\x02\x12\x0b\n\x07ST_SLOW\x10\x03\x12\r\n\tST_CUSTOM\x10\x04*\xe9\x01\n\x13\x43hannelCapabilities\x12\x16\n\x12\x43HAN_SUPPORTS_NONE\x10\x00\x12 \n\x1c\x43HAN_SUPPORTS_DIGITAL_OUTPUT\x10\x01\x12\x1b\n\x17\x43HAN_SUPPORTS_PWM_100HZ\x10\x02\x12\x1b\n\x17\x43HAN_SUPPORTS_PWM_200HZ\x10\x04\x12\x1c\n\x18\x43HAN_SUPPORTS_PWM_2000HZ\x10\x08\x12\x1f\n\x1b\x43HAN_SUPPORTS_BIDIRECTIONAL\x10\x10\x12\x1f\n\x1b\x43HAN_SUPPORTS_DIGITAL_INPUT\x10 b\x06proto3')
  ,
  dependencies=[nanopb__pb2.DESCRIPTOR,brewblox__pb2.DESCRIPTOR,])

_DIGITALSTATE = _descriptor.EnumDescriptor(
  name='DigitalState',
  full_name='blox.IoArray.DigitalState',
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
    _descriptor.EnumValueDescriptor(
      name='STATE_REVERSE', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Inactive', index=4, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Active', index=5, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Unknown', index=6, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=_b('\020\001'),
  serialized_start=129,
  serialized_end=262,
)
_sym_db.RegisterEnumDescriptor(_DIGITALSTATE)

DigitalState = enum_type_wrapper.EnumTypeWrapper(_DIGITALSTATE)
_SOFTTRANSITIONS = _descriptor.EnumDescriptor(
  name='SoftTransitions',
  full_name='blox.IoArray.SoftTransitions',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='ST_OFF', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ST_FAST', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ST_MEDIUM', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ST_SLOW', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ST_CUSTOM', index=4, number=4,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=264,
  serialized_end=349,
)
_sym_db.RegisterEnumDescriptor(_SOFTTRANSITIONS)

SoftTransitions = enum_type_wrapper.EnumTypeWrapper(_SOFTTRANSITIONS)
_CHANNELCAPABILITIES = _descriptor.EnumDescriptor(
  name='ChannelCapabilities',
  full_name='blox.IoArray.ChannelCapabilities',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_NONE', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_DIGITAL_OUTPUT', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_PWM_100HZ', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_PWM_200HZ', index=3, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_PWM_2000HZ', index=4, number=8,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_BIDIRECTIONAL', index=5, number=16,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CHAN_SUPPORTS_DIGITAL_INPUT', index=6, number=32,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=352,
  serialized_end=585,
)
_sym_db.RegisterEnumDescriptor(_CHANNELCAPABILITIES)

ChannelCapabilities = enum_type_wrapper.EnumTypeWrapper(_CHANNELCAPABILITIES)
STATE_INACTIVE = 0
STATE_ACTIVE = 1
STATE_UNKNOWN = 2
STATE_REVERSE = 3
Inactive = 0
Active = 1
Unknown = 2
ST_OFF = 0
ST_FAST = 1
ST_MEDIUM = 2
ST_SLOW = 3
ST_CUSTOM = 4
CHAN_SUPPORTS_NONE = 0
CHAN_SUPPORTS_DIGITAL_OUTPUT = 1
CHAN_SUPPORTS_PWM_100HZ = 2
CHAN_SUPPORTS_PWM_200HZ = 4
CHAN_SUPPORTS_PWM_2000HZ = 8
CHAN_SUPPORTS_BIDIRECTIONAL = 16
CHAN_SUPPORTS_DIGITAL_INPUT = 32



_IOCHANNEL = _descriptor.Descriptor(
  name='IoChannel',
  full_name='blox.IoArray.IoChannel',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='blox.IoArray.IoChannel.id', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\0028\010'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='capabilities', full_name='blox.IoArray.IoChannel.capabilities', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\0028\020\212\265\030\002P\001'), file=DESCRIPTOR),
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
  serialized_start=61,
  serialized_end=126,
)

DESCRIPTOR.message_types_by_name['IoChannel'] = _IOCHANNEL
DESCRIPTOR.enum_types_by_name['DigitalState'] = _DIGITALSTATE
DESCRIPTOR.enum_types_by_name['SoftTransitions'] = _SOFTTRANSITIONS
DESCRIPTOR.enum_types_by_name['ChannelCapabilities'] = _CHANNELCAPABILITIES
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

IoChannel = _reflection.GeneratedProtocolMessageType('IoChannel', (_message.Message,), dict(
  DESCRIPTOR = _IOCHANNEL,
  __module__ = 'IoArray_pb2'
  # @@protoc_insertion_point(class_scope:blox.IoArray.IoChannel)
  ))
_sym_db.RegisterMessage(IoChannel)


_DIGITALSTATE._options = None
_IOCHANNEL.fields_by_name['id']._options = None
_IOCHANNEL.fields_by_name['capabilities']._options = None
# @@protoc_insertion_point(module_scope)
