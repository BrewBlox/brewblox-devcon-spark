# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: ActuatorPwm.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import AnalogConstraints_pb2 as AnalogConstraints__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='ActuatorPwm.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=b'\n\x11\x41\x63tuatorPwm.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x17\x41nalogConstraints.proto\"\x80\x03\n\x0b\x41\x63tuatorPwm\x12\x1f\n\nactuatorId\x18\x01 \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x06\x92?\x02\x38\x10\x12\x1d\n\x06period\x18\x03 \x01(\rB\r\x8a\xb5\x18\x02\x08\x03\x8a\xb5\x18\x03\x10\xe8\x07\x12)\n\x07setting\x18\x04 \x01(\x11\x42\x18\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x02(\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x12\'\n\x05value\x18\x05 \x01(\x11\x42\x18\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x8a\xb5\x18\x02(\x01\x12.\n\rconstrainedBy\x18\x06 \x01(\x0b\x32\x17.blox.AnalogConstraints\x12\x31\n\x10\x64rivenActuatorId\x18\x07 \x01(\rB\x17\x8a\xb5\x18\x02\x18\x06\x8a\xb5\x18\x02@\x01\x92?\x02\x38\x10\x8a\xb5\x18\x02(\x01\x12\x0f\n\x07\x65nabled\x18\x08 \x01(\x08\x12*\n\x0e\x64\x65siredSetting\x18\t \x01(\x11\x42\x12\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x12(\n\x0estrippedFields\x18\x63 \x03(\rB\x10\x8a\xb5\x18\x02(\x01\x92?\x02\x38\x10\x92?\x02\x10\x02:\x13\x8a\xb5\x18\x03\x18\xb3\x02\x8a\xb5\x18\x02H\x01\x8a\xb5\x18\x02H\x05\x62\x06proto3'
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,AnalogConstraints__pb2.DESCRIPTOR,])




_ACTUATORPWM = _descriptor.Descriptor(
  name='ActuatorPwm',
  full_name='blox.ActuatorPwm',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='actuatorId', full_name='blox.ActuatorPwm.actuatorId', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\030\006\222?\0028\020', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='period', full_name='blox.ActuatorPwm.period', index=1,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\010\003\212\265\030\003\020\350\007', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='setting', full_name='blox.ActuatorPwm.setting', index=2,
      number=4, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\001\212\265\030\002(\001\212\265\030\003\020\200 \222?\0028 ', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='value', full_name='blox.ActuatorPwm.value', index=3,
      number=5, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\001\212\265\030\003\020\200 \222?\0028 \212\265\030\002(\001', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='constrainedBy', full_name='blox.ActuatorPwm.constrainedBy', index=4,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='drivenActuatorId', full_name='blox.ActuatorPwm.drivenActuatorId', index=5,
      number=7, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002\030\006\212\265\030\002@\001\222?\0028\020\212\265\030\002(\001', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='enabled', full_name='blox.ActuatorPwm.enabled', index=6,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='desiredSetting', full_name='blox.ActuatorPwm.desiredSetting', index=7,
      number=9, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\0020\001\212\265\030\003\020\200 \222?\0028 ', file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='strippedFields', full_name='blox.ActuatorPwm.strippedFields', index=8,
      number=99, type=13, cpp_type=3, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002(\001\222?\0028\020\222?\002\020\002', file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=b'\212\265\030\003\030\263\002\212\265\030\002H\001\212\265\030\002H\005',
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=83,
  serialized_end=467,
)

_ACTUATORPWM.fields_by_name['constrainedBy'].message_type = AnalogConstraints__pb2._ANALOGCONSTRAINTS
DESCRIPTOR.message_types_by_name['ActuatorPwm'] = _ACTUATORPWM
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

ActuatorPwm = _reflection.GeneratedProtocolMessageType('ActuatorPwm', (_message.Message,), {
  'DESCRIPTOR' : _ACTUATORPWM,
  '__module__' : 'ActuatorPwm_pb2'
  # @@protoc_insertion_point(class_scope:blox.ActuatorPwm)
  })
_sym_db.RegisterMessage(ActuatorPwm)


_ACTUATORPWM.fields_by_name['actuatorId']._options = None
_ACTUATORPWM.fields_by_name['period']._options = None
_ACTUATORPWM.fields_by_name['setting']._options = None
_ACTUATORPWM.fields_by_name['value']._options = None
_ACTUATORPWM.fields_by_name['drivenActuatorId']._options = None
_ACTUATORPWM.fields_by_name['desiredSetting']._options = None
_ACTUATORPWM.fields_by_name['strippedFields']._options = None
_ACTUATORPWM._options = None
# @@protoc_insertion_point(module_scope)
