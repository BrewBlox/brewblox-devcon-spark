# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Spark2Pins.proto
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
import IoArray_pb2 as IoArray__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x10Spark2Pins.proto\x12\x0f\x62lox.Spark2Pins\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\xb2\x01\n\x05\x42lock\x12\x12\n\nsoundAlarm\x18\x05 \x01(\x08\x12\x33\n\x08hardware\x18\x08 \x01(\x0e\x32\x19.blox.Spark2Pins.HardwareB\x06\x8a\xb5\x18\x02(\x01\x12\x38\n\x08\x63hannels\x18\t \x03(\x0b\x32\x17.blox.IoArray.IoChannelB\r\x92?\x04\x10\x04x\x01\x8a\xb5\x18\x02(\x01\x12\x19\n\x04pins\x18Z \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\x0b\x8a\xb5\x18\x07\x18\xc0\x02J\x02\n\x0c*\x85\x01\n\tChannelId\x12\x14\n\x10SPARK2_CHAN_NONE\x10\x00\x12\x17\n\x13SPARK2_CHAN_BOTTOM1\x10\x01\x12\x17\n\x13SPARK2_CHAN_BOTTOM2\x10\x02\x12\x17\n\x13SPARK2_CHAN_BOTTOM3\x10\x03\x12\x17\n\x13SPARK2_CHAN_BOTTOM0\x10\x04*8\n\x08Hardware\x12\x0e\n\nHW_UNKNOWN\x10\x00\x12\r\n\tHW_SPARK1\x10\x01\x12\r\n\tHW_SPARK2\x10\x02\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'Spark2Pins_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_BLOCK'].fields_by_name['hardware']._options = None
  _globals['_BLOCK'].fields_by_name['hardware']._serialized_options = b'\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['channels']._options = None
  _globals['_BLOCK'].fields_by_name['channels']._serialized_options = b'\222?\004\020\004x\001\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['pins']._options = None
  _globals['_BLOCK'].fields_by_name['pins']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _globals['_BLOCK']._options = None
  _globals['_BLOCK']._serialized_options = b'\212\265\030\007\030\300\002J\002\n\014'
  _globals['_CHANNELID']._serialized_start=264
  _globals['_CHANNELID']._serialized_end=397
  _globals['_HARDWARE']._serialized_start=399
  _globals['_HARDWARE']._serialized_end=455
  _globals['_BLOCK']._serialized_start=83
  _globals['_BLOCK']._serialized_end=261
# @@protoc_insertion_point(module_scope)
