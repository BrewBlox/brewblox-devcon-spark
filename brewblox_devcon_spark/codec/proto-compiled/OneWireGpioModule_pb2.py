# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: OneWireGpioModule.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import brewblox_pb2 as brewblox__pb2
import nanopb_pb2 as nanopb__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x17OneWireGpioModule.proto\x12\x16\x62lox.OneWireGpioModule\x1a\x0e\x62rewblox.proto\x1a\x0cnanopb.proto\"\x95\x02\n\x11GpioModuleChannel\x12\x11\n\x02id\x18\x01 \x01(\rB\x05\x92?\x02\x38\x08\x12:\n\ndeviceType\x18\x02 \x01(\x0e\x32&.blox.OneWireGpioModule.GpioDeviceType\x12\x1d\n\x08pinsMask\x18\x03 \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02P\x01\x12\x14\n\x05width\x18\x04 \x01(\rB\x05\x92?\x02\x38\x08\x12\x13\n\x04name\x18\x05 \x01(\tB\x05\x92?\x02\x08 \x12#\n\x0c\x63\x61pabilities\x18\x06 \x01(\rB\r\x92?\x02\x38\x10\x8a\xb5\x18\x04(\x01P\x01\x12!\n\tclaimedBy\x18\x07 \x01(\rB\x0e\x92?\x02\x38\x10\x8a\xb5\x18\x05\x18\xff\x01(\x01\x12\x1f\n\nerrorFlags\x18\x08 \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02P\x01\"\xd6\x05\n\x05\x42lock\x12\x42\n\x08\x63hannels\x18\x01 \x03(\x0b\x32).blox.OneWireGpioModule.GpioModuleChannelB\x05\x92?\x02\x10\x08\x12\x1d\n\x0emodulePosition\x18\x02 \x01(\rB\x05\x92?\x02\x38\x08\x12!\n\x0cmoduleStatus\x18\x03 \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02P\x01\x12$\n\rpullUpDesired\x18\x04 \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12#\n\x0cpullUpStatus\x18\x05 \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12\'\n\x10pullUpWhenActive\x18\x06 \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12)\n\x12pullUpWhenInactive\x18\x07 \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12&\n\x0fpullDownDesired\x18\x08 \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12%\n\x0epullDownStatus\x18\t \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12)\n\x12pullDownWhenActive\x18\n \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12+\n\x14pullDownWhenInactive\x18\x0b \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12\"\n\x0boverCurrent\x18\x0c \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12\x1f\n\x08openLoad\x18\r \x01(\rB\r\x92?\x02\x38\x08\x8a\xb5\x18\x04(\x01P\x01\x12\x18\n\x10useExternalPower\x18\x0e \x01(\x08\x12$\n\x0f\x66\x61ultsHistory5m\x18\x0f \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02P\x01\x12%\n\x10\x66\x61ultsHistory60m\x18\x10 \x01(\rB\x0b\x92?\x02\x38\x08\x8a\xb5\x18\x02P\x01\x12&\n\x11moduleStatusClear\x18Z \x01(\rB\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01\x12 \n\x0b\x63learFaults\x18  \x01(\x08\x42\x0b\x92?\x02\x18\x03\x8a\xb5\x18\x02H\x01:\x0b\x8a\xb5\x18\x07\x18\xc5\x02J\x02\n\x0c*\xad\x05\n\x0eGpioDeviceType\x12\x11\n\rGPIO_DEV_NONE\x10\x00\x12\x13\n\x0fGPIO_DEV_SSR_2P\x10\x01\x12\x13\n\x0fGPIO_DEV_SSR_1P\x10\x02\x12 \n\x1cGPIO_DEV_MECHANICAL_RELAY_2P\x10\x03\x12*\n&GPIO_DEV_MECHANICAL_RELAY_1P_HIGH_SIDE\x10\x04\x12)\n%GPIO_DEV_MECHANICAL_RELAY_1P_LOW_SIDE\x10\x05\x12\x14\n\x10GPIO_DEV_COIL_2P\x10\x06\x12\"\n\x1eGPIO_DEV_COIL_2P_BIDIRECTIONAL\x10\x07\x12\x1e\n\x1aGPIO_DEV_COIL_1P_HIGH_SIDE\x10\x08\x12\x1d\n\x19GPIO_DEV_COIL_1P_LOW_SIDE\x10\t\x12\x15\n\x11GPIO_DEV_MOTOR_2P\x10\n\x12#\n\x1fGPIO_DEV_MOTOR_2P_BIDIRECTIONAL\x10\x0b\x12\x1f\n\x1bGPIO_DEV_MOTOR_1P_HIGH_SIDE\x10\x0c\x12\x1e\n\x1aGPIO_DEV_MOTOR_1P_LOW_SIDE\x10\r\x12\"\n\x1eGPIO_DEV_DETECT_LOW_CURRENT_2P\x10\x0e\x12&\n\"GPIO_DEV_DETECT_LOW_CURRENT_1P_GND\x10\x0f\x12\x15\n\x11GPIO_DEV_POWER_1P\x10\x11\x12)\n%GPIO_DEV_DETECT_HIGH_CURRENT_1P_POWER\x10\x12\x12\x13\n\x0fGPIO_DEV_GND_1P\x10\x13\x12\'\n#GPIO_DEV_DETECT_HIGH_CURRENT_1P_GND\x10\x14\x12#\n\x1fGPIO_DEV_DETECT_HIGH_CURRENT_2P\x10\x15*\x8a\x02\n\x0eGpioErrorFlags\x12\x11\n\rGPIO_ERR_NONE\x10\x00\x12\x1b\n\x17GPIO_ERR_POWER_ON_RESET\x10\x01\x12\x18\n\x14GPIO_ERR_OVERVOLTAGE\x10\x02\x12\x19\n\x15GPIO_ERR_UNDERVOLTAGE\x10\x04\x12\x18\n\x14GPIO_ERR_OVERCURRENT\x10\x08\x12\x16\n\x12GPIO_ERR_OPEN_LOAD\x10\x10\x12$\n GPIO_ERR_OVERTEMPERATURE_WARNING\x10 \x12\"\n\x1eGPIO_ERR_OVERTEMPERATURE_ERROR\x10@\x12\x17\n\x12GPIO_ERR_SPI_ERROR\x10\x80\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'OneWireGpioModule_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _GPIOMODULECHANNEL.fields_by_name['id']._options = None
  _GPIOMODULECHANNEL.fields_by_name['id']._serialized_options = b'\222?\0028\010'
  _GPIOMODULECHANNEL.fields_by_name['pinsMask']._options = None
  _GPIOMODULECHANNEL.fields_by_name['pinsMask']._serialized_options = b'\222?\0028\010\212\265\030\002P\001'
  _GPIOMODULECHANNEL.fields_by_name['width']._options = None
  _GPIOMODULECHANNEL.fields_by_name['width']._serialized_options = b'\222?\0028\010'
  _GPIOMODULECHANNEL.fields_by_name['name']._options = None
  _GPIOMODULECHANNEL.fields_by_name['name']._serialized_options = b'\222?\002\010 '
  _GPIOMODULECHANNEL.fields_by_name['capabilities']._options = None
  _GPIOMODULECHANNEL.fields_by_name['capabilities']._serialized_options = b'\222?\0028\020\212\265\030\004(\001P\001'
  _GPIOMODULECHANNEL.fields_by_name['claimedBy']._options = None
  _GPIOMODULECHANNEL.fields_by_name['claimedBy']._serialized_options = b'\222?\0028\020\212\265\030\005\030\377\001(\001'
  _GPIOMODULECHANNEL.fields_by_name['errorFlags']._options = None
  _GPIOMODULECHANNEL.fields_by_name['errorFlags']._serialized_options = b'\222?\0028\010\212\265\030\002P\001'
  _BLOCK.fields_by_name['channels']._options = None
  _BLOCK.fields_by_name['channels']._serialized_options = b'\222?\002\020\010'
  _BLOCK.fields_by_name['modulePosition']._options = None
  _BLOCK.fields_by_name['modulePosition']._serialized_options = b'\222?\0028\010'
  _BLOCK.fields_by_name['moduleStatus']._options = None
  _BLOCK.fields_by_name['moduleStatus']._serialized_options = b'\222?\0028\010\212\265\030\002P\001'
  _BLOCK.fields_by_name['pullUpDesired']._options = None
  _BLOCK.fields_by_name['pullUpDesired']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullUpStatus']._options = None
  _BLOCK.fields_by_name['pullUpStatus']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullUpWhenActive']._options = None
  _BLOCK.fields_by_name['pullUpWhenActive']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullUpWhenInactive']._options = None
  _BLOCK.fields_by_name['pullUpWhenInactive']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullDownDesired']._options = None
  _BLOCK.fields_by_name['pullDownDesired']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullDownStatus']._options = None
  _BLOCK.fields_by_name['pullDownStatus']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullDownWhenActive']._options = None
  _BLOCK.fields_by_name['pullDownWhenActive']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['pullDownWhenInactive']._options = None
  _BLOCK.fields_by_name['pullDownWhenInactive']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['overCurrent']._options = None
  _BLOCK.fields_by_name['overCurrent']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['openLoad']._options = None
  _BLOCK.fields_by_name['openLoad']._serialized_options = b'\222?\0028\010\212\265\030\004(\001P\001'
  _BLOCK.fields_by_name['faultsHistory5m']._options = None
  _BLOCK.fields_by_name['faultsHistory5m']._serialized_options = b'\222?\0028\010\212\265\030\002P\001'
  _BLOCK.fields_by_name['faultsHistory60m']._options = None
  _BLOCK.fields_by_name['faultsHistory60m']._serialized_options = b'\222?\0028\010\212\265\030\002P\001'
  _BLOCK.fields_by_name['moduleStatusClear']._options = None
  _BLOCK.fields_by_name['moduleStatusClear']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK.fields_by_name['clearFaults']._options = None
  _BLOCK.fields_by_name['clearFaults']._serialized_options = b'\222?\002\030\003\212\265\030\002H\001'
  _BLOCK._options = None
  _BLOCK._serialized_options = b'\212\265\030\007\030\305\002J\002\n\014'
  _globals['_GPIODEVICETYPE']._serialized_start=1091
  _globals['_GPIODEVICETYPE']._serialized_end=1776
  _globals['_GPIOERRORFLAGS']._serialized_start=1779
  _globals['_GPIOERRORFLAGS']._serialized_end=2045
  _globals['_GPIOMODULECHANNEL']._serialized_start=82
  _globals['_GPIOMODULECHANNEL']._serialized_end=359
  _globals['_BLOCK']._serialized_start=362
  _globals['_BLOCK']._serialized_end=1088
# @@protoc_insertion_point(module_scope)
