# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: TempSensorMock.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x14TempSensorMock.proto\x12\x13\x62lox.TempSensorMock\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"R\n\x0b\x46luctuation\x12#\n\tamplitude\x18\x01 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x06\x10\x80 0\x01\x12\x1e\n\x06period\x18\x02 \x01(\rB\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x03\x10\xe8\x07\"\xaa\x01\n\x05\x42lock\x12!\n\x05value\x18\x01 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x01\x10\x80 (\x01\x30\x01\x12\x19\n\tconnected\x18\x03 \x01(\x08\x42\x06\x8a\xb5\x18\x02\x30\x01\x12\x1f\n\x07setting\x18\x04 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x01\x10\x80 \x12\x36\n\x0c\x66luctuations\x18\x05 \x03(\x0b\x32 .blox.TempSensorMock.Fluctuation:\n\x8a\xb5\x18\x06\x18\xad\x02J\x01\x02\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'TempSensorMock_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _FLUCTUATION.fields_by_name['amplitude']._options = None
  _FLUCTUATION.fields_by_name['amplitude']._serialized_options = b'\222?\0028 \212\265\030\007\010\006\020\200 0\001'
  _FLUCTUATION.fields_by_name['period']._options = None
  _FLUCTUATION.fields_by_name['period']._serialized_options = b'\222?\0028 \212\265\030\005\010\003\020\350\007'
  _BLOCK.fields_by_name['value']._options = None
  _BLOCK.fields_by_name['value']._serialized_options = b'\222?\0028 \212\265\030\t\010\001\020\200 (\0010\001'
  _BLOCK.fields_by_name['connected']._options = None
  _BLOCK.fields_by_name['connected']._serialized_options = b'\212\265\030\0020\001'
  _BLOCK.fields_by_name['setting']._options = None
  _BLOCK.fields_by_name['setting']._serialized_options = b'\222?\0028 \212\265\030\005\010\001\020\200 '
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\006\030\255\002J\001\002'
  _globals['_FLUCTUATION']._serialized_start=75
  _globals['_FLUCTUATION']._serialized_end=157
  _globals['_BLOCK']._serialized_start=160
  _globals['_BLOCK']._serialized_end=330
# @@protoc_insertion_point(module_scope)
