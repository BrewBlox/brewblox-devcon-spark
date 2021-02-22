# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Spark2Pins.proto
"""Generated protocol buffer code."""
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
  name='Spark2Pins.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x10Spark2Pins.proto\x12\x04\x62lox\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\xa8\x01\n\x0fSpark2PinsIoPin\x12\"\n\x07\x62ottom1\x18\x01 \x01(\x0b\x32\x0f.blox.IoChannelH\x00\x12\"\n\x07\x62ottom2\x18\x02 \x01(\x0b\x32\x0f.blox.IoChannelH\x00\x12\"\n\x07\x62ottom3\x18\x03 \x01(\x0b\x32\x0f.blox.IoChannelH\x00\x12\"\n\x07\x62ottom0\x18\x04 \x01(\x0b\x32\x0f.blox.IoChannelH\x00\x42\x05\n\x03Pin\"\xd5\x01\n\nSpark2Pins\x12\x35\n\x04pins\x18\x01 \x03(\x0b\x32\x15.blox.Spark2PinsIoPinB\x10\x92?\x02\x10\x04\x92?\x02x\x01\x8a\xb5\x18\x02(\x01\x12\x12\n\nsoundAlarm\x18\x05 \x01(\x08\x12\x33\n\x08hardware\x18\x08 \x01(\x0e\x32\x19.blox.Spark2Pins.HardwareB\x06\x8a\xb5\x18\x02(\x01\"8\n\x08Hardware\x12\x0e\n\nHW_UNKNOWN\x10\x00\x12\r\n\tHW_SPARK1\x10\x01\x12\r\n\tHW_SPARK2\x10\x02:\r\x8a\xb5\x18\x03\x18\xc0\x02\x8a\xb5\x18\x02H\nb\x06proto3'
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,IoArray__pb2.DESCRIPTOR,])



_SPARK2PINS_HARDWARE = _descriptor.EnumDescriptor(
  name='Hardware',
  full_name='blox.Spark2Pins.Hardware',
  filename=None,
  file=DESCRIPTOR,
  create_key=_descriptor._internal_create_key,
  values=[
    _descriptor.EnumValueDescriptor(
      name='HW_UNKNOWN', index=0, number=0,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='HW_SPARK1', index=1, number=1,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='HW_SPARK2', index=2, number=2,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=385,
  serialized_end=441,
)
_sym_db.RegisterEnumDescriptor(_SPARK2PINS_HARDWARE)


_SPARK2PINSIOPIN = _descriptor.Descriptor(
  name='Spark2PinsIoPin',
  full_name='blox.Spark2PinsIoPin',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='bottom1', full_name='blox.Spark2PinsIoPin.bottom1', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='bottom2', full_name='blox.Spark2PinsIoPin.bottom2', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='bottom3', full_name='blox.Spark2PinsIoPin.bottom3', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='bottom0', full_name='blox.Spark2PinsIoPin.bottom0', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
      name='Pin', full_name='blox.Spark2PinsIoPin.Pin',
      index=0, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
  ],
  serialized_start=72,
  serialized_end=240,
)


_SPARK2PINS = _descriptor.Descriptor(
  name='Spark2Pins',
  full_name='blox.Spark2Pins',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='pins', full_name='blox.Spark2Pins.pins', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\222?\002\020\004\222?\002x\001\212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='soundAlarm', full_name='blox.Spark2Pins.soundAlarm', index=1,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='hardware', full_name='blox.Spark2Pins.hardware', index=2,
      number=8, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=b'\212\265\030\002(\001', file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _SPARK2PINS_HARDWARE,
  ],
  serialized_options=b'\212\265\030\003\030\300\002\212\265\030\002H\n',
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=243,
  serialized_end=456,
)

_SPARK2PINSIOPIN.fields_by_name['bottom1'].message_type = IoArray__pb2._IOCHANNEL
_SPARK2PINSIOPIN.fields_by_name['bottom2'].message_type = IoArray__pb2._IOCHANNEL
_SPARK2PINSIOPIN.fields_by_name['bottom3'].message_type = IoArray__pb2._IOCHANNEL
_SPARK2PINSIOPIN.fields_by_name['bottom0'].message_type = IoArray__pb2._IOCHANNEL
_SPARK2PINSIOPIN.oneofs_by_name['Pin'].fields.append(
  _SPARK2PINSIOPIN.fields_by_name['bottom1'])
_SPARK2PINSIOPIN.fields_by_name['bottom1'].containing_oneof = _SPARK2PINSIOPIN.oneofs_by_name['Pin']
_SPARK2PINSIOPIN.oneofs_by_name['Pin'].fields.append(
  _SPARK2PINSIOPIN.fields_by_name['bottom2'])
_SPARK2PINSIOPIN.fields_by_name['bottom2'].containing_oneof = _SPARK2PINSIOPIN.oneofs_by_name['Pin']
_SPARK2PINSIOPIN.oneofs_by_name['Pin'].fields.append(
  _SPARK2PINSIOPIN.fields_by_name['bottom3'])
_SPARK2PINSIOPIN.fields_by_name['bottom3'].containing_oneof = _SPARK2PINSIOPIN.oneofs_by_name['Pin']
_SPARK2PINSIOPIN.oneofs_by_name['Pin'].fields.append(
  _SPARK2PINSIOPIN.fields_by_name['bottom0'])
_SPARK2PINSIOPIN.fields_by_name['bottom0'].containing_oneof = _SPARK2PINSIOPIN.oneofs_by_name['Pin']
_SPARK2PINS.fields_by_name['pins'].message_type = _SPARK2PINSIOPIN
_SPARK2PINS.fields_by_name['hardware'].enum_type = _SPARK2PINS_HARDWARE
_SPARK2PINS_HARDWARE.containing_type = _SPARK2PINS
DESCRIPTOR.message_types_by_name['Spark2PinsIoPin'] = _SPARK2PINSIOPIN
DESCRIPTOR.message_types_by_name['Spark2Pins'] = _SPARK2PINS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Spark2PinsIoPin = _reflection.GeneratedProtocolMessageType('Spark2PinsIoPin', (_message.Message,), {
  'DESCRIPTOR' : _SPARK2PINSIOPIN,
  '__module__' : 'Spark2Pins_pb2'
  # @@protoc_insertion_point(class_scope:blox.Spark2PinsIoPin)
  })
_sym_db.RegisterMessage(Spark2PinsIoPin)

Spark2Pins = _reflection.GeneratedProtocolMessageType('Spark2Pins', (_message.Message,), {
  'DESCRIPTOR' : _SPARK2PINS,
  '__module__' : 'Spark2Pins_pb2'
  # @@protoc_insertion_point(class_scope:blox.Spark2Pins)
  })
_sym_db.RegisterMessage(Spark2Pins)


_SPARK2PINS.fields_by_name['pins']._options = None
_SPARK2PINS.fields_by_name['hardware']._options = None
_SPARK2PINS._options = None
# @@protoc_insertion_point(module_scope)
