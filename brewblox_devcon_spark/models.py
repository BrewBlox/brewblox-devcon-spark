import enum
from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict, Union

from brewblox_service.models import BaseServiceConfig
from pydantic import BaseModel, Field, validator


class ServiceFirmwareIni(TypedDict):
    firmware_version: str
    firmware_date: str
    firmware_sha: str
    proto_version: str
    proto_date: str
    system_version: str


class DiscoveryType(enum.Enum):
    all = 1
    usb = 2
    mdns = 3
    mqtt = 4

    # Aliases for backwards compatibility
    wifi = 3
    lan = 3

    def __str__(self):
        return self.name


class ServiceConfig(BaseServiceConfig):
    # Device options
    simulation: bool
    mock: bool
    device_host: Optional[str]
    device_port: int
    device_serial: Optional[str]
    device_id: Optional[str]
    discovery: DiscoveryType
    display_ws_port: int

    # Network options
    command_timeout: float
    broadcast_interval: float
    isolated: bool
    datastore_topic: str

    # Firmware options
    skip_version_check: bool

    # Backup options
    backup_interval: float
    backup_retry_interval: float

    # Time sync options
    time_sync_interval: float


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


class BlockList(BaseModel):
    __root__: list[Block]


class BlockIdentityList(BaseModel):
    __root__: list[BlockIdentity]


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
    BLOCK_STORED_READ = 16
    BLOCK_STORED_READ_ALL = 17

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


class MaskMode(enum.Enum):
    NO_MASK = 0
    INCLUSIVE = 1
    EXCLUSIVE = 2


class BasePayload(BaseModel):
    blockId: int
    mask: list[int] = Field(default_factory=list)
    maskMode: MaskMode = Field(default=MaskMode.NO_MASK)

    @validator('maskMode', pre=True)
    def from_raw_mask_mode(cls, v):
        if isinstance(v, str):
            return MaskMode[v]
        return MaskMode(v)

    def clean_dict(self):
        return {
            **self.dict(),
            'maskMode': self.maskMode.name,
        }


class EncodedPayload(BasePayload):
    blockType: Optional[Union[int, str]]
    subtype: Optional[Union[int, str]]
    content: str = Field(default='')

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodedPayload(BasePayload):
    blockType: Optional[str]
    subtype: Optional[str]
    content: Optional[dict]


class BaseRequest(BaseModel):
    msgId: int
    opcode: Opcode
    payload: Optional[BasePayload]

    @validator('opcode', pre=True)
    def from_raw_opcode(cls, v):
        if isinstance(v, str):
            return Opcode[v]
        return Opcode(v)

    def clean_dict(self):
        return {
            **self.dict(),
            'opcode': self.opcode.name,
            'payload': self.payload.clean_dict() if self.payload else None,
        }


class IntermediateRequest(BaseRequest):
    payload: Optional[EncodedPayload]


class DecodedRequest(BaseRequest):
    payload: Optional[DecodedPayload]


class BaseResponse(BaseModel):
    msgId: int
    error: ErrorCode
    payload: list[BasePayload]

    @validator('error', pre=True)
    def from_raw_error(cls, v):
        if isinstance(v, str):
            return ErrorCode[v]
        return ErrorCode(v)

    def clean_dict(self):
        return {
            **self.dict(),
            'error': self.error.name,
            'payload': [v.clean_dict() for v in self.payload]
        }


class IntermediateResponse(BaseResponse):
    payload: list[EncodedPayload]


class DecodedResponse(BaseResponse):
    payload: list[DecodedPayload]


class EncodedMessage(BaseModel):
    message: str


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
    device_id: str = Field(default='')
    reset_reason: str = Field(init=False)
    reset_data: str = Field(init=False)

    def __post_init__(self):
        self.reset_reason = ResetReason(self.reset_reason_hex.upper()).name
        try:
            self.reset_data = ResetData(self.reset_data_hex.upper()).name
        except Exception:
            self.reset_data = self.reset_data_hex.upper()


class FirmwareDescription(BaseModel):
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str

    @validator('firmware_version', 'proto_version')
    def truncate_version(cls, v: str):
        # We only compare the first 8 characters of git hashes
        return v[:8]


class DeviceDescription(BaseModel):
    device_id: str

    @validator('device_id')
    def lower_device_id(cls, v: str):
        return v.lower()


class ServiceDescription(BaseModel):
    name: str
    firmware: FirmwareDescription
    device: DeviceDescription


class ControllerDescription(BaseModel):
    system_version: str
    platform: str
    reset_reason: str
    firmware: FirmwareDescription
    device: DeviceDescription


ConnectionKind_ = Literal[
    'MOCK',
    'SIM',
    'USB',
    'TCP',
    'MQTT'
]

ConnectionStatus_ = Literal[
    'DISCONNECTED',
    'CONNECTED',
    'ACKNOWLEDGED',
    'SYNCHRONIZED',
    'UPDATING',
]

FirmwareError_ = Literal[
    'INCOMPATIBLE',
    'MISMATCHED',
]

IdentityError_ = Literal[
    'INCOMPATIBLE',
    'WILDCARD_ID',
]


class ServiceStatusDescription(BaseModel):
    enabled: bool
    service: ServiceDescription
    controller: Optional[ControllerDescription]
    address: Optional[str]

    connection_kind: Optional[ConnectionKind_]
    connection_status: ConnectionStatus_
    firmware_error: Optional[FirmwareError_]
    identity_error: Optional[IdentityError_]


class BackupIdentity(BaseModel):
    name: str


class Backup(BaseModel):
    # Older backups won't have these fields
    # They will not be used when loading backups
    name: Optional[str]
    timestamp: Optional[str]
    firmware: Optional[FirmwareDescription]
    device: Optional[DeviceDescription]

    blocks: list[Block]
    store: list[StoreEntry]


class BackupApplyResult(BaseModel):
    messages: list[str]
