# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: MotorValve.proto

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
import DigitalConstraints_pb2 as DigitalConstraints__pb2
import IoArray_pb2 as IoArray__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='MotorValve.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x10MotorValve.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x18\x44igitalConstraints.proto\x1a\rIoArray.proto\"\xc5\x03\n\nMotorValve\x12#\n\x08hwDevice\x18\x01 \x01(\rB\x11\x8a\xb5\x18\x02\x18\x0b\x8a\xb5\x18\x02@\x01\x92?\x02\x38\x10\x12\x1b\n\x0cstartChannel\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12/\n\x05state\x18\x03 \x01(\x0e\x32\x12.blox.DigitalStateB\x0c\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x02(\x01\x12/\n\rconstrainedBy\x18\x05 \x01(\x0b\x32\x18.blox.DigitalConstraints\x12=\n\nvalveState\x18\x06 \x01(\x0e\x32\x1b.blox.MotorValve.ValveStateB\x0c\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x02(\x01\x12\x30\n\x0c\x64\x65siredState\x18\x07 \x01(\x0e\x32\x12.blox.DigitalStateB\x06\x8a\xb5\x18\x02\x30\x01\x12(\n\x0estrippedFields\x18\x63 \x03(\rB\x10\x8a\xb5\x18\x02(\x01\x92?\x02\x38\x10\x92?\x02\x10\x02\"i\n\nValveState\x12\x0b\n\x07Unknown\x10\x00\x12\x08\n\x04Open\x10\x01\x12\n\n\x06\x43losed\x10\x02\x12\x0b\n\x07Opening\x10\x03\x12\x0b\n\x07\x43losing\x10\x04\x12\x10\n\x0cHalfOpenIdle\x10\x05\x12\x0c\n\x08InitIdle\x10\x06:\r\x8a\xb5\x18\x03\x18\xc1\x02\x8a\xb5\x18\x02H\x06\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,DigitalConstraints__pb2.DESCRIPTOR,IoArray__pb2.DESCRIPTOR,])



_MOTORVALVE_VALVESTATE = _descriptor.EnumDescriptor(
  name='ValveState',
  full_name='blox.MotorValve.ValveState',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='Unknown', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Open', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Closed', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Opening', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='Closing', index=4, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='HalfOpenIdle', index=5, number=5,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='InitIdle', index=6, number=6,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=431,
  serialized_end=536,
)
_sym_db.RegisterEnumDescriptor(_MOTORVALVE_VALVESTATE)


_MOTORVALVE = _descriptor.Descriptor(
  name='MotorValve',
  full_name='blox.MotorValve',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='hwDevice', full_name='blox.MotorValve.hwDevice', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\013\212\265\030\002@\001\222?\0028\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='startChannel', full_name='blox.MotorValve.startChannel', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\0028\010'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='state', full_name='blox.MotorValve.state', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\0020\001\212\265\030\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='constrainedBy', full_name='blox.MotorValve.constrainedBy', index=3,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='valveState', full_name='blox.MotorValve.valveState', index=4,
      number=6, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\0020\001\212\265\030\002(\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='desiredState', full_name='blox.MotorValve.desiredState', index=5,
      number=7, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\0020\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='strippedFields', full_name='blox.MotorValve.strippedFields', index=6,
      number=99, type=13, cpp_type=3, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002(\001\222?\0028\020\222?\002\020\002'), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _MOTORVALVE_VALVESTATE,
  ],
  serialized_options=_b('\212\265\030\003\030\301\002\212\265\030\002H\006'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=98,
  serialized_end=551,
)

_MOTORVALVE.fields_by_name['state'].enum_type = IoArray__pb2._DIGITALSTATE
_MOTORVALVE.fields_by_name['constrainedBy'].message_type = DigitalConstraints__pb2._DIGITALCONSTRAINTS
_MOTORVALVE.fields_by_name['valveState'].enum_type = _MOTORVALVE_VALVESTATE
_MOTORVALVE.fields_by_name['desiredState'].enum_type = IoArray__pb2._DIGITALSTATE
_MOTORVALVE_VALVESTATE.containing_type = _MOTORVALVE
DESCRIPTOR.message_types_by_name['MotorValve'] = _MOTORVALVE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

MotorValve = _reflection.GeneratedProtocolMessageType('MotorValve', (_message.Message,), dict(
  DESCRIPTOR = _MOTORVALVE,
  __module__ = 'MotorValve_pb2'
  # @@protoc_insertion_point(class_scope:blox.MotorValve)
  ))
_sym_db.RegisterMessage(MotorValve)


_MOTORVALVE.fields_by_name['hwDevice']._options = None
_MOTORVALVE.fields_by_name['startChannel']._options = None
_MOTORVALVE.fields_by_name['state']._options = None
_MOTORVALVE.fields_by_name['valveState']._options = None
_MOTORVALVE.fields_by_name['desiredState']._options = None
_MOTORVALVE.fields_by_name['strippedFields']._options = None
_MOTORVALVE._options = None
# @@protoc_insertion_point(module_scope)
