# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: OneWireBus.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x10OneWireBus.proto\x12\x0f\x62lox.OneWireBus\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"5\n\x07\x43ommand\x12\x15\n\x06opcode\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08\x12\x13\n\x04\x64\x61ta\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\"V\n\x05\x42lock\x12)\n\x07\x63ommand\x18\x01 \x01(\x0b\x32\x18.blox.OneWireBus.Command\x12\x19\n\x07\x61\x64\x64ress\x18\x02 \x03(\x06\x42\x08\x8a\xb5\x18\x04 \x01(\x01:\x07\x8a\xb5\x18\x03\x18\x82\x02\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'OneWireBus_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _COMMAND.fields_by_name['opcode']._options = None
  _COMMAND.fields_by_name['opcode']._serialized_options = b'\222?\0028\010'
  _COMMAND.fields_by_name['data']._options = None
  _COMMAND.fields_by_name['data']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['address']._options = None
  _BLOCK.fields_by_name['address']._serialized_options = b'\212\265\030\004 \001(\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\003\030\202\002'
  _globals['_COMMAND']._serialized_start=67
  _globals['_COMMAND']._serialized_end=120
  _globals['_BLOCK']._serialized_start=122
  _globals['_BLOCK']._serialized_end=208
# @@protoc_insertion_point(module_scope)
