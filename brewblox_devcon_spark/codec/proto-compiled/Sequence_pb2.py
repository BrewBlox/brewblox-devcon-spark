# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: Sequence.proto
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


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0eSequence.proto\x12\rblox.Sequence\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\x1a\rIoArray.proto\"\x1f\n\x07\x43omment\x12\x14\n\x04text\x18\x01 \x01(\tB\x06\x8a\xb5\x18\x02x\x01\"\t\n\x07Restart\"b\n\rEnableDisable\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x0fx\x01H\x00\x12$\n\r__var__target\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\x08\n\x06target\"\x06\n\x04Wait\"l\n\x0cWaitDuration\x12(\n\x0f__raw__duration\x18\x01 \x01(\rB\r\x92?\x02\x38 \x8a\xb5\x18\x04\x08\x03x\x01H\x00\x12&\n\x0f__var__duration\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\n\n\x08\x64uration\"]\n\tWaitUntil\x12$\n\x0b__raw__time\x18\x01 \x01(\rB\r\x92?\x02\x38 \x8a\xb5\x18\x04X\x01x\x01H\x00\x12\"\n\x0b__var__time\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\x06\n\x04time\"\x99\x02\n\x14WaitTemperatureRange\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x02x\x01H\x00\x12$\n\r__var__target\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12(\n\x0c__raw__lower\x18\x02 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x01\x10\x80 x\x01H\x01\x12#\n\x0c__var__lower\x18\x05 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x12(\n\x0c__raw__upper\x18\x03 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x01\x10\x80 x\x01H\x02\x12#\n\x0c__var__upper\x18\x06 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x02\x42\x08\n\x06targetB\x07\n\x05lowerB\x07\n\x05upper\"\xc4\x01\n\x17WaitTemperatureBoundary\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x02x\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12(\n\x0c__raw__value\x18\x02 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x01\x10\x80 x\x01H\x01\x12#\n\x0c__var__value\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\x07\n\x05value\"\xbe\x01\n\x0bSetSetpoint\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x04x\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12*\n\x0e__raw__setting\x18\x02 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x01\x10\x80 x\x01H\x01\x12%\n\x0e__var__setting\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\t\n\x07setting\"\xc5\x01\n\x0cWaitSetpoint\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x04x\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12,\n\x10__raw__precision\x18\x02 \x01(\x11\x42\x10\x92?\x02\x38 \x8a\xb5\x18\x07\x08\x06\x10\x80 x\x01H\x01\x12\'\n\x10__var__precision\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\x0b\n\tprecision\"\xcf\x01\n\nSetDigital\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x06x\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12<\n\x0e__raw__setting\x18\x02 \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateB\x06\x8a\xb5\x18\x02x\x01H\x01\x12%\n\x0e__var__setting\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\t\n\x07setting\"`\n\x0bWaitDigital\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x06x\x01H\x00\x12$\n\r__var__target\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\x08\n\x06target\"\xcf\x01\n\x10WaitDigitalState\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x1bx\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12:\n\x0c__raw__state\x18\x02 \x01(\x0e\x32\x1a.blox.IoArray.DigitalStateB\x06\x8a\xb5\x18\x02x\x01H\x01\x12#\n\x0c__var__state\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\x07\n\x05state\"\xb7\x01\n\x06SetPwm\x12!\n\r__raw__target\x18\x01 \x01(\rB\x08\x8a\xb5\x18\x04\x18\x05x\x01H\x00\x12$\n\r__var__target\x18\x03 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x12(\n\x0e__raw__setting\x18\x02 \x01(\x11\x42\x0e\x92?\x02\x38 \x8a\xb5\x18\x05\x10\x80 x\x01H\x01\x12%\n\x0e__var__setting\x18\x04 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x01\x42\x08\n\x06targetB\t\n\x07setting\"c\n\rTargetProfile\x12\"\n\r__raw__target\x18\x01 \x01(\rB\t\x8a\xb5\x18\x05\x18\xb7\x02x\x01H\x00\x12$\n\r__var__target\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\x08\n\x06target\"d\n\x0eTargetSequence\x12\"\n\r__raw__target\x18\x01 \x01(\rB\t\x8a\xb5\x18\x05\x18\xc6\x02x\x01H\x00\x12$\n\r__var__target\x18\x02 \x01(\tB\x0b\x92?\x02\x08\x10\x8a\xb5\x18\x02x\x01H\x00\x42\x08\n\x06target\"\x8a\x0c\n\x0bInstruction\x12\x31\n\x07RESTART\x18\x01 \x01(\x0b\x32\x16.blox.Sequence.RestartB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x36\n\x06\x45NABLE\x18\x02 \x01(\x0b\x32\x1c.blox.Sequence.EnableDisableB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x37\n\x07\x44ISABLE\x18\x03 \x01(\x0b\x32\x1c.blox.Sequence.EnableDisableB\x06\x8a\xb5\x18\x02x\x01H\x00\x12+\n\x04WAIT\x18\x14 \x01(\x0b\x32\x13.blox.Sequence.WaitB\x06\x8a\xb5\x18\x02x\x01H\x00\x12<\n\rWAIT_DURATION\x18\x04 \x01(\x0b\x32\x1b.blox.Sequence.WaitDurationB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x36\n\nWAIT_UNTIL\x18\x05 \x01(\x0b\x32\x18.blox.Sequence.WaitUntilB\x06\x8a\xb5\x18\x02x\x01H\x00\x12H\n\x11WAIT_TEMP_BETWEEN\x18\x06 \x01(\x0b\x32#.blox.Sequence.WaitTemperatureRangeB\x06\x8a\xb5\x18\x02x\x01H\x00\x12L\n\x15WAIT_TEMP_NOT_BETWEEN\x18\x07 \x01(\x0b\x32#.blox.Sequence.WaitTemperatureRangeB\x06\x8a\xb5\x18\x02x\x01H\x00\x12K\n\x14WAIT_TEMP_UNEXPECTED\x18\x08 \x01(\x0b\x32#.blox.Sequence.WaitTemperatureRangeB\x06\x8a\xb5\x18\x02x\x01H\x00\x12I\n\x0fWAIT_TEMP_ABOVE\x18\t \x01(\x0b\x32&.blox.Sequence.WaitTemperatureBoundaryB\x06\x8a\xb5\x18\x02x\x01H\x00\x12I\n\x0fWAIT_TEMP_BELOW\x18\n \x01(\x0b\x32&.blox.Sequence.WaitTemperatureBoundaryB\x06\x8a\xb5\x18\x02x\x01H\x00\x12:\n\x0cSET_SETPOINT\x18\x0b \x01(\x0b\x32\x1a.blox.Sequence.SetSetpointB\x06\x8a\xb5\x18\x02x\x01H\x00\x12<\n\rWAIT_SETPOINT\x18\x0c \x01(\x0b\x32\x1b.blox.Sequence.WaitSetpointB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x42\n\x13WAIT_SETPOINT_ABOVE\x18\x15 \x01(\x0b\x32\x1b.blox.Sequence.WaitSetpointB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x42\n\x13WAIT_SETPOINT_BELOW\x18\x16 \x01(\x0b\x32\x1b.blox.Sequence.WaitSetpointB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x38\n\x0bSET_DIGITAL\x18\r \x01(\x0b\x32\x19.blox.Sequence.SetDigitalB\x06\x8a\xb5\x18\x02x\x01H\x00\x12:\n\x0cWAIT_DIGITAL\x18\x0e \x01(\x0b\x32\x1a.blox.Sequence.WaitDigitalB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x46\n\x13WAIT_DIGITAL_EQUALS\x18\x17 \x01(\x0b\x32\x1f.blox.Sequence.WaitDigitalStateB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x30\n\x07SET_PWM\x18\x0f \x01(\x0b\x32\x15.blox.Sequence.SetPwmB\x06\x8a\xb5\x18\x02x\x01H\x00\x12=\n\rSTART_PROFILE\x18\x10 \x01(\x0b\x32\x1c.blox.Sequence.TargetProfileB\x06\x8a\xb5\x18\x02x\x01H\x00\x12<\n\x0cWAIT_PROFILE\x18\x11 \x01(\x0b\x32\x1c.blox.Sequence.TargetProfileB\x06\x8a\xb5\x18\x02x\x01H\x00\x12?\n\x0eSTART_SEQUENCE\x18\x12 \x01(\x0b\x32\x1d.blox.Sequence.TargetSequenceB\x06\x8a\xb5\x18\x02x\x01H\x00\x12>\n\rWAIT_SEQUENCE\x18\x13 \x01(\x0b\x32\x1d.blox.Sequence.TargetSequenceB\x06\x8a\xb5\x18\x02x\x01H\x00\x12\x32\n\x07\x43OMMENT\x18\xc8\x01 \x01(\x0b\x32\x16.blox.Sequence.CommentB\x06\x8a\xb5\x18\x02x\x01H\x00:\x06\x92?\x03\xb0\x01\x01\x42\r\n\x0binstruction\"\x98\x04\n\x05\x42lock\x12\x19\n\x07\x65nabled\x18\x01 \x01(\x08\x42\x08\x8a\xb5\x18\x04\x30\x01x\x01\x12\x38\n\x0cinstructions\x18\x02 \x03(\x0b\x32\x1a.blox.Sequence.InstructionB\x06\x8a\xb5\x18\x02x\x01\x12\x1e\n\x0bvariablesId\x18\x0b \x01(\rB\t\x8a\xb5\x18\x05\x18\xcd\x02x\x01\x12\x1d\n\roverrideState\x18\x03 \x01(\x08\x42\x06\x8a\xb5\x18\x02x\x01\x12(\n\x11\x61\x63tiveInstruction\x18\x04 \x01(\rB\r\x92?\x02\x38\x10\x8a\xb5\x18\x04\x30\x01x\x01\x12;\n\tstoreMode\x18\x0c \x01(\x0e\x32 .blox.Sequence.SequenceStoreModeB\x06\x8a\xb5\x18\x02x\x01\x12\x35\n\x06status\x18\x08 \x01(\x0e\x32\x1d.blox.Sequence.SequenceStatusB\x06\x8a\xb5\x18\x02(\x01\x12\x33\n\x05\x65rror\x18\t \x01(\x0e\x32\x1c.blox.Sequence.SequenceErrorB\x06\x8a\xb5\x18\x02(\x01\x12#\n\x07\x65lapsed\x18\n \x01(\rB\x12\x92?\x02\x38 \x8a\xb5\x18\t\x08\x03\x10\xe8\x07(\x01\x30\x01\x12/\n\x1a\x61\x63tiveInstructionStartedAt\x18\x05 \x01(\rB\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01\x12\x1f\n\ndisabledAt\x18\x06 \x01(\rB\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01\x12%\n\x10\x64isabledDuration\x18\x07 \x01(\rB\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\n\x8a\xb5\x18\x06\x18\xc6\x02J\x01\x0f*l\n\x0eSequenceStatus\x12\x0b\n\x07UNKNOWN\x10\x00\x12\x0c\n\x08\x44ISABLED\x10\x01\x12\n\n\x06PAUSED\x10\x02\x12\x08\n\x04NEXT\x10\x03\x12\x08\n\x04WAIT\x10\x04\x12\x07\n\x03\x45ND\x10\x05\x12\x0b\n\x07RESTART\x10\x06\x12\t\n\x05\x45RROR\x10\x07*\xd7\x01\n\rSequenceError\x12\x08\n\x04NONE\x10\x00\x12\x14\n\x10INVALID_ARGUMENT\x10\x01\x12\x12\n\x0eINVALID_TARGET\x10\x02\x12\x13\n\x0fINACTIVE_TARGET\x10\x03\x12\x13\n\x0f\x44ISABLED_TARGET\x10\x04\x12\x1d\n\x19SYSTEM_TIME_NOT_AVAILABLE\x10\x05\x12\x1b\n\x17VARIABLES_NOT_SUPPORTED\x10\x06\x12\x16\n\x12UNDEFINED_VARIABLE\x10\x07\x12\x14\n\x10INVALID_VARIABLE\x10\x08*\x8f\x02\n\x11SequenceStoreMode\x12*\n&AT_RESTORE_INSTRUCTION_RESTORE_ENABLED\x10\x00\x12)\n%AT_RESTORE_INSTRUCTION_ALWAYS_ENABLED\x10\x01\x12(\n$AT_RESTORE_INSTRUCTION_NEVER_ENABLED\x10\x02\x12(\n$AT_FIRST_INSTRUCTION_RESTORE_ENABLED\x10\x03\x12\'\n#AT_FIRST_INSTRUCTION_ALWAYS_ENABLED\x10\x04\x12&\n\"AT_FIRST_INSTRUCTION_NEVER_ENABLED\x10\x05\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'Sequence_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_COMMENT'].fields_by_name['text']._options = None
  _globals['_COMMENT'].fields_by_name['text']._serialized_options = b'\212\265\030\002x\001'
  _globals['_ENABLEDISABLE'].fields_by_name['__raw__target']._options = None
  _globals['_ENABLEDISABLE'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\017x\001'
  _globals['_ENABLEDISABLE'].fields_by_name['__var__target']._options = None
  _globals['_ENABLEDISABLE'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITDURATION'].fields_by_name['__raw__duration']._options = None
  _globals['_WAITDURATION'].fields_by_name['__raw__duration']._serialized_options = b'\222?\0028 \212\265\030\004\010\003x\001'
  _globals['_WAITDURATION'].fields_by_name['__var__duration']._options = None
  _globals['_WAITDURATION'].fields_by_name['__var__duration']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITUNTIL'].fields_by_name['__raw__time']._options = None
  _globals['_WAITUNTIL'].fields_by_name['__raw__time']._serialized_options = b'\222?\0028 \212\265\030\004X\001x\001'
  _globals['_WAITUNTIL'].fields_by_name['__var__time']._options = None
  _globals['_WAITUNTIL'].fields_by_name['__var__time']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__target']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\002x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__target']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__lower']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__lower']._serialized_options = b'\222?\0028 \212\265\030\007\010\001\020\200 x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__lower']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__lower']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__upper']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__raw__upper']._serialized_options = b'\222?\0028 \212\265\030\007\010\001\020\200 x\001'
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__upper']._options = None
  _globals['_WAITTEMPERATURERANGE'].fields_by_name['__var__upper']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__raw__target']._options = None
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\002x\001'
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__var__target']._options = None
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__raw__value']._options = None
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__raw__value']._serialized_options = b'\222?\0028 \212\265\030\007\010\001\020\200 x\001'
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__var__value']._options = None
  _globals['_WAITTEMPERATUREBOUNDARY'].fields_by_name['__var__value']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETSETPOINT'].fields_by_name['__raw__target']._options = None
  _globals['_SETSETPOINT'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\004x\001'
  _globals['_SETSETPOINT'].fields_by_name['__var__target']._options = None
  _globals['_SETSETPOINT'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETSETPOINT'].fields_by_name['__raw__setting']._options = None
  _globals['_SETSETPOINT'].fields_by_name['__raw__setting']._serialized_options = b'\222?\0028 \212\265\030\007\010\001\020\200 x\001'
  _globals['_SETSETPOINT'].fields_by_name['__var__setting']._options = None
  _globals['_SETSETPOINT'].fields_by_name['__var__setting']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITSETPOINT'].fields_by_name['__raw__target']._options = None
  _globals['_WAITSETPOINT'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\004x\001'
  _globals['_WAITSETPOINT'].fields_by_name['__var__target']._options = None
  _globals['_WAITSETPOINT'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITSETPOINT'].fields_by_name['__raw__precision']._options = None
  _globals['_WAITSETPOINT'].fields_by_name['__raw__precision']._serialized_options = b'\222?\0028 \212\265\030\007\010\006\020\200 x\001'
  _globals['_WAITSETPOINT'].fields_by_name['__var__precision']._options = None
  _globals['_WAITSETPOINT'].fields_by_name['__var__precision']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETDIGITAL'].fields_by_name['__raw__target']._options = None
  _globals['_SETDIGITAL'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\006x\001'
  _globals['_SETDIGITAL'].fields_by_name['__var__target']._options = None
  _globals['_SETDIGITAL'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETDIGITAL'].fields_by_name['__raw__setting']._options = None
  _globals['_SETDIGITAL'].fields_by_name['__raw__setting']._serialized_options = b'\212\265\030\002x\001'
  _globals['_SETDIGITAL'].fields_by_name['__var__setting']._options = None
  _globals['_SETDIGITAL'].fields_by_name['__var__setting']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITDIGITAL'].fields_by_name['__raw__target']._options = None
  _globals['_WAITDIGITAL'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\006x\001'
  _globals['_WAITDIGITAL'].fields_by_name['__var__target']._options = None
  _globals['_WAITDIGITAL'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITDIGITALSTATE'].fields_by_name['__raw__target']._options = None
  _globals['_WAITDIGITALSTATE'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\033x\001'
  _globals['_WAITDIGITALSTATE'].fields_by_name['__var__target']._options = None
  _globals['_WAITDIGITALSTATE'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_WAITDIGITALSTATE'].fields_by_name['__raw__state']._options = None
  _globals['_WAITDIGITALSTATE'].fields_by_name['__raw__state']._serialized_options = b'\212\265\030\002x\001'
  _globals['_WAITDIGITALSTATE'].fields_by_name['__var__state']._options = None
  _globals['_WAITDIGITALSTATE'].fields_by_name['__var__state']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETPWM'].fields_by_name['__raw__target']._options = None
  _globals['_SETPWM'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\004\030\005x\001'
  _globals['_SETPWM'].fields_by_name['__var__target']._options = None
  _globals['_SETPWM'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_SETPWM'].fields_by_name['__raw__setting']._options = None
  _globals['_SETPWM'].fields_by_name['__raw__setting']._serialized_options = b'\222?\0028 \212\265\030\005\020\200 x\001'
  _globals['_SETPWM'].fields_by_name['__var__setting']._options = None
  _globals['_SETPWM'].fields_by_name['__var__setting']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_TARGETPROFILE'].fields_by_name['__raw__target']._options = None
  _globals['_TARGETPROFILE'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\005\030\267\002x\001'
  _globals['_TARGETPROFILE'].fields_by_name['__var__target']._options = None
  _globals['_TARGETPROFILE'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_TARGETSEQUENCE'].fields_by_name['__raw__target']._options = None
  _globals['_TARGETSEQUENCE'].fields_by_name['__raw__target']._serialized_options = b'\212\265\030\005\030\306\002x\001'
  _globals['_TARGETSEQUENCE'].fields_by_name['__var__target']._options = None
  _globals['_TARGETSEQUENCE'].fields_by_name['__var__target']._serialized_options = b'\222?\002\010\020\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['RESTART']._options = None
  _globals['_INSTRUCTION'].fields_by_name['RESTART']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['ENABLE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['ENABLE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['DISABLE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['DISABLE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DURATION']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DURATION']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_UNTIL']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_UNTIL']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_BETWEEN']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_BETWEEN']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_NOT_BETWEEN']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_NOT_BETWEEN']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_UNEXPECTED']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_UNEXPECTED']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_ABOVE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_ABOVE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_BELOW']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_TEMP_BELOW']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['SET_SETPOINT']._options = None
  _globals['_INSTRUCTION'].fields_by_name['SET_SETPOINT']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT_ABOVE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT_ABOVE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT_BELOW']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SETPOINT_BELOW']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['SET_DIGITAL']._options = None
  _globals['_INSTRUCTION'].fields_by_name['SET_DIGITAL']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DIGITAL']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DIGITAL']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DIGITAL_EQUALS']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_DIGITAL_EQUALS']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['SET_PWM']._options = None
  _globals['_INSTRUCTION'].fields_by_name['SET_PWM']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['START_PROFILE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['START_PROFILE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_PROFILE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_PROFILE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['START_SEQUENCE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['START_SEQUENCE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SEQUENCE']._options = None
  _globals['_INSTRUCTION'].fields_by_name['WAIT_SEQUENCE']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION'].fields_by_name['COMMENT']._options = None
  _globals['_INSTRUCTION'].fields_by_name['COMMENT']._serialized_options = b'\212\265\030\002x\001'
  _globals['_INSTRUCTION']._options = None
  _globals['_INSTRUCTION']._serialized_options = b'\222?\003\260\001\001'
  _globals['_BLOCK'].fields_by_name['enabled']._options = None
  _globals['_BLOCK'].fields_by_name['enabled']._serialized_options = b'\212\265\030\0040\001x\001'
  _globals['_BLOCK'].fields_by_name['instructions']._options = None
  _globals['_BLOCK'].fields_by_name['instructions']._serialized_options = b'\212\265\030\002x\001'
  _globals['_BLOCK'].fields_by_name['variablesId']._options = None
  _globals['_BLOCK'].fields_by_name['variablesId']._serialized_options = b'\212\265\030\005\030\315\002x\001'
  _globals['_BLOCK'].fields_by_name['overrideState']._options = None
  _globals['_BLOCK'].fields_by_name['overrideState']._serialized_options = b'\212\265\030\002x\001'
  _globals['_BLOCK'].fields_by_name['activeInstruction']._options = None
  _globals['_BLOCK'].fields_by_name['activeInstruction']._serialized_options = b'\222?\0028\020\212\265\030\0040\001x\001'
  _globals['_BLOCK'].fields_by_name['storeMode']._options = None
  _globals['_BLOCK'].fields_by_name['storeMode']._serialized_options = b'\212\265\030\002x\001'
  _globals['_BLOCK'].fields_by_name['status']._options = None
  _globals['_BLOCK'].fields_by_name['status']._serialized_options = b'\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['error']._options = None
  _globals['_BLOCK'].fields_by_name['error']._serialized_options = b'\212\265\030\002(\001'
  _globals['_BLOCK'].fields_by_name['elapsed']._options = None
  _globals['_BLOCK'].fields_by_name['elapsed']._serialized_options = b'\222?\0028 \212\265\030\t\010\003\020\350\007(\0010\001'
  _globals['_BLOCK'].fields_by_name['activeInstructionStartedAt']._options = None
  _globals['_BLOCK'].fields_by_name['activeInstructionStartedAt']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _globals['_BLOCK'].fields_by_name['disabledAt']._options = None
  _globals['_BLOCK'].fields_by_name['disabledAt']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _globals['_BLOCK'].fields_by_name['disabledDuration']._options = None
  _globals['_BLOCK'].fields_by_name['disabledDuration']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _globals['_BLOCK']._options = None
  _globals['_BLOCK']._serialized_options = b'\212\265\030\006\030\306\002J\001\017'
  _globals['_SEQUENCESTATUS']._serialized_start=4306
  _globals['_SEQUENCESTATUS']._serialized_end=4414
  _globals['_SEQUENCEERROR']._serialized_start=4417
  _globals['_SEQUENCEERROR']._serialized_end=4632
  _globals['_SEQUENCESTOREMODE']._serialized_start=4635
  _globals['_SEQUENCESTOREMODE']._serialized_end=4906
  _globals['_COMMENT']._serialized_start=78
  _globals['_COMMENT']._serialized_end=109
  _globals['_RESTART']._serialized_start=111
  _globals['_RESTART']._serialized_end=120
  _globals['_ENABLEDISABLE']._serialized_start=122
  _globals['_ENABLEDISABLE']._serialized_end=220
  _globals['_WAIT']._serialized_start=222
  _globals['_WAIT']._serialized_end=228
  _globals['_WAITDURATION']._serialized_start=230
  _globals['_WAITDURATION']._serialized_end=338
  _globals['_WAITUNTIL']._serialized_start=340
  _globals['_WAITUNTIL']._serialized_end=433
  _globals['_WAITTEMPERATURERANGE']._serialized_start=436
  _globals['_WAITTEMPERATURERANGE']._serialized_end=717
  _globals['_WAITTEMPERATUREBOUNDARY']._serialized_start=720
  _globals['_WAITTEMPERATUREBOUNDARY']._serialized_end=916
  _globals['_SETSETPOINT']._serialized_start=919
  _globals['_SETSETPOINT']._serialized_end=1109
  _globals['_WAITSETPOINT']._serialized_start=1112
  _globals['_WAITSETPOINT']._serialized_end=1309
  _globals['_SETDIGITAL']._serialized_start=1312
  _globals['_SETDIGITAL']._serialized_end=1519
  _globals['_WAITDIGITAL']._serialized_start=1521
  _globals['_WAITDIGITAL']._serialized_end=1617
  _globals['_WAITDIGITALSTATE']._serialized_start=1620
  _globals['_WAITDIGITALSTATE']._serialized_end=1827
  _globals['_SETPWM']._serialized_start=1830
  _globals['_SETPWM']._serialized_end=2013
  _globals['_TARGETPROFILE']._serialized_start=2015
  _globals['_TARGETPROFILE']._serialized_end=2114
  _globals['_TARGETSEQUENCE']._serialized_start=2116
  _globals['_TARGETSEQUENCE']._serialized_end=2216
  _globals['_INSTRUCTION']._serialized_start=2219
  _globals['_INSTRUCTION']._serialized_end=3765
  _globals['_BLOCK']._serialized_start=3768
  _globals['_BLOCK']._serialized_end=4304
# @@protoc_insertion_point(module_scope)
