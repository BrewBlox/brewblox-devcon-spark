# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Claims.proto

from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='Claims.proto',
  package='blox.Claims',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x0c\x43laims.proto\x12\x0b\x62lox.Claims*&\n\x0bSettingMode\x12\n\n\x06STORED\x10\x00\x12\x0b\n\x07\x43LAIMED\x10\x01\x62\x06proto3'
)

_SETTINGMODE = _descriptor.EnumDescriptor(
  name='SettingMode',
  full_name='blox.Claims.SettingMode',
  filename=None,
  file=DESCRIPTOR,
  create_key=_descriptor._internal_create_key,
  values=[
    _descriptor.EnumValueDescriptor(
      name='STORED', index=0, number=0,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
    _descriptor.EnumValueDescriptor(
      name='CLAIMED', index=1, number=1,
      serialized_options=None,
      type=None,
      create_key=_descriptor._internal_create_key),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=29,
  serialized_end=67,
)
_sym_db.RegisterEnumDescriptor(_SETTINGMODE)

SettingMode = enum_type_wrapper.EnumTypeWrapper(_SETTINGMODE)
STORED = 0
CLAIMED = 1


DESCRIPTOR.enum_types_by_name['SettingMode'] = _SETTINGMODE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)


# @@protoc_insertion_point(module_scope)