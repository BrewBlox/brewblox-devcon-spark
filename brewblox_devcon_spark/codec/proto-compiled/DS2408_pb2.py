# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: DS2408.proto
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


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0c\x44S2408.proto\x12\x0b\x62lox.DS2408\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\xf8\x01\n\x05\x42lock\x12\x19\n\x07\x61\x64\x64ress\x18\x01 \x01(\x06\x42\x08\x8a\xb5\x18\x04 \x01x\x01\x12\x19\n\tconnected\x18\x06 \x01(\x08\x42\x06\x8a\xb5\x18\x02(\x01\x12\x38\n\x0b\x63onnectMode\x18\t \x01(\x0e\x32\x1b.blox.DS2408.PinConnectModeB\x06\x8a\xb5\x18\x02x\x01\x12\x1e\n\x0coneWireBusId\x18\n \x01(\rB\x08\x8a\xb5\x18\x04\x18\x0c(\x01\x12\x36\n\x08\x63hannels\x18\x0b \x03(\x0b\x32\x17.blox.IoArray.IoChannelB\x0b\x92?\x02\x10\x08\x8a\xb5\x18\x02(\x01\x12\x19\n\x04pins\x18Z \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\x0c\x8a\xb5\x18\x08\x18\xbd\x02J\x03\n\x0b\t*\xfc\x01\n\tChannelId\x12\x14\n\x10\x44S2408_CHAN_NONE\x10\x00\x12\x11\n\rDS2408_CHAN_A\x10\x01\x12\x11\n\rDS2408_CHAN_B\x10\x02\x12\x11\n\rDS2408_CHAN_C\x10\x03\x12\x11\n\rDS2408_CHAN_D\x10\x04\x12\x11\n\rDS2408_CHAN_E\x10\x05\x12\x11\n\rDS2408_CHAN_F\x10\x06\x12\x11\n\rDS2408_CHAN_G\x10\x07\x12\x11\n\rDS2408_CHAN_H\x10\x08\x12\x15\n\x11\x44S2408_VALVE_NONE\x10\x00\x12\x12\n\x0e\x44S2408_VALVE_A\x10\x05\x12\x12\n\x0e\x44S2408_VALVE_B\x10\x01\x1a\x02\x10\x01*9\n\x0ePinConnectMode\x12\x11\n\rCONNECT_VALVE\x10\x00\x12\x14\n\x10\x43ONNECT_ACTUATOR\x10\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'DS2408_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_CHANNELID']._options = None
  _globals['_CHANNELID']._serialized_options = b'\020\001'
  _globals['_BLOCK'].fields_by_name['address']._options = None
  _globals['_BLOCK'].fields_by_name['address']._serialized_options = b'\212\265\030\004 \001x\001'
  _globals['_BLOCK'].fields_by_name['connected']._options = None
  _globals['_BLOCK'].fields_by_name['connected']._serialized_options = b'\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['connectMode']._options = None
  _globals['_BLOCK'].fields_by_name['connectMode']._serialized_options = b'\212\265\030\002x\001'
  _globals['_BLOCK'].fields_by_name['oneWireBusId']._options = None
  _globals['_BLOCK'].fields_by_name['oneWireBusId']._serialized_options = b'\212\265\030\004\030\014(\001'
  _globals['_BLOCK'].fields_by_name['channels']._options = None
  _globals['_BLOCK'].fields_by_name['channels']._serialized_options = b'\222?\002\020\010\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['pins']._options = None
  _globals['_BLOCK'].fields_by_name['pins']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _globals['_BLOCK']._options = None
  _globals['_BLOCK']._serialized_options = b'\212\265\030\010\030\275\002J\003\n\013\t'
  _globals['_CHANNELID']._serialized_start=326
  _globals['_CHANNELID']._serialized_end=578
  _globals['_PINCONNECTMODE']._serialized_start=580
  _globals['_PINCONNECTMODE']._serialized_end=637
  _globals['_BLOCK']._serialized_start=75
  _globals['_BLOCK']._serialized_end=323
# @@protoc_insertion_point(module_scope)
