# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: OneWireGpioModule.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import GpioModule_pb2 as GpioModule__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x17OneWireGpioModule.proto\x12\x16\x62lox.OneWireGpioModule\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x10GpioModule.proto\"\xf3\x01\n\x05\x42lock\x12\x31\n\x08\x63hannels\x18\x01 \x03(\x0b\x32\x18.blox.GpioModule.ChannelB\x05\x92?\x02\x10\x08\x12\x1d\n\x0emodulePosition\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12\x18\n\x10useExternalPower\x18\x0e \x01(\x08\x12\'\n\x06status\x18\x0f \x01(\x0b\x32\x17.blox.GpioModule.Status\x12&\n\x11moduleStatusClear\x18Z \x01(\rB\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01\x12 \n\x0b\x63learFaults\x18  \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\x0b\x8a\xb5\x18\x07\x18\xc5\x02J\x02\n\x0c\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'OneWireGpioModule_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['channels']._options = None
  _BLOCK.fields_by_name['channels']._serialized_options = b'\222?\002\020\010'
  _BLOCK.fields_by_name['modulePosition']._options = None
  _BLOCK.fields_by_name['modulePosition']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['moduleStatusClear']._options = None
  _BLOCK.fields_by_name['moduleStatusClear']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK.fields_by_name['clearFaults']._options = None
  _BLOCK.fields_by_name['clearFaults']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\007\030\305\002J\002\n\014'
  _globals['_BLOCK']._serialized_start=100
  _globals['_BLOCK']._serialized_end=343
# @@protoc_insertion_point(module_scope)
