# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: EdgeCase.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0e\x45\x64geCase.proto\x12\rblox.EdgeCase\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\">\n\x08Settings\x12\x17\n\x07\x61\x64\x64ress\x18\x01 \x01(\x06\x42\x06\x8a\xb5\x18\x02 \x01\x12\x19\n\x06offset\x18\x02 \x01(\x11\x42\t\x8a\xb5\x18\x05\x08\x06\x10\x80\x02\"<\n\x05State\x12\x18\n\x05value\x18\x01 \x01(\x11\x42\t\x8a\xb5\x18\x05\x08\x01\x10\x80\x02\x12\x19\n\tconnected\x18\x02 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\"(\n\nNestedLink\x12\x1a\n\nconnection\x18\x01 \x01(\rB\x06\x8a\xb5\x18\x02\x18\x02\"\xaa\x02\n\x05\x42lock\x12)\n\x08settings\x18\x01 \x01(\x0b\x32\x17.blox.EdgeCase.Settings\x12#\n\x05state\x18\x02 \x01(\x0b\x32\x14.blox.EdgeCase.State\x12\x16\n\x04link\x18\x03 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x05x\x01\x12\x32\n\x0f\x61\x64\x64itionalLinks\x18\x04 \x03(\x0b\x32\x19.blox.EdgeCase.NestedLink\x12!\n\nlistValues\x18\x05 \x03(\x11\x42\r\x8a\xb5\x18\t\x08\x01\x10\x80\x02h\x01x\x01\x12\x1d\n\x06\x64\x65ltaV\x18\x06 \x01(\rB\r\x8a\xb5\x18\t\x08\x07\x10\x80\x02p\x01x\x01\x12\x18\n\x06logged\x18\x07 \x01(\rB\x08\x8a\xb5\x18\x04\x30\x01h\x01\x12\x10\n\x08unLogged\x18\x08 \x01(\r\x12\x17\n\x02ip\x18\n \x01(\rB\x0b\x92?\x02\x38 \x8a\xb5\x18\x02`\x01\"#\n\x07SubCase\x12\x10\n\x08subvalue\x18\x01 \x01(\r:\x06\x8a\xb5\x18\x02X\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'EdgeCase_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_SETTINGS'].fields_by_name['address']._options = None
  _globals['_SETTINGS'].fields_by_name['address']._serialized_options = b'\212\265\030\002 \001'
  _globals['_SETTINGS'].fields_by_name['offset']._options = None
  _globals['_SETTINGS'].fields_by_name['offset']._serialized_options = b'\212\265\030\005\010\006\020\200\002'
  _globals['_STATE'].fields_by_name['value']._options = None
  _globals['_STATE'].fields_by_name['value']._serialized_options = b'\212\265\030\005\010\001\020\200\002'
  _globals['_STATE'].fields_by_name['connected']._options = None
  _globals['_STATE'].fields_by_name['connected']._serialized_options = b'\212\265\030\002(\001'
  _globals['_NESTEDLINK'].fields_by_name['connection']._options = None
  _globals['_NESTEDLINK'].fields_by_name['connection']._serialized_options = b'\212\265\030\002\030\002'
  _globals['_BLOCK'].fields_by_name['link']._options = None
  _globals['_BLOCK'].fields_by_name['link']._serialized_options = b'\212\265\030\004\030\005x\001'
  _globals['_BLOCK'].fields_by_name['listValues']._options = None
  _globals['_BLOCK'].fields_by_name['listValues']._serialized_options = b'\212\265\030\t\010\001\020\200\002h\001x\001'
  _globals['_BLOCK'].fields_by_name['deltaV']._options = None
  _globals['_BLOCK'].fields_by_name['deltaV']._serialized_options = b'\212\265\030\t\010\007\020\200\002p\001x\001'
  _globals['_BLOCK'].fields_by_name['logged']._options = None
  _globals['_BLOCK'].fields_by_name['logged']._serialized_options = b'\212\265\030\0040\001h\001'
  _globals['_BLOCK'].fields_by_name['ip']._options = None
  _globals['_BLOCK'].fields_by_name['ip']._serialized_options = b'\222?\0028 \212\265\030\002`\001'
  _globals['_SUBCASE']._options = None
  _globals['_SUBCASE']._serialized_options = b'\212\265\030\002X\001'
  _globals['_SETTINGS']._serialized_start=63
  _globals['_SETTINGS']._serialized_end=125
  _globals['_STATE']._serialized_start=127
  _globals['_STATE']._serialized_end=187
  _globals['_NESTEDLINK']._serialized_start=189
  _globals['_NESTEDLINK']._serialized_end=229
  _globals['_BLOCK']._serialized_start=232
  _globals['_BLOCK']._serialized_end=530
  _globals['_SUBCASE']._serialized_start=532
  _globals['_SUBCASE']._serialized_end=567
# @@protoc_insertion_point(module_scope)
