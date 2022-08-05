# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: DisplaySettings.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='DisplaySettings.proto',
  package='blox.DisplaySettings',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x15\x44isplaySettings.proto\x12\x14\x62lox.DisplaySettings\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\xf2\x01\n\x06Widget\x12\x12\n\x03pos\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08\x12\x1f\n\x05\x63olor\x18\x02 \x01(\x0c\x42\x10\x92?\x02\x08\x03\x92?\x02x\x01\x8a\xb5\x18\x02\x38\x01\x12\x13\n\x04name\x18\x03 \x01(\tB\x05\x92?\x02\x08\x10\x12!\n\ntempSensor\x18\n \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x02\x92?\x02\x38\x10H\x00\x12)\n\x12setpointSensorPair\x18\x0b \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x04\x92?\x02\x38\x10H\x00\x12%\n\x0e\x61\x63tuatorAnalog\x18\x0c \x01(\rB\x0b\x8a\xb5\x18\x02\x18\x05\x92?\x02\x38\x10H\x00\x12\x1b\n\x03pid\x18\x0e \x01(\rB\x0c\x8a\xb5\x18\x03\x18\xb0\x02\x92?\x02\x38\x10H\x00\x42\x0c\n\nWidgetType\"[\n\x05\x42lock\x12\x34\n\x07widgets\x18\x01 \x03(\x0b\x32\x1c.blox.DisplaySettings.WidgetB\x05\x92?\x02\x10\x06\x12\x13\n\x04name\x18\x02 \x01(\tB\x05\x92?\x02\x08(:\x07\x8a\xb5\x18\x03\x18\xba\x02\x62\x06proto3')
  ,
  dependencies=[brewblox__pb2.DESCRIPTOR,nanopb__pb2.DESCRIPTOR,])




_WIDGET = _descriptor.Descriptor(
  name='Widget',
  full_name='blox.DisplaySettings.Widget',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='pos', full_name='blox.DisplaySettings.Widget.pos', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\0028\010'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='color', full_name='blox.DisplaySettings.Widget.color', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\002\010\003\222?\002x\001\212\265\030\0028\001'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='blox.DisplaySettings.Widget.name', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\002\010\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='tempSensor', full_name='blox.DisplaySettings.Widget.tempSensor', index=3,
      number=10, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\002\222?\0028\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='setpointSensorPair', full_name='blox.DisplaySettings.Widget.setpointSensorPair', index=4,
      number=11, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\004\222?\0028\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='actuatorAnalog', full_name='blox.DisplaySettings.Widget.actuatorAnalog', index=5,
      number=12, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\002\030\005\222?\0028\020'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='pid', full_name='blox.DisplaySettings.Widget.pid', index=6,
      number=14, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\212\265\030\003\030\260\002\222?\0028\020'), file=DESCRIPTOR),
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
    _descriptor.OneofDescriptor(
      name='WidgetType', full_name='blox.DisplaySettings.Widget.WidgetType',
      index=0, containing_type=None, fields=[]),
  ],
  serialized_start=78,
  serialized_end=320,
)


_BLOCK = _descriptor.Descriptor(
  name='Block',
  full_name='blox.DisplaySettings.Block',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='widgets', full_name='blox.DisplaySettings.Block.widgets', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\002\020\006'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='blox.DisplaySettings.Block.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\222?\002\010('), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=_b('\212\265\030\003\030\272\002'),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=322,
  serialized_end=413,
)

_WIDGET.oneofs_by_name['WidgetType'].fields.append(
  _WIDGET.fields_by_name['tempSensor'])
_WIDGET.fields_by_name['tempSensor'].containing_oneof = _WIDGET.oneofs_by_name['WidgetType']
_WIDGET.oneofs_by_name['WidgetType'].fields.append(
  _WIDGET.fields_by_name['setpointSensorPair'])
_WIDGET.fields_by_name['setpointSensorPair'].containing_oneof = _WIDGET.oneofs_by_name['WidgetType']
_WIDGET.oneofs_by_name['WidgetType'].fields.append(
  _WIDGET.fields_by_name['actuatorAnalog'])
_WIDGET.fields_by_name['actuatorAnalog'].containing_oneof = _WIDGET.oneofs_by_name['WidgetType']
_WIDGET.oneofs_by_name['WidgetType'].fields.append(
  _WIDGET.fields_by_name['pid'])
_WIDGET.fields_by_name['pid'].containing_oneof = _WIDGET.oneofs_by_name['WidgetType']
_BLOCK.fields_by_name['widgets'].message_type = _WIDGET
DESCRIPTOR.message_types_by_name['Widget'] = _WIDGET
DESCRIPTOR.message_types_by_name['Block'] = _BLOCK
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Widget = _reflection.GeneratedProtocolMessageType('Widget', (_message.Message,), dict(
  DESCRIPTOR = _WIDGET,
  __module__ = 'DisplaySettings_pb2'
  # @@protoc_insertion_point(class_scope:blox.DisplaySettings.Widget)
  ))
_sym_db.RegisterMessage(Widget)

Block = _reflection.GeneratedProtocolMessageType('Block', (_message.Message,), dict(
  DESCRIPTOR = _BLOCK,
  __module__ = 'DisplaySettings_pb2'
  # @@protoc_insertion_point(class_scope:blox.DisplaySettings.Block)
  ))
_sym_db.RegisterMessage(Block)


_WIDGET.fields_by_name['pos']._options = None
_WIDGET.fields_by_name['color']._options = None
_WIDGET.fields_by_name['name']._options = None
_WIDGET.fields_by_name['tempSensor']._options = None
_WIDGET.fields_by_name['setpointSensorPair']._options = None
_WIDGET.fields_by_name['actuatorAnalog']._options = None
_WIDGET.fields_by_name['pid']._options = None
_BLOCK.fields_by_name['widgets']._options = None
_BLOCK.fields_by_name['name']._options = None
_BLOCK._options = None
# @@protoc_insertion_point(module_scope)
