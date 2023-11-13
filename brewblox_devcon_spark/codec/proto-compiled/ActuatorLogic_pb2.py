# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: ActuatorLogic.proto
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


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x13\x41\x63tuatorLogic.proto\x12\x12\x62lox.ActuatorLogic\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\xb7\x01\n\x0e\x44igitalCompare\x12/\n\x02op\x18\x01 \x01(\x0e\x32#.blox.ActuatorLogic.DigitalOperator\x12\x32\n\x06result\x18\x02 \x01(\x0e\x32\x1a.blox.ActuatorLogic.ResultB\x06\x8a\xb5\x18\x02(\x01\x12\x17\n\x02id\x18\x03 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x1b\x12\'\n\x03rhs\x18\x04 \x01(\x0e\x32\x1a.blox.IoArray.DigitalState\"\xa7\x01\n\rAnalogCompare\x12.\n\x02op\x18\x01 \x01(\x0e\x32\".blox.ActuatorLogic.AnalogOperator\x12\x32\n\x06result\x18\x02 \x01(\x0e\x32\x1a.blox.ActuatorLogic.ResultB\x06\x8a\xb5\x18\x02(\x01\x12\x17\n\x02id\x18\x03 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x01\x12\x19\n\x03rhs\x18\x04 \x01(\x11\x42\x0c\x92?\x02\x38 \x8a\xb5\x18\x03\x10\x80 \"\xce\x02\n\x05\x42lock\x12\x1d\n\x08targetId\x18\x01 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x06\x12\x0f\n\x07\x65nabled\x18\x03 \x01(\x08\x12\x34\n\x06result\x18\x04 \x01(\x0e\x32\x1a.blox.ActuatorLogic.ResultB\x08\x8a\xb5\x18\x04(\x01\x30\x01\x12\x19\n\nexpression\x18\x05 \x01(\tB\x05\x92?\x02p@\x12:\n\x07\x64igital\x18\x06 \x03(\x0b\x32\".blox.ActuatorLogic.DigitalCompareB\x05\x92?\x02\x10\x10\x12\x38\n\x06\x61nalog\x18\x07 \x03(\x0b\x32!.blox.ActuatorLogic.AnalogCompareB\x05\x92?\x02\x10\x10\x12\x1d\n\x08\x65rrorPos\x18\x08 \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02(\x01\x12#\n\x0e\x64rivenTargetId\x18Z \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\n\x8a\xb5\x18\x06\x18\xc2\x02J\x01\x0f*\xcb\x03\n\x06Result\x12\x10\n\x0cRESULT_FALSE\x10\x00\x12\x0f\n\x0bRESULT_TRUE\x10\x01\x12\x10\n\x0cRESULT_EMPTY\x10\x02\x12\x1a\n\x16RESULT_EMPTY_SUBSTRING\x10\x03\x12\x1a\n\x16RESULT_BLOCK_NOT_FOUND\x10\x04\x12\x1d\n\x19RESULT_INVALID_DIGITAL_OP\x10\x05\x12\x1c\n\x18RESULT_INVALID_ANALOG_OP\x10\x06\x12$\n RESULT_UNDEFINED_DIGITAL_COMPARE\x10\x08\x12#\n\x1fRESULT_UNDEFINED_ANALOG_COMPARE\x10\x07\x12\"\n\x1eRESULT_UNEXPECTED_OPEN_BRACKET\x10\x0b\x12#\n\x1fRESULT_UNEXPECTED_CLOSE_BRACKET\x10\t\x12\x1f\n\x1bRESULT_UNEXPECTED_CHARACTER\x10\x0c\x12 \n\x1cRESULT_UNEXPECTED_COMPARISON\x10\r\x12\x1e\n\x1aRESULT_UNEXPECTED_OPERATOR\x10\x0e\x12 \n\x1cRESULT_MISSING_CLOSE_BRACKET\x10\n*a\n\x0f\x44igitalOperator\x12\x0f\n\x0bOP_VALUE_IS\x10\x00\x12\x13\n\x0fOP_VALUE_IS_NOT\x10\x01\x12\x11\n\rOP_DESIRED_IS\x10\n\x12\x15\n\x11OP_DESIRED_IS_NOT\x10\x0b*X\n\x0e\x41nalogOperator\x12\x0f\n\x0bOP_VALUE_LE\x10\x00\x12\x0f\n\x0bOP_VALUE_GE\x10\x01\x12\x11\n\rOP_SETTING_LE\x10\n\x12\x11\n\rOP_SETTING_GE\x10\x0b\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'ActuatorLogic_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _DIGITALCOMPARE.fields_by_name['result']._options = None
  _DIGITALCOMPARE.fields_by_name['result']._serialized_options = b'\212\265\030\002(\001'
  _DIGITALCOMPARE.fields_by_name['id']._options = None
  _DIGITALCOMPARE.fields_by_name['id']._serialized_options = b'\222?\0028\020\212\265\030\002\030\033'
  _ANALOGCOMPARE.fields_by_name['result']._options = None
  _ANALOGCOMPARE.fields_by_name['result']._serialized_options = b'\212\265\030\002(\001'
  _ANALOGCOMPARE.fields_by_name['id']._options = None
  _ANALOGCOMPARE.fields_by_name['id']._serialized_options = b'\222?\0028\020\212\265\030\002\030\001'
  _ANALOGCOMPARE.fields_by_name['rhs']._options = None
  _ANALOGCOMPARE.fields_by_name['rhs']._serialized_options = b'\222?\0028 \212\265\030\003\020\200 '
  _BLOCK.fields_by_name['targetId']._options = None
  _BLOCK.fields_by_name['targetId']._serialized_options = b'\222?\0028\020\212\265\030\002\030\006'
  _BLOCK.fields_by_name['result']._options = None
  _BLOCK.fields_by_name['result']._serialized_options = b'\212\265\030\004(\0010\001'
  _BLOCK.fields_by_name['expression']._options = None
  _BLOCK.fields_by_name['expression']._serialized_options = b'\222?\002p@'
  _BLOCK.fields_by_name['digital']._options = None
  _BLOCK.fields_by_name['digital']._serialized_options = b'\222?\002\020\020'
  _BLOCK.fields_by_name['analog']._options = None
  _BLOCK.fields_by_name['analog']._serialized_options = b'\222?\002\020\020'
  _BLOCK.fields_by_name['errorPos']._options = None
  _BLOCK.fields_by_name['errorPos']._serialized_options = b'\222?\0028\010\212\265\030\002(\001'
  _BLOCK.fields_by_name['drivenTargetId']._options = None
  _BLOCK.fields_by_name['drivenTargetId']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\006\030\302\002J\001\017'
  _globals['_RESULT']._serialized_start=782
  _globals['_RESULT']._serialized_end=1241
  _globals['_DIGITALOPERATOR']._serialized_start=1243
  _globals['_DIGITALOPERATOR']._serialized_end=1340
  _globals['_ANALOGOPERATOR']._serialized_start=1342
  _globals['_ANALOGOPERATOR']._serialized_end=1430
  _globals['_DIGITALCOMPARE']._serialized_start=89
  _globals['_DIGITALCOMPARE']._serialized_end=272
  _globals['_ANALOGCOMPARE']._serialized_start=275
  _globals['_ANALOGCOMPARE']._serialized_end=442
  _globals['_BLOCK']._serialized_start=445
  _globals['_BLOCK']._serialized_end=779
# @@protoc_insertion_point(module_scope)
