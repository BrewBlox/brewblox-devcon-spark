# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: IoArray.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import nanopb_pb2 as nanopb__pb2
import brewblox_pb2 as brewblox__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\rIoArray.proto\x12\x0c\x62lox.IoArray\x1a\x0cnanopb.proto\x1a\x0e\x62rewblox.proto\"f\n\tIoChannel\x12\x11\n\x02id\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08\x12#\n\x0c\x63\x61pabilities\x18\x02 \x01(\rB\r\x92?\x02\x38\x10\x8a\xb5\x18\x04(\x01P\x01\x12!\n\tclaimedBy\x18\x03 \x01(\rB\x0e\x92?\x02\x38\x10\x8a\xb5\x18\x05\x18\xff\x01(\x01*\x85\x01\n\x0c\x44igitalState\x12\x12\n\x0eSTATE_INACTIVE\x10\x00\x12\x10\n\x0cSTATE_ACTIVE\x10\x01\x12\x11\n\rSTATE_UNKNOWN\x10\x02\x12\x11\n\rSTATE_REVERSE\x10\x03\x12\x0c\n\x08Inactive\x10\x00\x12\n\n\x06\x41\x63tive\x10\x01\x12\x0b\n\x07Unknown\x10\x02\x1a\x02\x10\x01*^\n\x18TransitionDurationPreset\x12\n\n\x06ST_OFF\x10\x00\x12\x0b\n\x07ST_FAST\x10\x01\x12\r\n\tST_MEDIUM\x10\x02\x12\x0b\n\x07ST_SLOW\x10\x03\x12\r\n\tST_CUSTOM\x10\x04*\x85\x02\n\x13\x43hannelCapabilities\x12\x16\n\x12\x43HAN_SUPPORTS_NONE\x10\x00\x12 \n\x1c\x43HAN_SUPPORTS_DIGITAL_OUTPUT\x10\x01\x12\x1a\n\x16\x43HAN_SUPPORTS_PWM_80HZ\x10\x02\x12\x1b\n\x17\x43HAN_SUPPORTS_PWM_100HZ\x10\x04\x12\x1b\n\x17\x43HAN_SUPPORTS_PWM_200HZ\x10\x08\x12\x1c\n\x18\x43HAN_SUPPORTS_PWM_2000HZ\x10\x10\x12\x1f\n\x1b\x43HAN_SUPPORTS_BIDIRECTIONAL\x10 \x12\x1f\n\x1b\x43HAN_SUPPORTS_DIGITAL_INPUT\x10@*^\n\x0cPwmFrequency\x12\x11\n\rPWM_FREQ_80HZ\x10\x00\x12\x12\n\x0ePWM_FREQ_100HZ\x10\x01\x12\x12\n\x0ePWM_FREQ_200HZ\x10\x02\x12\x13\n\x0fPWM_FREQ_2000HZ\x10\x03\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'IoArray_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _DIGITALSTATE._options = None
  _DIGITALSTATE._serialized_options = b'\020\001'
  _IOCHANNEL.fields_by_name['id']._options = None
  _IOCHANNEL.fields_by_name['id']._serialized_options = b'\222?\0028\010'
  _IOCHANNEL.fields_by_name['capabilities']._options = None
  _IOCHANNEL.fields_by_name['capabilities']._serialized_options = b'\222?\0028\020\212\265\030\004(\001P\001'
  _IOCHANNEL.fields_by_name['claimedBy']._options = None
  _IOCHANNEL.fields_by_name['claimedBy']._serialized_options = b'\222?\0028\020\212\265\030\005\030\377\001(\001'
  _globals['_DIGITALSTATE']._serialized_start=166
  _globals['_DIGITALSTATE']._serialized_end=299
  _globals['_TRANSITIONDURATIONPRESET']._serialized_start=301
  _globals['_TRANSITIONDURATIONPRESET']._serialized_end=395
  _globals['_CHANNELCAPABILITIES']._serialized_start=398
  _globals['_CHANNELCAPABILITIES']._serialized_end=659
  _globals['_PWMFREQUENCY']._serialized_start=661
  _globals['_PWMFREQUENCY']._serialized_end=755
  _globals['_IOCHANNEL']._serialized_start=61
  _globals['_IOCHANNEL']._serialized_end=163
# @@protoc_insertion_point(module_scope)
