# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Constraints.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='Constraints.proto',
  package='blox.Constraints',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x11\x43onstraints.proto\x12\x10\x62lox.Constraints\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"d\n\x08\x42\x61lanced\x12\x1f\n\nbalancerId\x18\x01 \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x07\x92?\x02\x38\x10\x12\x1e\n\x07granted\x18\x02 \x01(\rB\r\x8a\xb5\x18\x03\x10\x80 \x8a\xb5\x18\x02(\x01\x12\x17\n\x02id\x18\x03 \x01(\rB\x0b\x8a\xb5\x18\x02(\x01\x92?\x02\x38\x08\"\x93\x01\n\x07Mutexed\x12\x1c\n\x07mutexId\x18\x01 \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x08\x92?\x02\x38\x10\x12)\n\rextraHoldTime\x18\x02 \x01(\rB\x12\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x92?\x02\x38 \x12\x17\n\x07hasLock\x18\x04 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\x12&\n\x11hasCustomHoldTime\x18Z \x01(\x08\x42\x0b\x8a\xb5\x18\x02H\x01\x92?\x02\x18\x03\"\xa4\x01\n\x10\x41nalogConstraint\x12\x1b\n\x03min\x18\x01 \x01(\x11\x42\x0c\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 H\x00\x12\x1b\n\x03max\x18\x02 \x01(\x11\x42\x0c\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 H\x00\x12.\n\x08\x62\x61lanced\x18\x03 \x01(\x0b\x32\x1a.blox.Constraints.BalancedH\x00\x12\x18\n\x08limiting\x18\x64 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\x42\x0c\n\nconstraint\"S\n\x11\x41nalogConstraints\x12>\n\x0b\x63onstraints\x18\x01 \x03(\x0b\x32\".blox.Constraints.AnalogConstraintB\x05\x92?\x02\x10\x08\"\xd7\x02\n\x11\x44igitalConstraint\x12$\n\x06minOff\x18\x01 \x01(\rB\x12\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x92?\x02\x38 H\x00\x12#\n\x05minOn\x18\x02 \x01(\rB\x12\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x92?\x02\x38 H\x00\x12,\n\x07mutexed\x18\x04 \x01(\x0b\x32\x19.blox.Constraints.MutexedH\x00\x12(\n\ndelayedOff\x18\x05 \x01(\rB\x12\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x92?\x02\x38 H\x00\x12\'\n\tdelayedOn\x18\x06 \x01(\rB\x12\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x92?\x02\x38 H\x00\x12\x1c\n\x05mutex\x18\x03 \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x08\x92?\x02\x38\x10H\x00\x12\x1d\n\x08limiting\x18\x64 \x01(\rB\x0b\x8a\xb5\x18\x02H\x01\x92?\x02\x18\x03\x12+\n\tremaining\x18\x65 \x01(\rB\x18\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x8a\xb5\x18\x02(\x01\x92?\x02\x38 B\x0c\n\nconstraint\"U\n\x12\x44igitalConstraints\x12?\n\x0b\x63onstraints\x18\x01 \x03(\x0b\x32#.blox.Constraints.DigitalConstraintB\x05\x92?\x02\x10\x08\x62\x06proto3'
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_BALANCED = _descriptor.Descriptor(
  name='Balanced',
  full_name='blox.Constraints.Balanced',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='balancerId', full_name='blox.Constraints.Balanced.balancerId', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\030\007\222?\0028\020', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='granted', full_name='blox.Constraints.Balanced.granted', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\003\020\200 \212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='id', full_name='blox.Constraints.Balanced.id', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002(\001\222?\0028\010', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=69,
  serialized_end=169,
)


_MUTEXED = _descriptor.Descriptor(
  name='Mutexed',
  full_name='blox.Constraints.Mutexed',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='mutexId', full_name='blox.Constraints.Mutexed.mutexId', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\030\010\222?\0028\020', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='extraHoldTime', full_name='blox.Constraints.Mutexed.extraHoldTime', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='hasLock', full_name='blox.Constraints.Mutexed.hasLock', index=2,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='hasCustomHoldTime', full_name='blox.Constraints.Mutexed.hasCustomHoldTime', index=3,
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
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=172,
  serialized_end=319,
)


_ANALOGCONSTRAINT = _descriptor.Descriptor(
  name='AnalogConstraint',
  full_name='blox.Constraints.AnalogConstraint',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='min', full_name='blox.Constraints.AnalogConstraint.min', index=0,
      number=1, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\003\020\200 \222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='max', full_name='blox.Constraints.AnalogConstraint.max', index=1,
      number=2, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\003\020\200 \222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='balanced', full_name='blox.Constraints.AnalogConstraint.balanced', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='limiting', full_name='blox.Constraints.AnalogConstraint.limiting', index=3,
      number=100, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
      name='constraint', full_name='blox.Constraints.AnalogConstraint.constraint',
      index=0, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
  ],
  serialized_start=322,
  serialized_end=486,
)


_ANALOGCONSTRAINTS = _descriptor.Descriptor(
  name='AnalogConstraints',
  full_name='blox.Constraints.AnalogConstraints',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='constraints', full_name='blox.Constraints.AnalogConstraints.constraints', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\222?\002\020\010', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=488,
  serialized_end=571,
)


_DIGITALCONSTRAINT = _descriptor.Descriptor(
  name='DigitalConstraint',
  full_name='blox.Constraints.DigitalConstraint',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='minOff', full_name='blox.Constraints.DigitalConstraint.minOff', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='minOn', full_name='blox.Constraints.DigitalConstraint.minOn', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='mutexed', full_name='blox.Constraints.DigitalConstraint.mutexed', index=2,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='delayedOff', full_name='blox.Constraints.DigitalConstraint.delayedOff', index=3,
      number=5, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='delayedOn', full_name='blox.Constraints.DigitalConstraint.delayedOn', index=4,
      number=6, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='mutex', full_name='blox.Constraints.DigitalConstraint.mutex', index=5,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\030\010\222?\0028\020', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='limiting', full_name='blox.Constraints.DigitalConstraint.limiting', index=6,
      number=100, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002H\001\222?\002\030\003', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='remaining', full_name='blox.Constraints.DigitalConstraint.remaining', index=7,
      number=101, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007\212\265\030\002(\001\222?\0028 ', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
      name='constraint', full_name='blox.Constraints.DigitalConstraint.constraint',
      index=0, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
  ],
  serialized_start=574,
  serialized_end=917,
)


_DIGITALCONSTRAINTS = _descriptor.Descriptor(
  name='DigitalConstraints',
  full_name='blox.Constraints.DigitalConstraints',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='constraints', full_name='blox.Constraints.DigitalConstraints.constraints', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\222?\002\020\010', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=919,
  serialized_end=1004,
)

_ANALOGCONSTRAINT.fields_by_name['balanced'].message_type = _BALANCED
_ANALOGCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _ANALOGCONSTRAINT.fields_by_name['min'])
_ANALOGCONSTRAINT.fields_by_name['min'].containing_oneof = _ANALOGCONSTRAINT.oneofs_by_name['constraint']
_ANALOGCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _ANALOGCONSTRAINT.fields_by_name['max'])
_ANALOGCONSTRAINT.fields_by_name['max'].containing_oneof = _ANALOGCONSTRAINT.oneofs_by_name['constraint']
_ANALOGCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _ANALOGCONSTRAINT.fields_by_name['balanced'])
_ANALOGCONSTRAINT.fields_by_name['balanced'].containing_oneof = _ANALOGCONSTRAINT.oneofs_by_name['constraint']
_ANALOGCONSTRAINTS.fields_by_name['constraints'].message_type = _ANALOGCONSTRAINT
_DIGITALCONSTRAINT.fields_by_name['mutexed'].message_type = _MUTEXED
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['minOff'])
_DIGITALCONSTRAINT.fields_by_name['minOff'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['minOn'])
_DIGITALCONSTRAINT.fields_by_name['minOn'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['mutexed'])
_DIGITALCONSTRAINT.fields_by_name['mutexed'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['delayedOff'])
_DIGITALCONSTRAINT.fields_by_name['delayedOff'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['delayedOn'])
_DIGITALCONSTRAINT.fields_by_name['delayedOn'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINT.oneofs_by_name['constraint'].fields.append(
  _DIGITALCONSTRAINT.fields_by_name['mutex'])
_DIGITALCONSTRAINT.fields_by_name['mutex'].containing_oneof = _DIGITALCONSTRAINT.oneofs_by_name['constraint']
_DIGITALCONSTRAINTS.fields_by_name['constraints'].message_type = _DIGITALCONSTRAINT
DESCRIPTOR.message_types_by_name['Balanced'] = _BALANCED
DESCRIPTOR.message_types_by_name['Mutexed'] = _MUTEXED
DESCRIPTOR.message_types_by_name['AnalogConstraint'] = _ANALOGCONSTRAINT
DESCRIPTOR.message_types_by_name['AnalogConstraints'] = _ANALOGCONSTRAINTS
DESCRIPTOR.message_types_by_name['DigitalConstraint'] = _DIGITALCONSTRAINT
DESCRIPTOR.message_types_by_name['DigitalConstraints'] = _DIGITALCONSTRAINTS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Balanced = _reflection.GeneratedProtocolMessageType('Balanced', (_message.Message,), {
  'DESCRIPTOR' : _BALANCED,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.Balanced)
  })
_sym_db.RegisterMessage(Balanced)

Mutexed = _reflection.GeneratedProtocolMessageType('Mutexed', (_message.Message,), {
  'DESCRIPTOR' : _MUTEXED,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.Mutexed)
  })
_sym_db.RegisterMessage(Mutexed)

AnalogConstraint = _reflection.GeneratedProtocolMessageType('AnalogConstraint', (_message.Message,), {
  'DESCRIPTOR' : _ANALOGCONSTRAINT,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.AnalogConstraint)
  })
_sym_db.RegisterMessage(AnalogConstraint)

AnalogConstraints = _reflection.GeneratedProtocolMessageType('AnalogConstraints', (_message.Message,), {
  'DESCRIPTOR' : _ANALOGCONSTRAINTS,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.AnalogConstraints)
  })
_sym_db.RegisterMessage(AnalogConstraints)

DigitalConstraint = _reflection.GeneratedProtocolMessageType('DigitalConstraint', (_message.Message,), {
  'DESCRIPTOR' : _DIGITALCONSTRAINT,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.DigitalConstraint)
  })
_sym_db.RegisterMessage(DigitalConstraint)

DigitalConstraints = _reflection.GeneratedProtocolMessageType('DigitalConstraints', (_message.Message,), {
  'DESCRIPTOR' : _DIGITALCONSTRAINTS,
  '__module__' : 'Constraints_pb2'
  # @@protoc_insertion_point(class_scope:blox.Constraints.DigitalConstraints)
  })
_sym_db.RegisterMessage(DigitalConstraints)


_BALANCED.fields_by_name['balancerId']._options = None
_BALANCED.fields_by_name['granted']._options = None
_BALANCED.fields_by_name['id']._options = None
_MUTEXED.fields_by_name['mutexId']._options = None
_MUTEXED.fields_by_name['extraHoldTime']._options = None
_MUTEXED.fields_by_name['hasLock']._options = None
_MUTEXED.fields_by_name['hasCustomHoldTime']._options = None
_ANALOGCONSTRAINT.fields_by_name['min']._options = None
_ANALOGCONSTRAINT.fields_by_name['max']._options = None
_ANALOGCONSTRAINT.fields_by_name['limiting']._options = None
_ANALOGCONSTRAINTS.fields_by_name['constraints']._options = None
_DIGITALCONSTRAINT.fields_by_name['minOff']._options = None
_DIGITALCONSTRAINT.fields_by_name['minOn']._options = None
_DIGITALCONSTRAINT.fields_by_name['delayedOff']._options = None
_DIGITALCONSTRAINT.fields_by_name['delayedOn']._options = None
_DIGITALCONSTRAINT.fields_by_name['mutex']._options = None
_DIGITALCONSTRAINT.fields_by_name['limiting']._options = None
_DIGITALCONSTRAINT.fields_by_name['remaining']._options = None
_DIGITALCONSTRAINTS.fields_by_name['constraints']._options = None
# @@protoc_insertion_point(module_scope)
