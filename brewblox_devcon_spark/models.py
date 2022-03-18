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
    NONE = 0
    VERSION = 1

    BLOCK_READ = 10
    BLOCK_READ_ALL = 11
    BLOCK_WRITE = 12
    BLOCK_CREATE = 13
    BLOCK_DELETE = 14
    BLOCK_DISCOVER = 15

    STORAGE_READ = 20
    STORAGE_READ_ALL = 21

    REBOOT = 30
    CLEAR_BLOCKS = 31
    CLEAR_WIFI = 32
    FACTORY_RESET = 33

    FIRMWARE_UPDATE = 40


class ErrorCode(enum.Enum):
    OK = 0
    UNKNOWN_ERROR = 1
    INVALID_OPCODE = 2

    # Memory errors
    INSUFFICIENT_HEAP = 4
    INSUFFICIENT_STORAGE = 5

    # Network I/O errors
    NETWORK_ERROR = 10
    NETWORK_READ_ERROR = 11
    NETWORK_DECODING_ERROR = 12
    NETWORK_WRITE_ERROR = 13
    NETWORK_ENCODING_ERROR = 14

    # Storage I/O errors
    STORAGE_ERROR = 20
    STORAGE_READ_ERROR = 21
    STORAGE_DECODING_ERROR = 22
    STORAGE_CRC_ERROR = 23
    STORAGE_WRITE_ERROR = 24
    STORAGE_ENCODING_ERROR = 25

    # Invalid actions
    BLOCK_NOT_WRITABLE = 30
    BLOCK_NOT_READABLE = 31
    BLOCK_NOT_CREATABLE = 32
    BLOCK_NOT_DELETABLE = 33

    # Invalid block data
    INVALID_BLOCK = 40
    INVALID_BLOCK_ID = 41
    INVALID_BLOCK_TYPE = 42
    INVALID_BLOCK_SUBTYPE = 43
    INVALID_BLOCK_CONTENT = 44

    # Invalid stored block data
    INVALID_STORED_BLOCK = 50
    INVALID_STORED_BLOCK_ID = 51
    INVALID_STORED_BLOCK_TYPE = 52
    INVALID_STORED_BLOCK_SUBTYPE = 53
    INVALID_STORED_BLOCK_CONTENT = 54


class EncodedPayload(BaseModel):
    blockId: int
    blockType: Optional[Union[int, str]]
    subtype: Optional[Union[int, str]]
    content: Optional[str]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodedPayload(BaseModel):
    blockId: int
    blockType: Optional[Union[int, str]]
    subtype: Optional[Union[int, str]]
    content: Optional[dict]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class BaseRequest(BaseModel):
    msgId: int
    opcode: Opcode

    @validator('opcode', pre=True)
    def from_string_opcode(cls, v):
        if isinstance(v, str):
            v = Opcode[v]
        return v


class EncodedRequest(BaseRequest):
    payload: Optional[EncodedPayload]


class DecodedRequest(BaseRequest):
    payload: Optional[DecodedPayload]


class BaseResponse(BaseModel):
    msgId: int
    error: ErrorCode

    @validator('error', pre=True)
    def from_string_error(cls, v):
        if isinstance(v, str):
            v = ErrorCode[v]
        return v


class EncodedResponse(BaseResponse):
    payload: list[EncodedPayload]


class DecodedResponse(BaseResponse):
    payload: list[DecodedPayload]


class EncodeArgs(BaseModel):
    blockType: Union[int, str]
    subtype: Optional[Union[int, str]]
    content: Optional[dict]

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodeArgs(BaseModel):
    blockType: Union[int, str]
    subtype: Optional[Union[int, str]]
    content: Optional[str]

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
