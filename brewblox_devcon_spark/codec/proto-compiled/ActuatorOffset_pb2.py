# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: ActuatorOffset.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2
import Constraints_pb2 as Constraints__pb2
import Claims_pb2 as Claims__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x14\x41\x63tuatorOffset.proto\x12\x13\x62lox.ActuatorOffset\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\x11\x43onstraints.proto\x1a\x0c\x43laims.proto\"\xc2\x04\n\x05\x42lock\x12\x0f\n\x07\x65nabled\x18\n \x01(\x08\x12\x1d\n\x08targetId\x18\x01 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x04\x12 \n\x0breferenceId\x18\x03 \x01(\rB\x0b\x92?\x02\x38\x10\x8a\xb5\x18\x02\x18\x04\x12\'\n\rstoredSetting\x18\r \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x06\x10\x80 0\x01\x12*\n\x0e\x64\x65siredSetting\x18\x0b \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x06\x10\x80 (\x01\x30\x01\x12#\n\x07setting\x18\x06 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x06\x10\x80 (\x01\x30\x01\x12!\n\x05value\x18\x07 \x01(\x11\x42\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x06\x10\x80 (\x01\x30\x01\x12\x43\n\x17referenceSettingOrValue\x18\x04 \x01(\x0e\x32\".blox.ActuatorOffset.ReferenceKind\x12\x44\n\rconstrainedBy\x18\x08 \x01(\x0b\x32-.blox.Constraints.DeprecatedAnalogConstraints\x12\x38\n\x0b\x63onstraints\x18\x0f \x01(\x0b\x32#.blox.Constraints.AnalogConstraints\x12!\n\tclaimedBy\x18\x0c \x01(\rB\x0e\x92?\x02\x38\x10\x8a\xb5\x18\x05\x18\xff\x01(\x01\x12-\n\x0bsettingMode\x18\x0e \x01(\x0e\x32\x18.blox.Claims.SettingMode\x12#\n\x0e\x64rivenTargetId\x18Z \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\x0e\x8a\xb5\x18\n\x18\xb4\x02J\x05\x01\x05\x13\x0f\x10*/\n\rReferenceKind\x12\x0f\n\x0bREF_SETTING\x10\x00\x12\r\n\tREF_VALUE\x10\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'ActuatorOffset_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _BLOCK.fields_by_name['targetId']._options = None
  _BLOCK.fields_by_name['targetId']._serialized_options = b'\222?\0028\020\212\265\030\002\030\004'
  _BLOCK.fields_by_name['referenceId']._options = None
  _BLOCK.fields_by_name['referenceId']._serialized_options = b'\222?\0028\020\212\265\030\002\030\004'
  _BLOCK.fields_by_name['storedSetting']._options = None
  _BLOCK.fields_by_name['storedSetting']._serialized_options = b'\222?\0028 \212\265\030\007\010\006\020\200 0\001'
  _BLOCK.fields_by_name['desiredSetting']._options = None
  _BLOCK.fields_by_name['desiredSetting']._serialized_options = b'\222?\0028 \212\265\030\t\010\006\020\200 (\0010\001'
  _BLOCK.fields_by_name['setting']._options = None
  _BLOCK.fields_by_name['setting']._serialized_options = b'\222?\0028 \212\265\030\t\010\006\020\200 (\0010\001'
  _BLOCK.fields_by_name['value']._options = None
  _BLOCK.fields_by_name['value']._serialized_options = b'\222?\0028 \212\265\030\t\010\006\020\200 (\0010\001'
  _BLOCK.fields_by_name['claimedBy']._options = None
  _BLOCK.fields_by_name['claimedBy']._serialized_options = b'\222?\0028\020\212\265\030\005\030\377\001(\001'
  _BLOCK.fields_by_name['drivenTargetId']._options = None
  _BLOCK.fields_by_name['drivenTargetId']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\n\030\264\002J\005\001\005\023\017\020'
  _globals['_REFERENCEKIND']._serialized_start=689
  _globals['_REFERENCEKIND']._serialized_end=736
  _globals['_BLOCK']._serialized_start=109
  _globals['_BLOCK']._serialized_end=687
# @@protoc_insertion_point(module_scope)
