# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Variables.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import IoArray_pb2 as IoArray__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0fVariables.proto\x12\x0e\x62lox.Variables\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\x9b\x02\n\x0cVarContainer\x12\x0f\n\x05\x65mpty\x18\x01 \x01(\x08H\x00\x12-\n\x07\x64igital\x18\n \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateH\x00\x12\x1e\n\x06\x61nalog\x18\x0b \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 H\x00\x12\x1e\n\x04temp\x18\x14 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x01\x10\x80 H\x00\x12#\n\tdeltaTemp\x18\x15 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x06\x10\x80 H\x00\x12 \n\ttimestamp\x18\x1e \x01(\rB\x0b\x92?\x02\x38 \x8a\xb5\x18\x02X\x01H\x00\x12\x1f\n\x08\x64uration\x18\x1f \x01(\rB\x0b\x92?\x02\x38 \x8a\xb5\x18\x02\x08\x03H\x00\x12\x1c\n\x04link\x18( \x01(\rB\x0c\x92?\x02\x38\x10\x8a\xb5\x18\x03\x18\xff\x01H\x00\x42\x05\n\x03var\"\x99\x01\n\x05\x42lock\x12\x37\n\tvariables\x18\x01 \x03(\x0b\x32$.blox.Variables.Block.VariablesEntry\x1aN\n\x0eVariablesEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12+\n\x05value\x18\x02 \x01(\x0b\x32\x1c.blox.Variables.VarContainer:\x02\x38\x01:\x07\x8a\xb5\x18\x03\x18\xcd\x02\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'Variables_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _VARCONTAINER.fields_by_name['analog']._options = None
  _VARCONTAINER.fields_by_name['analog']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _VARCONTAINER.fields_by_name['temp']._options = None
  _VARCONTAINER.fields_by_name['temp']._serialized_options = b'\222?\0028 \212\265\030\005\010\001\020\200 '
  _VARCONTAINER.fields_by_name['deltaTemp']._options = None
  _VARCONTAINER.fields_by_name['deltaTemp']._serialized_options = b'\222?\0028 \212\265\030\005\010\006\020\200 '
  _VARCONTAINER.fields_by_name['timestamp']._options = None
  _VARCONTAINER.fields_by_name['timestamp']._serialized_options = b'\222?\0028 \212\265\030\002X\001'
  _VARCONTAINER.fields_by_name['duration']._options = None
  _VARCONTAINER.fields_by_name['duration']._serialized_options = b'\222?\0028 \212\265\030\002\010\003'
  _VARCONTAINER.fields_by_name['link']._options = None
  _VARCONTAINER.fields_by_name['link']._serialized_options = b'\222?\0028\020\212\265\030\003\030\377\001'
  _BLOCK_VARIABLESENTRY._options = None
  _BLOCK_VARIABLESENTRY._serialized_options = b'8\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\003\030\315\002'
  _globals['_VARCONTAINER']._serialized_start=81
  _globals['_VARCONTAINER']._serialized_end=364
  _globals['_BLOCK']._serialized_start=367
  _globals['_BLOCK']._serialized_end=520
  _globals['_BLOCK_VARIABLESENTRY']._serialized_start=433
  _globals['_BLOCK_VARIABLESENTRY']._serialized_end=511
# @@protoc_insertion_point(module_scope)
