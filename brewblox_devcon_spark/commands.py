from construct import (Byte, Const, Default, Enum, FlagsEnum, Int8sb, Int8ub,
                       Optional, Padding, PascalString, PrefixedArray,
                       Sequence, Struct, Terminated, VarInt, Adapter, RepeatUntil)


class VariableLengthIDAdapter(Adapter):

    def __init__(self):
        super().__init__(RepeatUntil(lambda obj, lst, ctx: obj & 0xF0 == 0x00, Byte))

    def _encode(self, obj, context):
        rewritten_list = []
        for idx, i in enumerate(obj):
            if idx != len(obj)-1:
                rewritten_list.append(i | 0x80)
            else:
                rewritten_list.append(i)

        return rewritten_list

    def _decode(self, obj, context):
        return list(map(lambda x: x & 0x0F, obj))


CBoxOpcodeEnum = Enum(Byte,
                      READ_VALUE=1,  # read a value
                      WRITE_VALUE=2,  # write a value
                      CREATE_OBJECT=3,  # add object in a container
                      DELETE_OBJECT=4,  # delete the object at the specified location
                      LIST_OBJECTS=5,  # list objects in a container
                      FREE_SLOT=6,  # retrieves the next free slot in a container
                      CREATE_PROFILE=7,  # create a new profile
                      DELETE_PROFILE=8,  # delete a profile
                      ACTIVATE_PROFILE=9,  # activate a profile
                      LOG_VALUES=10,  # log values from the selected container
                      RESET=11,  # reset the device
                      FREE_SLOT_ROOT=12,  # find the next free slot in the root container
                      UNUSED=13,  # unused
                      LIST_PROFILES=14,  # list the define profile IDs and the active profile
                      READ_SYSTEM_VALUE=15,  # read the value of a system object
                      SET_SYSTEM_VALUE=16,  # write the value of a system object
                      SET_MASK_VALUE=17
                      )


# FIXME
BrewBloxObjectTypeEnum = Enum(Byte,
                              TEMPERATURE_SENSOR=6,
                              SETPOINT_SIMPLE=7
                              )

CBoxCommand = Struct(
    "opcode" / CBoxOpcodeEnum,
)

# CREATE OBJECT
CreateObjectCommandHeader = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['CREATE_OBJECT'], Byte),
    "id" / VariableLengthIDAdapter()
)

CreateObjectCommandRequest = CreateObjectCommandHeader + Struct(
    "type" / BrewBloxObjectTypeEnum,
    "reserved_size" / Byte,
    "data" / PrefixedArray(VarInt, Byte)
)

CreateObjectCommandResponse = CreateObjectCommandHeader + Struct(
    "type" / Optional(BrewBloxObjectTypeEnum),
    "reserved_size" / Byte,
    "data" / Optional(PrefixedArray(VarInt, Byte)),
    "status" / Int8sb,
    Terminated
)

# CREATE PROFILE
CreateProfileCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['CREATE_PROFILE'], Byte),
)

CreateProfileCommandResponse = CreateProfileCommandRequest + Struct(
    "profile_id" / Int8sb,
    Terminated
)

# ACTIVATE PROFILE
ActivateProfileCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['ACTIVATE_PROFILE'], Byte),
    "profile_id" / Int8sb
)

ActivateProfileCommandResponse = ActivateProfileCommandRequest + Struct(
    "status" / Int8sb,
    Terminated
)

# LIST PROFILES
ListProfilesCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['LIST_PROFILES'], Byte),
)

ListProfilesCommandResponse = ListProfilesCommandRequest + Struct(
    "active_profile" / Int8ub
    #    "defined_profiles" / Sequence(Int8ub)
)


# LIST PROFILE OBJECTS
ListObjectsCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['LIST_OBJECTS'], Byte),
    "profile_id" / Int8sb
)

ListObjectsCommandResponse = ListObjectsCommandRequest + Struct(
    "status" / Int8sb,
    Padding(1),  # FIXME Protocol error?
    "objects" / Optional(Sequence(CreateObjectCommandRequest)),
    "terminator" / Const(0x00, Byte),
    Terminated
)

# READ VALUE
ReadValueCommandHeader = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['READ_VALUE'], Byte),
    "id" / VariableLengthIDAdapter(),
    "type" / BrewBloxObjectTypeEnum
)

ReadValueCommandRequest = ReadValueCommandHeader + Struct(
    "size" / Default(Int8ub, 0)
)

ReadValueCommandResponse = ReadValueCommandHeader + Struct(
    "expectedsize" / Int8sb,
    "real-type" / BrewBloxObjectTypeEnum,
    Padding(1),
    "data" / Optional(PascalString(VarInt, 'utf8')),  # TODO(Bob): should encoding be utf8?
    Terminated
)

# DELETE OBJECT
DeleteObjectCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['DELETE_OBJECT'], Byte),
    "id" / VariableLengthIDAdapter()
)

DeleteObjectCommandResponse = DeleteObjectCommandRequest + Struct(
    "status" / Int8sb,
    Terminated
)


# RESET
ResetCommandRequest = Struct(
    "opcode" / Const(CBoxOpcodeEnum.encmapping['RESET'], Byte),
    "flags" / FlagsEnum(Byte,
                        erase_eeprom=1,
                        hard_reset=2,
                        default=0)
)
