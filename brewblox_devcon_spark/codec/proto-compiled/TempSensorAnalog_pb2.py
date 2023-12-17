# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: TempSensorAnalog.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x16TempSensorAnalog.proto\x12\x15\x62lox.TempSensorAnalog\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\xc9\x01\n\x05\x42lock\x12\x39\n\x04type\x18\x01 \x01(\x0e\x32+.blox.TempSensorAnalog.TempSensorAnalogType\x12\x1e\n\x08moduleId\x18\x02 \x01(\rB\x0c\x92?\x02\x38\x10\x8a\xb5\x18\x03\x18\xcb\x02\x12\x16\n\x07\x63hannel\x18\x03 \x01(\rB\x05\x92?\x02\x38\x08\x12!\n\x05value\x18\x04 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x01\x10\x80 (\x01\x30\x01\x12\x1e\n\x06offset\x18\x05 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x06\x10\x80 :\n\x8a\xb5\x18\x06\x18\xcc\x02J\x01\x02*\x92\x01\n\x14TempSensorAnalogType\x12\x1a\n\x16TEMP_SENSOR_TYPE_UNSET\x10\x00\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_2WIRE\x10\x01\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_3WIRE\x10\x02\x12\x1e\n\x1aTEMP_SENSOR_TYPE_RTD_4WIRE\x10\x03\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'TempSensorAnalog_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['moduleId']._options = None
  _BLOCK.fields_by_name['moduleId']._serialized_options = b'\222?\0028\020\212\265\030\003\030\313\002'
  _BLOCK.fields_by_name['channel']._options = None
  _BLOCK.fields_by_name['channel']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['value']._options = None
  _BLOCK.fields_by_name['value']._serialized_options = b'\222?\0028 \212\265\030\t\010\001\020\200 (\0010\001'
  _BLOCK.fields_by_name['offset']._options = None
  _BLOCK.fields_by_name['offset']._serialized_options = b'\222?\0028 \212\265\030\005\010\006\020\200 '
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\006\030\314\002J\001\002'
  _globals['_TEMPSENSORANALOGTYPE']._serialized_start=284
  _globals['_TEMPSENSORANALOGTYPE']._serialized_end=430
  _globals['_BLOCK']._serialized_start=80
  _globals['_BLOCK']._serialized_end=281
# @@protoc_insertion_point(module_scope)
