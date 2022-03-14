import enum
from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict, Union

from pydantic import BaseModel, validator


class BlockIdentity(BaseModel):
    id: Optional[str]
    nid: Optional[int]
    type: Optional[str]
    serviceId: Optional[str]


class Block(BaseModel):
    id: Optional[str]
    nid: Optional[int]
    type: str
    serviceId: Optional[str]
    data: dict[str, Any]


class FirmwareBlockIdentity(BaseModel):
    nid: int
    type: Optional[str]
    data: Optional[dict[str, Any]]


class FirmwareBlock(BaseModel):
    nid: int
    type: str
    data: dict[str, Any]


class StoreEntry(TypedDict):
    keys: tuple[str, int]
    data: dict


class Backup(BaseModel):
    blocks: list[Block]
    store: list[StoreEntry]


class BackupLoadResult(BaseModel):
    messages: list[str]


class BlockNameChange(BaseModel):
    existing: str
    desired: str


class ResetReason(enum.Enum):
    NONE = '00'
    UNKNOWN = '0A'
    # Hardware
    PIN_RESET = '14'
    POWER_MANAGEMENT = '1E'
    POWER_DOWN = '28'
    POWER_BROWNOUT = '32'
    WATCHDOG = '3C'
    # Software
    UPDATE = '46'
    UPDATE_ERROR = '50'
    UPDATE_TIMEOUT = '5A'
    FACTORY_RESET = '64'
    SAFE_MODE = '6E'
    DFU_MODE = '78'
    PANIC = '82'
    USER = '8C'


class ResetData(enum.Enum):
    NOT_SPECIFIED = '00'
    WATCHDOG = '01'
    CBOX_RESET = '02'
    CBOX_FACTORY_RESET = '03'
    FIRMWARE_UPDATE_FAILED = '04'
    LISTENING_MODE_EXIT = '05'
    FIRMWARE_UPDATE_SUCCESS = '06'
    OUT_OF_MEMORY = '07'


class Opcode(enum.Enum):
    OPCODE_NONE = 0
    OPCODE_READ_OBJECT = 1
    OPCODE_WRITE_OBJECT = 2
    OPCODE_CREATE_OBJECT = 3
    OPCODE_DELETE_OBJECT = 4
    OPCODE_LIST_OBJECTS = 5
    OPCODE_READ_STORED_OBJECT = 6
    OPCODE_LIST_STORED_OBJECTS = 7
    OPCODE_CLEAR_OBJECTS = 8
    OPCODE_REBOOT = 9
    OPCODE_FACTORY_RESET = 10
    OPCODE_LIST_COMPATIBLE_OBJECTS = 11
    OPCODE_DISCOVER_OBJECTS = 12
    OPCODE_FIRMWARE_UPDATE = 100


class ErrorCode(enum.Enum):
    ERR_OK = 0
    ERR_UNKNOWN_ERROR = 1

    # object creation
    ERR_INSUFFICIENT_HEAP = 4

    # generic stream errors
    ERR_STREAM_ERROR_UNSPECIFIED = 8
    ERR_OUTPUT_STREAM_WRITE_ERROR = 9
    ERR_INPUT_STREAM_READ_ERROR = 10
    ERR_INPUT_STREAM_DECODING_ERROR = 11
    ERR_OUTPUT_STREAM_ENCODING_ERROR = 12

    # storage errors
    ERR_INSUFFICIENT_PERSISTENT_STORAGE = 16
    ERR_PERSISTED_OBJECT_NOT_FOUND = 17
    ERR_INVALID_PERSISTED_BLOCK_TYPE = 18
    ERR_COULD_NOT_READ_PERSISTED_BLOCK_SIZE = 19
    ERR_PERSISTED_BLOCK_STREAM_ERROR = 20
    ERR_PERSISTED_STORAGE_WRITE_ERROR = 21
    ERR_CRC_ERROR_IN_STORED_OBJECT = 22

    # invalid actions
    ERR_OBJECT_NOT_WRITABLE = 32
    ERR_OBJECT_NOT_READABLE = 33
    ERR_OBJECT_NOT_CREATABLE = 34
    ERR_OBJECT_NOT_DELETABLE = 35

    # invalid parameters
    ERR_INVALID_COMMAND = 63
    ERR_INVALID_OBJECT_ID = 64
    ERR_INVALID_OBJECT_TYPE = 65
    ERR_INVALID_OBJECT_GROUPS = 66
    ERR_CRC_ERROR_IN_COMMAND = 67
    ERR_OBJECT_DATA_NOT_ACCEPTED = 68

    # freak events that should not be possible
    ERR_WRITE_TO_INACTIVE_OBJECT = 200


class EncodedPayload(BaseModel):
    blockId: int
    objtype: Optional[Union[int, str]]
    subtype: Optional[Union[int, str]]
    data: Optional[str]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodedPayload(BaseModel):
    blockId: int
    objtype: Optional[Union[int, str]]
    subtype: Optional[Union[int, str]]
    data: Optional[dict]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class ControlboxRequest(BaseModel):
    msgId: int
    opcode: Opcode

    @validator('opcode', pre=True)
    def from_string_opcode(cls, v):
        if isinstance(v, str):
            v = Opcode[v]
        return v


class EncodedRequest(ControlboxRequest):
    payload: Optional[EncodedPayload]


class DecodedRequest(ControlboxRequest):
    payload: Optional[DecodedPayload]


class ControlboxResponse(BaseModel):
    msgId: int
    error: ErrorCode

    @validator('error', pre=True)
    def from_string_error(cls, v):
        if isinstance(v, str):
            v = ErrorCode[v]
        return v


class EncodedResponse(ControlboxResponse):
    payload: list[EncodedPayload]


class DecodedResponse(ControlboxResponse):
    payload: list[DecodedPayload]


class EncodeArgs(BaseModel):
    objtype: Union[int, str]
    subtype: Optional[Union[int, str]]
    data: Optional[dict]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodeArgs(BaseModel):
    objtype: Union[int, str]
    subtype: Optional[Union[int, str]]
    data: Optional[str]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


@dataclass
class HandshakeMessage:
    name: str
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str
    system_version: str
    platform: str
    reset_reason_hex: str
    reset_data_hex: str
    device_id: str = field(default='')
    reset_reason: str = field(init=False)
    reset_data: str = field(init=False)

    def __post_init__(self):
        self.reset_reason = ResetReason(self.reset_reason_hex.upper()).name
        try:
            self.reset_data = ResetData(self.reset_data_hex.upper()).name
        except Exception:
            self.reset_data = self.reset_data_hex.upper()


class SharedInfo(BaseModel):
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str
    device_id: str

    @validator('device_id')
    def lower_device_id(cls, v: str):
        return v.lower()

    @validator('firmware_version', 'proto_version')
    def truncate_version(cls, v: str):
        # We only compare the first 8 characters of git hashes
        return v[:8]


class ServiceInfo(SharedInfo):
    name: str


class DeviceInfo(SharedInfo):
    system_version: str
    platform: str
    reset_reason: str


class HandshakeInfo(BaseModel):
    is_compatible_firmware: bool
    is_latest_firmware: bool
    is_valid_device_id: bool


class StatusDescription(BaseModel):
    device_address: Optional[str]
    connection_kind: Optional[str]

    service_info: ServiceInfo
    device_info: Optional[DeviceInfo]
    handshake_info: Optional[HandshakeInfo]

    is_autoconnecting: bool
    is_connected: bool
    is_acknowledged: bool
    is_synchronized: bool
    is_updating: bool
