# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: PrecisionAnalogModule.proto
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


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1bPrecisionAnalogModule.proto\x12\x1a\x62lox.PrecisionAnalogModule\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x10GpioModule.proto\"\xa7\x02\n\rAnalogChannel\x12\x41\n\nsensorType\x18\x01 \x01(\x0e\x32-.blox.PrecisionAnalogModule.AnalogChannelType\x12!\n\tclaimedBy\x18\x02 \x01(\rB\x0e\x92?\x02\x38\x10\x8a\xb5\x18\x05\x18\xff\x01(\x01\x12(\n\nresistance\x18\x04 \x01(\x11\x42\x14\x92?\x02\x38 \x8a\xb5\x18\x0b\x08\x0f\x10\x80 (\x01\x30\x01h\x01\x12,\n\x0eleadResistance\x18\x05 \x01(\x11\x42\x14\x92?\x02\x38 \x8a\xb5\x18\x0b\x08\x0f\x10\x80 (\x01\x30\x01h\x01\x12.\n\x10\x62ridgeResistance\x18\x06 \x01(\x11\x42\x14\x92?\x02\x38 \x8a\xb5\x18\x0b\x08\x0f\x10\x80 (\x01\x30\x01h\x01\x12(\n\x0c\x62ridgeOutput\x18\x07 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x10\x80 (\x01\x30\x01h\x01\"\xd7\x02\n\x05\x42lock\x12\x35\n\x0cgpioChannels\x18\x01 \x03(\x0b\x32\x18.blox.GpioModule.ChannelB\x05\x92?\x02\x10\x08\x12\x1d\n\x0emodulePosition\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12\x18\n\x10useExternalPower\x18\x03 \x01(\x08\x12+\n\ngpioStatus\x18\x04 \x01(\x0b\x32\x17.blox.GpioModule.Status\x12S\n\x0e\x61nalogChannels\x18\x05 \x03(\x0b\x32).blox.PrecisionAnalogModule.AnalogChannelB\x10\x92?\x05\x10\x04\x80\x01\x01\x8a\xb5\x18\x04(\x01\x30\x01\x12(\n\x0c\x62\x61roPressure\x18\x06 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12)\n\x0f\x62\x61roTemperature\x18\x07 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01:\x07\x8a\xb5\x18\x03\x18\xcb\x02*\xe6\x01\n\x11\x41nalogChannelType\x12\x1c\n\x18\x41NALOG_CHANNEL_TYPE_NONE\x10\x00\x12$\n ANALOG_CHANNEL_TYPE_STRAIN_GAUGE\x10\x01\x12!\n\x1d\x41NALOG_CHANNEL_TYPE_RTD_2WIRE\x10\x02\x12!\n\x1d\x41NALOG_CHANNEL_TYPE_RTD_3WIRE\x10\x03\x12!\n\x1d\x41NALOG_CHANNEL_TYPE_RTD_4WIRE\x10\x04\x12$\n ANALOG_CHANNEL_TYPE_RTD_3WIRE_LS\x10\x05\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'PrecisionAnalogModule_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _ANALOGCHANNEL.fields_by_name['claimedBy']._options = None
  _ANALOGCHANNEL.fields_by_name['claimedBy']._serialized_options = b'\222?\0028\020\212\265\030\005\030\377\001(\001'
  _ANALOGCHANNEL.fields_by_name['resistance']._options = None
  _ANALOGCHANNEL.fields_by_name['resistance']._serialized_options = b'\222?\0028 \212\265\030\013\010\017\020\200 (\0010\001h\001'
  _ANALOGCHANNEL.fields_by_name['leadResistance']._options = None
  _ANALOGCHANNEL.fields_by_name['leadResistance']._serialized_options = b'\222?\0028 \212\265\030\013\010\017\020\200 (\0010\001h\001'
  _ANALOGCHANNEL.fields_by_name['bridgeResistance']._options = None
  _ANALOGCHANNEL.fields_by_name['bridgeResistance']._serialized_options = b'\222?\0028 \212\265\030\013\010\017\020\200 (\0010\001h\001'
  _ANALOGCHANNEL.fields_by_name['bridgeOutput']._options = None
  _ANALOGCHANNEL.fields_by_name['bridgeOutput']._serialized_options = b'\222?\0028 \212\265\030\t\020\200 (\0010\001h\001'
  _BLOCK.fields_by_name['gpioChannels']._options = None
  _BLOCK.fields_by_name['gpioChannels']._serialized_options = b'\222?\002\020\010'
  _BLOCK.fields_by_name['modulePosition']._options = None
  _BLOCK.fields_by_name['modulePosition']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['analogChannels']._options = None
  _BLOCK.fields_by_name['analogChannels']._serialized_options = b'\222?\005\020\004\200\001\001\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['baroPressure']._options = None
  _BLOCK.fields_by_name['baroPressure']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['baroTemperature']._options = None
  _BLOCK.fields_by_name['baroTemperature']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\003\030\313\002'
  _globals['_ANALOGCHANNELTYPE']._serialized_start=752
  _globals['_ANALOGCHANNELTYPE']._serialized_end=982
  _globals['_ANALOGCHANNEL']._serialized_start=108
  _globals['_ANALOGCHANNEL']._serialized_end=403
  _globals['_BLOCK']._serialized_start=406
  _globals['_BLOCK']._serialized_end=749
# @@protoc_insertion_point(module_scope)
