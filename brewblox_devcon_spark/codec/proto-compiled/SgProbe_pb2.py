# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: SgProbe.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\rSgProbe.proto\x12\x0c\x62lox.SgProbe\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\xaf\x0b\n\x05\x42lock\x12&\n\x10probeConnectorId\x18\x01 \x01(\rB\x0c\x92?\x02\x38\x10\x8a\xb5\x18\x03\x18\x90\x03\x12!\n\x12probeConnectorSlot\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12\x19\n\tconnected\x18\x03 \x01(\x08\x42\x06\x8a\xb5\x18\x02\x30\x01\x12%\n\tpressure1\x18\x04 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12%\n\tpressure2\x18\x05 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12-\n\x11pressure1Filtered\x18\x06 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12-\n\x11pressure2Filtered\x18\x07 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12(\n\x0cpressureDiff\x18\x08 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12\x30\n\x14pressureDiffFiltered\x18\t \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\r\x10\x80 (\x01\x30\x01\x12\"\n\x08tempRtd1\x18\n \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\"\n\x08tempRtd2\x18\x0c \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\"\n\x08tempAdc1\x18\r \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\"\n\x08tempAdc2\x18\x0e \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12!\n\x07\x62ridge1\x18\x0f \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12!\n\x07\x62ridge2\x18\x10 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12*\n\x06\x66ilter\x18\x11 \x01(\x0e\x32\x1a.blox.SgProbe.FilterChoice\x12\x1e\n\x04raw1\x18\x12 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\x1e\n\x04raw2\x18\x13 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12&\n\x0craw1Filtered\x18\x14 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12&\n\x0craw2Filtered\x18\x15 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\x1d\n\x07offset1\x18\x16 \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 \x12\x1d\n\x07offset2\x18\x17 \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 \x12\x1d\n\x06scale1\x18\x18 \x01(\x11\x42\r\x92?\x02\x38 \x8a\xb5\x18\x04\x10\x80\x80@\x12\x1d\n\x06scale2\x18\x19 \x01(\x11\x42\r\x92?\x02\x38 \x8a\xb5\x18\x04\x10\x80\x80@\x12#\n\rreferenceDiff\x18\x1a \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 \x12\x1f\n\x07\x64\x65nsity\x18\x1b \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12#\n\x0b\x64\x65nsityFilt\x18\x1c \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12.\n\x08sgFilter\x18\x1d \x01(\x0e\x32\x1c.blox.SgProbe.SgFilterChoice\x12*\n\x12\x63\x61librationBridge1\x18  \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12*\n\x12\x63\x61librationBridge2\x18! \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12%\n\rcalibrateTemp\x18# \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x01\x10\x80 \x12&\n\x0etempRtdOffset1\x18$ \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12&\n\x0etempRtdOffset2\x18% \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12&\n\x0etempAdcOffset1\x18& \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12&\n\x0etempAdcOffset2\x18\' \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12\x1d\n\x06\x64Temp1\x18( \x01(\x11\x42\r\x92?\x02\x38 \x8a\xb5\x18\x04\x10\x80\x80@\x12\x1d\n\x06\x64Temp2\x18) \x01(\x11\x42\r\x92?\x02\x38 \x8a\xb5\x18\x04\x10\x80\x80@\x12)\n\x0b\x63hemVoltage\x18* \x01(\x11\x42\x14\x92?\x02\x38 \x8a\xb5\x18\x0b\x08\x0e\x10\x80\x80\xfa\x01(\x01\x30\x01:\x07\x8a\xb5\x18\x03\x18\x91\x03*|\n\x0c\x46ilterChoice\x12\x0f\n\x0b\x46ILTER_NONE\x10\x00\x12\r\n\tFILTER_3s\x10\x01\x12\x0e\n\nFILTER_10s\x10\x02\x12\x0e\n\nFILTER_20s\x10\x03\x12\x0e\n\nFILTER_40s\x10\x04\x12\r\n\tFILTER_2m\x10\x05\x12\r\n\tFILTER_6m\x10\x06*\x93\x01\n\x0eSgFilterChoice\x12\x11\n\rSG_FILTER_20s\x10\x00\x12\x10\n\x0cSG_FILTER_2m\x10\x01\x12\x10\n\x0cSG_FILTER_7m\x10\x02\x12\x11\n\rSG_FILTER_15m\x10\x03\x12\x11\n\rSG_FILTER_45m\x10\x04\x12\x12\n\x0eSG_FILTER_1h30\x10\x05\x12\x10\n\x0cSG_FILTER_3h\x10\x06\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'SgProbe_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['probeConnectorId']._options = None
  _BLOCK.fields_by_name['probeConnectorId']._serialized_options = b'\222?\0028\020\212\265\030\003\030\220\003'
  _BLOCK.fields_by_name['probeConnectorSlot']._options = None
  _BLOCK.fields_by_name['probeConnectorSlot']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['connected']._options = None
  _BLOCK.fields_by_name['connected']._serialized_options = b'\212\265\030\0020\001'
  _BLOCK.fields_by_name['pressure1']._options = None
  _BLOCK.fields_by_name['pressure1']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['pressure2']._options = None
  _BLOCK.fields_by_name['pressure2']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['pressure1Filtered']._options = None
  _BLOCK.fields_by_name['pressure1Filtered']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['pressure2Filtered']._options = None
  _BLOCK.fields_by_name['pressure2Filtered']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['pressureDiff']._options = None
  _BLOCK.fields_by_name['pressureDiff']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['pressureDiffFiltered']._options = None
  _BLOCK.fields_by_name['pressureDiffFiltered']._serialized_options = b'\222?\0028 \212\265\030\t\010\r\020\200 (\0010\001'
  _BLOCK.fields_by_name['tempRtd1']._options = None
  _BLOCK.fields_by_name['tempRtd1']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['tempRtd2']._options = None
  _BLOCK.fields_by_name['tempRtd2']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['tempAdc1']._options = None
  _BLOCK.fields_by_name['tempAdc1']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['tempAdc2']._options = None
  _BLOCK.fields_by_name['tempAdc2']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['bridge1']._options = None
  _BLOCK.fields_by_name['bridge1']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['bridge2']._options = None
  _BLOCK.fields_by_name['bridge2']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['raw1']._options = None
  _BLOCK.fields_by_name['raw1']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['raw2']._options = None
  _BLOCK.fields_by_name['raw2']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['raw1Filtered']._options = None
  _BLOCK.fields_by_name['raw1Filtered']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['raw2Filtered']._options = None
  _BLOCK.fields_by_name['raw2Filtered']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['offset1']._options = None
  _BLOCK.fields_by_name['offset1']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _BLOCK.fields_by_name['offset2']._options = None
  _BLOCK.fields_by_name['offset2']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _BLOCK.fields_by_name['scale1']._options = None
  _BLOCK.fields_by_name['scale1']._serialized_options = b'\222?\0028 \212\265\030\004\020\200\200@'
  _BLOCK.fields_by_name['scale2']._options = None
  _BLOCK.fields_by_name['scale2']._serialized_options = b'\222?\0028 \212\265\030\004\020\200\200@'
  _BLOCK.fields_by_name['referenceDiff']._options = None
  _BLOCK.fields_by_name['referenceDiff']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _BLOCK.fields_by_name['density']._options = None
  _BLOCK.fields_by_name['density']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['densityFilt']._options = None
  _BLOCK.fields_by_name['densityFilt']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['calibrationBridge1']._options = None
  _BLOCK.fields_by_name['calibrationBridge1']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['calibrationBridge2']._options = None
  _BLOCK.fields_by_name['calibrationBridge2']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['calibrateTemp']._options = None
  _BLOCK.fields_by_name['calibrateTemp']._serialized_options = b'\222?\0028 \212\265\030\005\010\001\020\200 '
  _BLOCK.fields_by_name['tempRtdOffset1']._options = None
  _BLOCK.fields_by_name['tempRtdOffset1']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['tempRtdOffset2']._options = None
  _BLOCK.fields_by_name['tempRtdOffset2']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['tempAdcOffset1']._options = None
  _BLOCK.fields_by_name['tempAdcOffset1']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['tempAdcOffset2']._options = None
  _BLOCK.fields_by_name['tempAdcOffset2']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['dTemp1']._options = None
  _BLOCK.fields_by_name['dTemp1']._serialized_options = b'\222?\0028 \212\265\030\004\020\200\200@'
  _BLOCK.fields_by_name['dTemp2']._options = None
  _BLOCK.fields_by_name['dTemp2']._serialized_options = b'\222?\0028 \212\265\030\004\020\200\200@'
  _BLOCK.fields_by_name['chemVoltage']._options = None
  _BLOCK.fields_by_name['chemVoltage']._serialized_options = b'\222?\0028 \212\265\030\013\010\016\020\200\200\372\001(\0010\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\003\030\221\003'
  _globals['_FILTERCHOICE']._serialized_start=1519
  _globals['_FILTERCHOICE']._serialized_end=1643
  _globals['_SGFILTERCHOICE']._serialized_start=1646
  _globals['_SGFILTERCHOICE']._serialized_end=1793
  _globals['_BLOCK']._serialized_start=62
  _globals['_BLOCK']._serialized_end=1517
# @@protoc_insertion_point(module_scope)
