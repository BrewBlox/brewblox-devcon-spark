# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: OneWireBus.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='OneWireBus.proto',
  package='blox',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x10OneWireBus.proto\x12\x04\x62lox\"q\n\nOneWireBus\x12)\n\x07\x63ommand\x18\x01 \x01(\x0b\x32\x18.blox.OneWireBus.Command\x12\x0f\n\x07\x61\x64\x64ress\x18\x02 \x03(\x0c\x1a\'\n\x07\x43ommand\x12\x0e\n\x06opcode\x18\x01 \x01(\r\x12\x0c\n\x04\x64\x61ta\x18\x02 \x01(\r\"<\n\x0fOneWireBusWrite\x12)\n\x07\x63ommand\x18\x01 \x01(\x0b\x32\x18.blox.OneWireBus.Commandb\x06proto3')
)




_ONEWIREBUS_COMMAND = _descriptor.Descriptor(
  name='Command',
  full_name='blox.OneWireBus.Command',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='opcode', full_name='blox.OneWireBus.Command.opcode', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='data', full_name='blox.OneWireBus.Command.data', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=100,
  serialized_end=139,
)

_ONEWIREBUS = _descriptor.Descriptor(
  name='OneWireBus',
  full_name='blox.OneWireBus',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='command', full_name='blox.OneWireBus.command', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='address', full_name='blox.OneWireBus.address', index=1,
      number=2, type=12, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_ONEWIREBUS_COMMAND, ],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=26,
  serialized_end=139,
)


_ONEWIREBUSWRITE = _descriptor.Descriptor(
  name='OneWireBusWrite',
  full_name='blox.OneWireBusWrite',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='command', full_name='blox.OneWireBusWrite.command', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=141,
  serialized_end=201,
)

_ONEWIREBUS_COMMAND.containing_type = _ONEWIREBUS
_ONEWIREBUS.fields_by_name['command'].message_type = _ONEWIREBUS_COMMAND
_ONEWIREBUSWRITE.fields_by_name['command'].message_type = _ONEWIREBUS_COMMAND
DESCRIPTOR.message_types_by_name['OneWireBus'] = _ONEWIREBUS
DESCRIPTOR.message_types_by_name['OneWireBusWrite'] = _ONEWIREBUSWRITE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

OneWireBus = _reflection.GeneratedProtocolMessageType('OneWireBus', (_message.Message,), dict(

  Command = _reflection.GeneratedProtocolMessageType('Command', (_message.Message,), dict(
    DESCRIPTOR = _ONEWIREBUS_COMMAND,
    __module__ = 'OneWireBus_pb2'
    # @@protoc_insertion_point(class_scope:blox.OneWireBus.Command)
    ))
  ,
  DESCRIPTOR = _ONEWIREBUS,
  __module__ = 'OneWireBus_pb2'
  # @@protoc_insertion_point(class_scope:blox.OneWireBus)
  ))
_sym_db.RegisterMessage(OneWireBus)
_sym_db.RegisterMessage(OneWireBus.Command)

OneWireBusWrite = _reflection.GeneratedProtocolMessageType('OneWireBusWrite', (_message.Message,), dict(
  DESCRIPTOR = _ONEWIREBUSWRITE,
  __module__ = 'OneWireBus_pb2'
  # @@protoc_insertion_point(class_scope:blox.OneWireBusWrite)
  ))
_sym_db.RegisterMessage(OneWireBusWrite)


# @@protoc_insertion_point(module_scope)
