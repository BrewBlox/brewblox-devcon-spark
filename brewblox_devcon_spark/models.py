import enum
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal, Self

from pydantic import (BaseModel, ConfigDict, Field, ValidationInfo,
                      field_validator, model_validator)
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class ServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.appenv',
        env_prefix='brewblox_',
        case_sensitive=False,
        json_schema_extra='ignore',
    )

    # Generic options
    name: str  # Required
    debug: bool = False
    debugger: bool = False

    mqtt_protocol: Literal['mqtt', 'mqtts'] = 'mqtt'
    mqtt_host: str = 'eventbus'
    mqtt_port: int = 1883

    redis_host: str = 'redis'
    redis_port: int = 6379

    state_topic: str = 'brewcast/state'
    history_topic: str = 'brewcast/history'
    datastore_topic: str = 'brewcast/datastore'
    blocks_topic: str = 'brewcast/spark/blocks'

    # Device options
    simulation: bool = False
    mock: bool = False
    device_host: str | None = None
    device_port: int = 8332
    device_serial: str | None = None
    device_id: str | None = None
    discovery: DiscoveryType = DiscoveryType.all
    display_ws_port: int = 7377

    # Network options
    command_timeout: timedelta = timedelta(seconds=20)
    broadcast_interval: timedelta = timedelta(seconds=5)

    # Firmware options
    skip_version_check: bool = False

    # Backup options
    backup_interval: timedelta = timedelta(hours=1)
    backup_retry_interval: timedelta = timedelta(minutes=5)

    # Time sync options
    time_sync_interval: timedelta = timedelta(minutes=15)

    @model_validator(mode='after')
    def default_device_id(self) -> Self:
        if self.device_id is None and (self.simulation or self.mock):
            self.device_id = '123456789012345678901234'
        return self


class FirmwareConfig(BaseModel):
    firmware_version: str
    firmware_date: str
    firmware_sha: str
    proto_version: str
    proto_date: str
    system_version: str


class BlockIdentity(BaseModel):
    id: str | None = None
    nid: int | None = None
    type: str | None = None
    serviceId: str | None = None


class Block(BaseModel):
    id: str | None = None
    nid: int | None = None
    type: str
    serviceId: str | None = None
    data: dict[str, Any]


class FirmwareBlockIdentity(BaseModel):
    nid: int
    type: str | None = None
    data: dict[str, Any] | None = None


class FirmwareBlock(BaseModel):
    nid: int
    type: str
    data: dict[str, Any]


class TwinkeyEntry(BaseModel):
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
    maskMode: MaskMode = MaskMode.NO_MASK

    # @validator('maskMode', pre=True)
    # def from_raw_mask_mode(cls, v):
    #     if isinstance(v, str):
    #         return MaskMode[v]
    #     return MaskMode(v)

    # def clean_dict(self):
    #     return {
    #         **self.dict(),
    #         'maskMode': self.maskMode.name,
    #     }


class EncodedPayload(BasePayload):
    blockType:  int | str | None = None
    subtype:  int | str | None = None
    content: str = ''

    class Config:
        # ensures integers in Union[int, str] are parsed correctly
        smart_union = True


class DecodedPayload(BasePayload):
    blockType: str | None = None
    subtype: str | None = None
    content: dict | None = None


class BaseRequest(BaseModel):
    msgId: int
    opcode: Opcode
    payload: BasePayload | None = None

    # Maybe
    # @field_validator('opcode', mode='before')
    # @classmethod
    # def from_raw_opcode(cls, v):
    #     if isinstance(v, str):
    #         return Opcode[v]
    #     return Opcode(v)

    # def clean_dict(self):
    #     return {
    #         **self.dict(),
    #         'opcode': self.opcode.name,
    #         'payload': self.payload.clean_dict() if self.payload else None,
    #     }


class IntermediateRequest(BaseRequest):
    payload: EncodedPayload | None


class DecodedRequest(BaseRequest):
    payload: DecodedPayload | None


class BaseResponse(BaseModel):
    msgId: int
    error: ErrorCode
    payload: list[BasePayload]

    # # Maybe???
    # @field_validator('error', mode='before')
    # @classmethod
    # def from_raw_error(cls, v):
    #     if isinstance(v, str):
    #         return ErrorCode[v]
    #     return ErrorCode(v)


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

    @field_validator('firmware_version', 'proto_version')
    @classmethod
    def truncate_version(cls, v: str, info: ValidationInfo):
        # We only compare the first 8 characters of git hashes
        return v[:8]


class DeviceDescription(BaseModel):
    device_id: str

    @model_validator(mode='after')
    def lower_device_id(self) -> Self:
        self.device_id = self.device_id.lower()
        return self


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
    controller: ControllerDescription | None = None
    address: str | None = None

    connection_kind: ConnectionKind_ | None = None
    connection_status: ConnectionStatus_
    firmware_error: FirmwareError_ | None = None
    identity_error: IdentityError_ | None = None


class BackupIdentity(BaseModel):
    name: str


class Backup(BaseModel):
    # Older backups won't have these fields
    # They will not be used when loading backups
    name: str | None = None
    timestamp: str | None = None
    firmware: FirmwareDescription | None = None
    device: DeviceDescription | None = None

    blocks: list[Block]
    store: list[TwinkeyEntry]


class BackupApplyResult(BaseModel):
    messages: list[str]


class AutoconnectSettings(BaseModel):
    enabled: bool


class ErrorResponse(BaseModel):
    error: str
    details: str


class FirmwareFlashResponse(BaseModel):
    address: str
    version: str


class PingResponse(BaseModel):
    ping: Literal['pong'] = 'pong'


class DatastoreValue(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )

    namespace: str
    id: str


class DatastoreSingleQuery(BaseModel):
    namespace: str
    id: str


class DatastoreMultiQuery(BaseModel):
    namespace: str
    ids: list[str] | None = None
    filter: str | None = None


class DatastoreSingleValueBox(BaseModel):
    value: DatastoreValue | None


class DatastoreMultiValueBox(BaseModel):
    values: list[DatastoreValue]


class TwinkeyEntriesValue(DatastoreValue):
    data: list[TwinkeyEntry]


class TwinkeyEntriesBox(BaseModel):
    value: TwinkeyEntriesValue | None


class ServiceConfigData(BaseModel):
    model_config = ConfigDict(
        extra='ignore',
    )

    reconnect_delay: float = 0
    autoconnecting: bool = True


class ServiceConfigValue(DatastoreValue):
    data: ServiceConfigData = Field(default_factory=ServiceConfigData)


class ServiceConfigBox(BaseModel):
    value: ServiceConfigValue | None
