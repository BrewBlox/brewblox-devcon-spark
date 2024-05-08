# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: brewblox.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import descriptor_pb2 as google_dot_protobuf_dot_descriptor__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0e\x62rewblox.proto\x12\x08\x62rewblox\x1a google/protobuf/descriptor.proto\x1a\x0cnanopb.proto\"|\n\x0bMessageOpts\x12$\n\x07objtype\x18\x03 \x01(\x0e\x32\x13.brewblox.BlockType\x12(\n\x04impl\x18\t \x03(\x0e\x32\x13.brewblox.BlockTypeB\x05\x92?\x02\x10\x05\x12\x16\n\x07subtype\x18\x0b \x01(\rB\x05\x92?\x02\x38\x10:\x05\x92?\x02\x30\x01\"\xb0\x02\n\tFieldOpts\x12 \n\x04unit\x18\x01 \x01(\x0e\x32\x12.brewblox.UnitType\x12\r\n\x05scale\x18\x02 \x01(\r\x12$\n\x07objtype\x18\x03 \x01(\x0e\x32\x13.brewblox.BlockType\x12\r\n\x05hexed\x18\x04 \x01(\x08\x12\x10\n\x08readonly\x18\x05 \x01(\x08\x12\x0e\n\x06logged\x18\x06 \x01(\x08\x12\x0e\n\x06stored\x18\x0f \x01(\x08\x12\x0e\n\x06hexstr\x18\x07 \x01(\x08\x12\x0f\n\x07ignored\x18\t \x01(\x08\x12\x10\n\x08\x62itfield\x18\n \x01(\x08\x12\x10\n\x08\x64\x61tetime\x18\x0b \x01(\x08\x12\x13\n\x0bipv4address\x18\x0c \x01(\x08\x12\x14\n\x0comit_if_zero\x18\r \x01(\x08\x12\x14\n\x0cnull_if_zero\x18\x0e \x01(\x08:\x05\x92?\x02\x30\x01*\xad\x02\n\x08UnitType\x12\n\n\x06NotSet\x10\x00\x12\x0b\n\x07\x43\x65lsius\x10\x01\x12\x12\n\x0eInverseCelsius\x10\x02\x12\n\n\x06Second\x10\x03\x12\n\n\x06Minute\x10\x04\x12\x08\n\x04Hour\x10\x05\x12\x10\n\x0c\x44\x65ltaCelsius\x10\x06\x12\x19\n\x15\x44\x65ltaCelsiusPerSecond\x10\x07\x12\x19\n\x15\x44\x65ltaCelsiusPerMinute\x10\x08\x12\x17\n\x13\x44\x65ltaCelsiusPerHour\x10\t\x12\x1a\n\x16\x44\x65ltaCelsiusMultSecond\x10\n\x12\x1a\n\x16\x44\x65ltaCelsiusMultMinute\x10\x0b\x12\x18\n\x14\x44\x65ltaCelsiusMultHour\x10\x0c\x12\x0c\n\x08MilliBar\x10\r\x12\x08\n\x04Volt\x10\x0e\x12\x07\n\x03Ohm\x10\x0f*\x96\x0b\n\tBlockType\x12\x0b\n\x07Invalid\x10\x00\x12\x19\n\x15ProcessValueInterface\x10\x01\x12\x17\n\x13TempSensorInterface\x10\x02\x12\x1f\n\x1bSetpointSensorPairInterface\x10\x04\x12\x1b\n\x17\x41\x63tuatorAnalogInterface\x10\x05\x12\x1c\n\x18\x41\x63tuatorDigitalInterface\x10\x06\x12\x15\n\x11\x42\x61lancerInterface\x10\x07\x12\x12\n\x0eMutexInterface\x10\x08\x12\x1a\n\x16OneWireDeviceInterface\x10\t\x12\x14\n\x10IoArrayInterface\x10\n\x12\x13\n\x0f\x44S2408Interface\x10\x0b\x12\x17\n\x13OneWireBusInterface\x10\x0c\x12\x15\n\x11IoModuleInterface\x10\r\x12\x1f\n\x1bOneWireDeviceBlockInterface\x10\x0e\x12\x14\n\x10\x45nablerInterface\x10\x0f\x12\x16\n\x12\x43laimableInterface\x10\x10\x12\x15\n\x11IoDriverInterface\x10\x11\x12\x15\n\x11SetpointInterface\x10\x12\x12\x19\n\x15StoredAnalogInterface\x10\x13\x12\x1b\n\x17StoredSetpointInterface\x10\x14\x12\x1a\n\x16StoredDigitalInterface\x10\x15\x12\x1e\n\x1a\x43onstrainedAnalogInterface\x10\x16\x12 \n\x1c\x43onstrainedSetpointInterface\x10\x17\x12\x1f\n\x1b\x43onstrainedDigitalInterface\x10\x18\x12\x1c\n\x18ScanningFactoryInterface\x10\x19\x12\x1c\n\x18I2CDiscoverableInterface\x10\x1a\x12\x14\n\x10\x44igitalInterface\x10\x1b\x12\x19\n\x15\x41nalogModuleInterface\x10\x1c\x12\x08\n\x03\x41ny\x10\xff\x01\x12\x0c\n\x07SysInfo\x10\x80\x02\x12\n\n\x05Ticks\x10\x81\x02\x12\x0f\n\nOneWireBus\x10\x82\x02\x12\x0e\n\tBoardPins\x10\x83\x02\x12\x13\n\x0eTempSensorMock\x10\xad\x02\x12\x16\n\x11TempSensorOneWire\x10\xae\x02\x12\x17\n\x12SetpointSensorPair\x10\xaf\x02\x12\x08\n\x03Pid\x10\xb0\x02\x12\x17\n\x12\x41\x63tuatorAnalogMock\x10\xb1\x02\x12\x10\n\x0b\x41\x63tuatorPin\x10\xb2\x02\x12\x10\n\x0b\x41\x63tuatorPwm\x10\xb3\x02\x12\x13\n\x0e\x41\x63tuatorOffset\x10\xb4\x02\x12\r\n\x08\x42\x61lancer\x10\xb5\x02\x12\n\n\x05Mutex\x10\xb6\x02\x12\x14\n\x0fSetpointProfile\x10\xb7\x02\x12\x11\n\x0cWiFiSettings\x10\xb8\x02\x12\x12\n\rTouchSettings\x10\xb9\x02\x12\x14\n\x0f\x44isplaySettings\x10\xba\x02\x12\x0b\n\x06\x44S2413\x10\xbb\x02\x12\x14\n\x0f\x41\x63tuatorOneWire\x10\xbc\x02\x12\x0b\n\x06\x44S2408\x10\xbd\x02\x12\x14\n\x0f\x44igitalActuator\x10\xbe\x02\x12\x0f\n\nSpark3Pins\x10\xbf\x02\x12\x0f\n\nSpark2Pins\x10\xc0\x02\x12\x0f\n\nMotorValve\x10\xc1\x02\x12\x12\n\rActuatorLogic\x10\xc2\x02\x12\r\n\x08MockPins\x10\xc3\x02\x12\x14\n\x0fTempSensorCombi\x10\xc4\x02\x12\x16\n\x11OneWireGpioModule\x10\xc5\x02\x12\r\n\x08Sequence\x10\xc6\x02\x12\x17\n\x12TempSensorExternal\x10\xc8\x02\x12\x0c\n\x07\x46\x61stPwm\x10\xc9\x02\x12\x11\n\x0c\x44igitalInput\x10\xca\x02\x12\x1a\n\x15PrecisionAnalogModule\x10\xcb\x02\x12\x15\n\x10TempSensorAnalog\x10\xcc\x02\x12\x0e\n\tVariables\x10\xcd\x02:J\n\x05\x66ield\x12\x1d.google.protobuf.FieldOptions\x18\xd1\x86\x03 \x01(\x0b\x32\x13.brewblox.FieldOptsB\x05\x92?\x02\x18\x03:L\n\x03msg\x12\x1f.google.protobuf.MessageOptions\x18\xd1\x86\x03 \x01(\x0b\x32\x15.brewblox.MessageOptsB\x05\x92?\x02\x18\x03\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'brewblox_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  field._options = None
  field._serialized_options = b'\222?\002\030\003'
  msg._options = None
  msg._serialized_options = b'\222?\002\030\003'
  _MESSAGEOPTS.fields_by_name['impl']._options = None
  _MESSAGEOPTS.fields_by_name['impl']._serialized_options = b'\222?\002\020\005'
  _MESSAGEOPTS.fields_by_name['subtype']._options = None
  _MESSAGEOPTS.fields_by_name['subtype']._serialized_options = b'\222?\0028\020'
  _MESSAGEOPTS._options = None
  _MESSAGEOPTS._serialized_options = b'\222?\0020\001'
  _FIELDOPTS._options = None
  _FIELDOPTS._serialized_options = b'\222?\0020\001'
  _globals['_UNITTYPE']._serialized_start=510
  _globals['_UNITTYPE']._serialized_end=811
  _globals['_BLOCKTYPE']._serialized_start=814
  _globals['_BLOCKTYPE']._serialized_end=2244
  _globals['_MESSAGEOPTS']._serialized_start=76
  _globals['_MESSAGEOPTS']._serialized_end=200
  _globals['_FIELDOPTS']._serialized_start=203
  _globals['_FIELDOPTS']._serialized_end=507
# @@protoc_insertion_point(module_scope)
