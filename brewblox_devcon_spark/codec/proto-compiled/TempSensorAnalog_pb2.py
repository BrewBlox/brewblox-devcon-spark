# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: TempSensorAnalog.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x16TempSensorAnalog.proto\x12\x15\x62lox.TempSensorAnalog\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\xdc\x01\n\x05\x42lock\x12\x39\n\x04type\x18\x01 \x01(\x0e\x32+.blox.TempSensorAnalog.TempSensorAnalogType\x12\x1e\n\x08moduleId\x18\x02 \x01(\rB\x0c\x8a\xb5\x18\x03\x18\xcb\x02\x92?\x02\x38\x10\x12\x16\n\x07\x63hannel\x18\x03 \x01(\rB\x05\x92?\x02\x38\x08\x12-\n\x05value\x18\x04 \x01(\x11\x42\x1e\x8a\xb5\x18\x02\x30\x01\x8a\xb5\x18\x02\x08\x01\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 \x8a\xb5\x18\x02(\x01\x12\"\n\x06offset\x18\x05 \x01(\x11\x42\x12\x8a\xb5\x18\x02\x08\x06\x8a\xb5\x18\x03\x10\x80 \x92?\x02\x38 :\r\x8a\xb5\x18\x03\x18\xcc\x02\x8a\xb5\x18\x02H\x02*\x92\x01\n\x14TempSensorAnalogType\x12\x1a\n\x16TEMP_SENSOR_TYPE_UNSET\x10\x00\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_2WIRE\x10\x01\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_3WIRE\x10\x02\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_4WIRE\x10\x03\x62\x06proto3')

_TEMPSENSORANALOGTYPE = DESCRIPTOR.enum_types_by_name['TempSensorAnalogType']
TempSensorAnalogType = enum_type_wrapper.EnumTypeWrapper(_TEMPSENSORANALOGTYPE)
TEMP_SENSOR_TYPE_UNSET = 0
TEMP_SENSOR_TYPE_RTD_2WIRE = 1
TEMP_SENSOR_TYPE_RTD_3WIRE = 2
TEMP_SENSOR_TYPE_RTD_4WIRE = 3


_BLOCK = DESCRIPTOR.message_types_by_name['Block']
Block = _reflection.GeneratedProtocolMessageType('Block', (_message.Message,), {
  'DESCRIPTOR' : _BLOCK,
  '__module__' : 'TempSensorAnalog_pb2'
  # @@protoc_insertion_point(class_scope:blox.TempSensorAnalog.Block)
  })
_sym_db.RegisterMessage(Block)

if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['moduleId']._options = None
  _BLOCK.fields_by_name['moduleId']._serialized_options = b'\212\265\030\003\030\313\002\222?\0028\020'
  _BLOCK.fields_by_name['channel']._options = None
  _BLOCK.fields_by_name['channel']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['value']._options = None
  _BLOCK.fields_by_name['value']._serialized_options = b'\212\265\030\0020\001\212\265\030\002\010\001\212\265\030\003\020\200 \222?\0028 \212\265\030\002(\001'
  _BLOCK.fields_by_name['offset']._options = None
  _BLOCK.fields_by_name['offset']._serialized_options = b'\212\265\030\002\010\006\212\265\030\003\020\200 \222?\0028 '
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\003\030\314\002\212\265\030\002H\002'
  _TEMPSENSORANALOGTYPE._serialized_start=303
  _TEMPSENSORANALOGTYPE._serialized_end=449
  _BLOCK._serialized_start=80
  _BLOCK._serialized_end=300
# @@protoc_insertion_point(module_scope)
