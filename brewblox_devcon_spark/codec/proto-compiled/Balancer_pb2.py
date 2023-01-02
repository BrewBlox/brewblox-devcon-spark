# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Balancer.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='Balancer.proto',
  package='blox.Balancer',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x0e\x42\x61lancer.proto\x12\rblox.Balancer\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\x90\x01\n\x10\x42\x61lancedActuator\x12$\n\x02id\x18\x01 \x01(\rB\x18\x8a\xb5\x18\x03\x18\xff\x01\x8a\xb5\x18\x02\x30\x00\x8a\xb5\x18\x02(\x01\x92?\x02\x38\x10\x12+\n\trequested\x18\x02 \x01(\x11\x42\x18\x8a\xb5\x18\x02\x30\x00\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x8a\xb5\x18\x02(\x01\x12)\n\x07granted\x18\x03 \x01(\x11\x42\x18\x8a\xb5\x18\x02\x30\x00\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x8a\xb5\x18\x02(\x01\"V\n\x05\x42lock\x12>\n\x07\x63lients\x18\x01 \x03(\x0b\x32\x1f.blox.Balancer.BalancedActuatorB\x0c\x8a\xb5\x18\x02\x30\x00\x8a\xb5\x18\x02(\x01:\r\x8a\xb5\x18\x03\x18\xb5\x02\x8a\xb5\x18\x02H\x07\x62\x06proto3'
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_BALANCEDACTUATOR = _descriptor.Descriptor(
  name='BalancedActuator',
  full_name='blox.Balancer.BalancedActuator',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='blox.Balancer.BalancedActuator.id', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\003\030\377\001\212\265\030\0020\000\212\265\030\002(\001\222?\0028\020', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='requested', full_name='blox.Balancer.BalancedActuator.requested', index=1,
      number=2, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\000\212\265\030\003\020\200 \222?\0028 \212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='granted', full_name='blox.Balancer.BalancedActuator.granted', index=2,
      number=3, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\000\212\265\030\003\020\200 \222?\0028 \212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=64,
  serialized_end=208,
)


_BLOCK = _descriptor.Descriptor(
  name='Block',
  full_name='blox.Balancer.Block',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='clients', full_name='blox.Balancer.Block.clients', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\000\212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\212\265\030\003\030\265\002\212\265\030\002H\007',
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=210,
  serialized_end=296,
)

_BLOCK.fields_by_name['clients'].message_type = _BALANCEDACTUATOR
DESCRIPTOR.message_types_by_name['BalancedActuator'] = _BALANCEDACTUATOR
DESCRIPTOR.message_types_by_name['Block'] = _BLOCK
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

BalancedActuator = _reflection.GeneratedProtocolMessageType('BalancedActuator', (_message.Message,), {
  'DESCRIPTOR' : _BALANCEDACTUATOR,
  '__module__' : 'Balancer_pb2'
  # @@protoc_insertion_point(class_scope:blox.Balancer.BalancedActuator)
  })
_sym_db.RegisterMessage(BalancedActuator)

Block = _reflection.GeneratedProtocolMessageType('Block', (_message.Message,), {
  'DESCRIPTOR' : _BLOCK,
  '__module__' : 'Balancer_pb2'
  # @@protoc_insertion_point(class_scope:blox.Balancer.Block)
  })
_sym_db.RegisterMessage(Block)


_BALANCEDACTUATOR.fields_by_name['id']._options = None
_BALANCEDACTUATOR.fields_by_name['requested']._options = None
_BALANCEDACTUATOR.fields_by_name['granted']._options = None
_BLOCK.fields_by_name['clients']._options = None
_BLOCK._options = None
# @@protoc_insertion_point(module_scope)
