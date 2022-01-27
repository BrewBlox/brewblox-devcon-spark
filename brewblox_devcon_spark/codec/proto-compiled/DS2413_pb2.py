# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: DS2413.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import IoArray_pb2 as IoArray__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='DS2413.proto',
  package='blox.DS2413',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x0c\x44S2413.proto\x12\x0b\x62lox.DS2413\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\xd2\x01\n\x05\x42lock\x12\x17\n\x07\x61\x64\x64ress\x18\x01 \x01(\x06\x42\x06\x8a\xb5\x18\x02 \x01\x12\x19\n\tconnected\x18\x06 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\x12(\n\x0coneWireBusId\x18\x08 \x01(\rB\x12\x8a\xb5\x18\x03\x18\x82\x02\x92?\x02\x38\x10\x8a\xb5\x18\x02(\x01\x12;\n\x08\x63hannels\x18\t \x03(\x0b\x32\x17.blox.IoArray.IoChannelB\x10\x92?\x02\x10\x02\x92?\x02x\x01\x8a\xb5\x18\x02(\x01\x12\x19\n\x04pins\x18Z \x01(\x08\x42\x0b\x8a\xb5\x18\x02H\x01\x92?\x02\x18\x03:\x13\x8a\xb5\x18\x03\x18\xbb\x02\x8a\xb5\x18\x02H\n\x8a\xb5\x18\x02H\t*G\n\tChannelId\x12\x14\n\x10\x44S2413_CHAN_NONE\x10\x00\x12\x11\n\rDS2413_CHAN_A\x10\x01\x12\x11\n\rDS2413_CHAN_B\x10\x02\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,IoArray__pb2.DESCRIPTOR,])

_CHANNELID = _descriptor.EnumDescriptor(
  name='ChannelId',
  full_name='blox.DS2413.ChannelId',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='DS2413_CHAN_NONE', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DS2413_CHAN_A', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DS2413_CHAN_B', index=2, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=287,
  serialized_end=358,
)
_sym_db.RegisterEnumDescriptor(_CHANNELID)

ChannelId = enum_type_wrapper.EnumTypeWrapper(_CHANNELID)
DS2413_CHAN_NONE = 0
DS2413_CHAN_A = 1
DS2413_CHAN_B = 2



_BLOCK = _descriptor.Descriptor(
  name='Block',
  full_name='blox.DS2413.Block',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='address', full_name='blox.DS2413.Block.address', index=0,
      number=1, type=6, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002 \001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='connected', full_name='blox.DS2413.Block.connected', index=1,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='oneWireBusId', full_name='blox.DS2413.Block.oneWireBusId', index=2,
      number=8, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\003\030\202\002\222?\0028\020\212\265\030\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='channels', full_name='blox.DS2413.Block.channels', index=3,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\002\020\002\222?\002x\001\212\265\030\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='pins', full_name='blox.DS2413.Block.pins', index=4,
      number=90, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002H\001\222?\002\030\003'), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=_b('\212\265\030\003\030\273\002\212\265\030\002H\n\212\265\030\002H\t'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=75,
  serialized_end=285,
)

_BLOCK.fields_by_name['channels'].message_type = IoArray__pb2._IOCHANNEL
DESCRIPTOR.message_types_by_name['Block'] = _BLOCK
DESCRIPTOR.enum_types_by_name['ChannelId'] = _CHANNELID
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Block = _reflection.GeneratedProtocolMessageType('Block', (_message.Message,), dict(
  DESCRIPTOR = _BLOCK,
  __module__ = 'DS2413_pb2'
  # @@protoc_insertion_point(class_scope:blox.DS2413.Block)
  ))
_sym_db.RegisterMessage(Block)


_BLOCK.fields_by_name['address']._options = None
_BLOCK.fields_by_name['connected']._options = None
_BLOCK.fields_by_name['oneWireBusId']._options = None
_BLOCK.fields_by_name['channels']._options = None
_BLOCK.fields_by_name['pins']._options = None
_BLOCK._options = None
# @@protoc_insertion_point(module_scope)
