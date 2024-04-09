# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Pid.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import SetpointSensorPair_pb2 as SetpointSensorPair__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\tPid.proto\x12\x08\x62lox.Pid\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x18SetpointSensorPair.proto\"\xbd\x06\n\x05\x42lock\x12\x1c\n\x07inputId\x18\x01 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x04\x12\x1d\n\x08outputId\x18\x02 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x05\x12&\n\ninputValue\x18\x05 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x01\x10\x80 (\x01\x30\x01\x12(\n\x0cinputSetting\x18\x06 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x01\x10\x80 (\x01\x30\x01\x12%\n\x0boutputValue\x18\x07 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\'\n\routputSetting\x18\x08 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\x17\n\x07\x65nabled\x18\x0b \x01(\x08\x42\x06\x8a\xb5\x18\x02\x30\x01\x12\x18\n\x06\x61\x63tive\x18\x0c \x01(\x08\x42\x08\x8a\xb5\x18\x04(\x01\x30\x01\x12\x1a\n\x02kp\x18\r \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x02\x10\x80 \x12\x17\n\x02ti\x18\x0e \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x08\x03\x12\x17\n\x02td\x18\x0f \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x08\x03\x12\x1b\n\x01p\x18\x10 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\x1b\n\x01i\x18\x11 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12\x1b\n\x01\x64\x18\x12 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80 (\x01\x30\x01\x12!\n\x05\x65rror\x18\x13 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x06\x10\x80 (\x01\x30\x01\x12\"\n\x08integral\x18\x14 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x10\x80\x02(\x01\x30\x01\x12%\n\nderivative\x18\x15 \x01(\x11\x42\x11\x92?\x02\x38 \x8a\xb5\x18\x08\x10\x80\x80 (\x01\x30\x01\x12%\n\rintegralReset\x18\x17 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 0\x01\x12\'\n\x0f\x62oilPointAdjust\x18\x18 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x08\x06\x10\x80 \x12#\n\rboilMinOutput\x18\x19 \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 \x12 \n\x0e\x62oilModeActive\x18\x1a \x01(\x08\x42\x08\x8a\xb5\x18\x04(\x01\x30\x01\x12G\n\x10\x64\x65rivativeFilter\x18\x1b \x01(\x0e\x32%.blox.SetpointSensorPair.FilterChoiceB\x06\x8a\xb5\x18\x02(\x01\x12#\n\x0e\x64rivenOutputId\x18Z \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\n\x8a\xb5\x18\x06\x18\xb0\x02J\x01\x0f\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'Pid_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['inputId']._options = None
  _BLOCK.fields_by_name['inputId']._serialized_options = b'\222?\0028\020\212\265\030\002\030\004'
  _BLOCK.fields_by_name['outputId']._options = None
  _BLOCK.fields_by_name['outputId']._serialized_options = b'\222?\0028\020\212\265\030\002\030\005'
  _BLOCK.fields_by_name['inputValue']._options = None
  _BLOCK.fields_by_name['inputValue']._serialized_options = b'\222?\0028 \212\265\030\t\010\001\020\200 (\0010\001'
  _BLOCK.fields_by_name['inputSetting']._options = None
  _BLOCK.fields_by_name['inputSetting']._serialized_options = b'\222?\0028 \212\265\030\t\010\001\020\200 (\0010\001'
  _BLOCK.fields_by_name['outputValue']._options = None
  _BLOCK.fields_by_name['outputValue']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['outputSetting']._options = None
  _BLOCK.fields_by_name['outputSetting']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['enabled']._options = None
  _BLOCK.fields_by_name['enabled']._serialized_options = b'\212\265\030\0020\001'
  _BLOCK.fields_by_name['active']._options = None
  _BLOCK.fields_by_name['active']._serialized_options = b'\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['kp']._options = None
  _BLOCK.fields_by_name['kp']._serialized_options = b'\222?\0028 \212\265\030\005\010\002\020\200 '
  _BLOCK.fields_by_name['ti']._options = None
  _BLOCK.fields_by_name['ti']._serialized_options = b'\222?\0028\020\212\265\030\002\010\003'
  _BLOCK.fields_by_name['td']._options = None
  _BLOCK.fields_by_name['td']._serialized_options = b'\222?\0028\020\212\265\030\002\010\003'
  _BLOCK.fields_by_name['p']._options = None
  _BLOCK.fields_by_name['p']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['i']._options = None
  _BLOCK.fields_by_name['i']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['d']._options = None
  _BLOCK.fields_by_name['d']._serialized_options = b'\222?\0028 \212\265\030\007\020\200 (\0010\001'
  _BLOCK.fields_by_name['error']._options = None
  _BLOCK.fields_by_name['error']._serialized_options = b'\222?\0028 \212\265\030\t\010\006\020\200 (\0010\001'
  _BLOCK.fields_by_name['integral']._options = None
  _BLOCK.fields_by_name['integral']._serialized_options = b'\222?\0028 \212\265\030\007\020\200\002(\0010\001'
  _BLOCK.fields_by_name['derivative']._options = None
  _BLOCK.fields_by_name['derivative']._serialized_options = b'\222?\0028 \212\265\030\010\020\200\200 (\0010\001'
  _BLOCK.fields_by_name['integralReset']._options = None
  _BLOCK.fields_by_name['integralReset']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 0\001'
  _BLOCK.fields_by_name['boilPointAdjust']._options = None
  _BLOCK.fields_by_name['boilPointAdjust']._serialized_options = b'\222?\0028 \212\265\030\005\010\006\020\200 '
  _BLOCK.fields_by_name['boilMinOutput']._options = None
  _BLOCK.fields_by_name['boilMinOutput']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _BLOCK.fields_by_name['boilModeActive']._options = None
  _BLOCK.fields_by_name['boilModeActive']._serialized_options = b'\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['derivativeFilter']._options = None
  _BLOCK.fields_by_name['derivativeFilter']._serialized_options = b'\212\265\030\002(\001'
  _BLOCK.fields_by_name['drivenOutputId']._options = None
  _BLOCK.fields_by_name['drivenOutputId']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\006\030\260\002J\001\017'
  _globals['_BLOCK']._serialized_start=80
  _globals['_BLOCK']._serialized_end=909
# @@protoc_insertion_point(module_scope)
