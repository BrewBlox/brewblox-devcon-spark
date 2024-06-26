import enum
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (BaseModel, ConfigDict, Field, ValidationInfo,
                      computed_field, field_validator, model_validator)
from pydantic.functional_validators import BeforeValidator
from pydantic_core import SchemaValidator, core_schema
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytimeparse.timeparse import timeparse

from . import const

pydantic_timedelta_validator = SchemaValidator(core_schema.timedelta_schema())


def parse_timedelta(value: str | int | float | timedelta) -> timedelta:
    if isinstance(value, timedelta):
        return value

    try:
        value = float(value)
    except TypeError:
        value = None
    except ValueError:
        value = timeparse(value) or value

    return pydantic_timedelta_validator.validate_python(value)


timedelta_field = Annotated[timedelta, BeforeValidator(parse_timedelta)]


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

    def __str__(self):
        return self.name


class ResetData(enum.Enum):
    NOT_SPECIFIED = '00'
    WATCHDOG = '01'
    CBOX_RESET = '02'
    CBOX_FACTORY_RESET = '03'
    FIRMWARE_UPDATE_FAILED = '04'
    LISTENING_MODE_EXIT = '05'
    FIRMWARE_UPDATE_SUCCESS = '06'
    OUT_OF_MEMORY = '07'

    def __str__(self):
        return self.name


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

    NAME_READ = 50
    NAME_READ_ALL = 51
    NAME_WRITE = 52

    REBOOT = 30
    CLEAR_BLOCKS = 31
    CLEAR_WIFI = 32
    FACTORY_RESET = 33

    FIRMWARE_UPDATE = 40


class ErrorCode(enum.Enum):
    OK = 0
    UNKNOWN_ERROR = 1
    INVALID_OPCODE = 2
    NOT_ALLOWED = 3

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
    STORAGE_OUT_OF_BOUNDS_ERROR = 26

    # Invalid actions
    BLOCK_NOT_WRITABLE = 30
    BLOCK_NOT_READABLE = 31
    BLOCK_NOT_CREATABLE = 32
    BLOCK_NOT_DELETABLE = 33

    # Invalid block data
    INVALID_BLOCK = 40
    INVALID_BLOCK_ID = 41
    INVALID_BLOCK_TYPE = 42
    INVALID_BLOCK_CONTENT = 44
    INVALID_BLOCK_NAME = 45

    # Invalid stored block data
    INVALID_STORED_BLOCK = 50
    INVALID_STORED_BLOCK_ID = 51
    INVALID_STORED_BLOCK_TYPE = 52
    INVALID_STORED_BLOCK_CONTENT = 54
    INVALID_STORED_BLOCK_NAME = 55

    # Invalid block identifiers
    DUPLICATE_BLOCK_ID = 60
    DUPLICATE_BLOCK_NAME = 61


class ReadMode(enum.Enum):
    DEFAULT = 0
    STORED = 1
    LOGGED = 2


class MaskMode(enum.Enum):
    NO_MASK = 0
    INCLUSIVE = 1
    EXCLUSIVE = 2


def parse_enum(cls: type[enum.Enum], v: Any):
    """Return enum value if `v` matches either name or value"""
    try:
        return cls[v]
    except KeyError:
        return cls(v)


DiscoveryType_field = Annotated[DiscoveryType, BeforeValidator(partial(parse_enum, DiscoveryType))]
ResetReason_field = Annotated[ResetReason, BeforeValidator(partial(parse_enum, ResetReason))]
ResetData_field = Annotated[ResetData, BeforeValidator(partial(parse_enum, ResetData))]
Opcode_field = Annotated[Opcode, BeforeValidator(partial(parse_enum, Opcode))]
ErrorCode_field = Annotated[ErrorCode, BeforeValidator(partial(parse_enum, ErrorCode))]
ReadMode_field = Annotated[ReadMode, BeforeValidator(partial(parse_enum, ReadMode))]
MaskMode_field = Annotated[MaskMode, BeforeValidator(partial(parse_enum, MaskMode))]


class ServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.appenv',
        env_prefix='brewblox_spark_',
        case_sensitive=False,
        json_schema_extra='ignore',
    )

    # Generic options
    name: str = ''  # autodetect if not set
    debug: bool = False
    trace: bool = False
    debugger: bool = False

    # MQTT options
    mqtt_protocol: Literal['mqtt', 'mqtts'] = 'mqtt'
    mqtt_host: str = 'eventbus'
    mqtt_port: int = 1883

    state_topic: str = 'brewcast/state'
    history_topic: str = 'brewcast/history'
    datastore_topic: str = 'brewcast/datastore'
    blocks_topic: str = 'brewcast/spark/blocks'

    # HTTP client options
    http_client_interval: timedelta_field = timedelta(seconds=1)
    http_client_interval_max: timedelta_field = timedelta(minutes=1)
    http_client_backoff: float = 1.1

    # Datastore options
    datastore_host: str = 'history'
    datastore_port: int = 5000
    datastore_path: str = '/history/datastore'

    datastore_fetch_timeout: timedelta_field = timedelta(minutes=5)
    datastore_flush_delay: timedelta_field = timedelta(seconds=5)
    datastore_shutdown_timeout: timedelta_field = timedelta(seconds=2)

    # Device options
    device_id: str | None = None
    discovery: DiscoveryType_field = DiscoveryType.all

    device_host: str | None = None
    device_port: int = 8332

    usb_proxy_host: str = 'usb-proxy'
    usb_proxy_port: int = 5000

    mock: bool = False

    simulation: bool = False
    simulation_port: int = 0  # any free port
    simulation_display_port: int = 0  # any free port
    simulation_workdir: Path = Path('./simulator')

    # Connection options
    connect_interval: timedelta_field = timedelta(seconds=2)
    connect_interval_max: timedelta_field = timedelta(seconds=30)
    connect_backoff: float = 1.5

    discovery_interval: timedelta_field = timedelta(seconds=5)
    discovery_timeout: timedelta_field = timedelta(minutes=2)
    discovery_timeout_mqtt: timedelta_field = timedelta(seconds=3)
    discovery_timeout_mdns: timedelta_field = timedelta(seconds=20)

    subprocess_connect_interval: timedelta_field = timedelta(milliseconds=200)
    subprocess_connect_timeout: timedelta_field = timedelta(seconds=10)

    handshake_timeout: timedelta_field = timedelta(minutes=2)
    handshake_ping_interval: timedelta_field = timedelta(seconds=2)

    # Command options
    command_timeout: timedelta_field = timedelta(seconds=20)

    # Broadcast options
    broadcast_interval: timedelta_field = timedelta(seconds=5)

    # Firmware options
    skip_version_check: bool = False

    # Backup options
    backup_interval: timedelta_field = timedelta(hours=1)
    backup_retry_interval: timedelta_field = timedelta(minutes=5)
    backup_root_dir: Path = Path('./backup')

    # Time sync options
    time_sync_interval: timedelta_field = timedelta(minutes=15)
    time_sync_retry_interval: timedelta_field = timedelta(seconds=10)

    # Firmware flash options
    flash_ymodem_timeout: timedelta_field = timedelta(seconds=30)
    flash_disconnect_timeout: timedelta_field = timedelta(seconds=20)

    @computed_field
    @property
    def datastore_url(self) -> str:
        return f'http://{self.datastore_host}:{self.datastore_port}{self.datastore_path}'


class FirmwareConfig(BaseModel):
    firmware_version: str
    firmware_date: str
    firmware_sha: str
    proto_version: str
    proto_date: str
    proto_sha: str
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
    id: str | None = None
    nid: int
    type: str | None = None
    data: dict[str, Any] | None = None


class FirmwareBlock(BaseModel):
    id: str | None = None
    nid: int
    type: str
    data: dict[str, Any]


class TwinKeyEntry(BaseModel):
    keys: tuple[str, int]
    data: dict


class BlockNameChange(BaseModel):
    existing: str
    desired: str


class MaskField(BaseModel):
    address: list[int]


class BasePayload(BaseModel):
    blockId: int
    maskMode: MaskMode_field = MaskMode.NO_MASK
    maskFields: list[MaskField] = Field(default_factory=list)


class EncodedPayload(BasePayload):
    blockType: int | str | None = None
    name: str | None = None
    content: str = ''


class DecodedPayload(BasePayload):
    blockType: str | None = None
    name: str | None = None
    content: dict | None = None


class BaseRequest(BaseModel):
    msgId: int
    opcode: Opcode_field
    mode: ReadMode_field = ReadMode.DEFAULT
    payload: BasePayload | None = None


class IntermediateRequest(BaseRequest):
    payload: EncodedPayload | None = None


class DecodedRequest(BaseRequest):
    payload: DecodedPayload | None = None


class BaseResponse(BaseModel):
    msgId: int
    error: ErrorCode_field
    mode: ReadMode_field = ReadMode.DEFAULT
    payload: list[BasePayload]


class IntermediateResponse(BaseResponse):
    payload: list[EncodedPayload]


class DecodedResponse(BaseResponse):
    payload: list[DecodedPayload]


class EncodedMessage(BaseModel):
    message: str


class HandshakeMessage(BaseModel):
    name: str
    firmware_version: str
    proto_version: str
    firmware_date: str
    proto_date: str
    system_version: str
    platform: str
    reset_reason_hex: str
    reset_data_hex: str
    device_id: str
    reset_reason: str = str(ResetReason.NONE)
    reset_data: str = str(ResetData.NOT_SPECIFIED)

    @model_validator(mode='after')
    def parse_reset_enums(self) -> Self:
        self.reset_reason = str(ResetReason(self.reset_reason_hex.upper()))
        try:
            self.reset_data = str(ResetData(self.reset_data_hex.upper()))
        except Exception:
            self.reset_data = str(ResetData.NOT_SPECIFIED)
        return self


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


DiscoveryKind_ = Literal[
    'SIM',
    'ADDRESS',
    'USB',
    'MDNS',
    'MQTT',
    'ALL',
]

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


class StatusDescription(BaseModel):
    enabled: bool
    service: ServiceDescription
    controller: ControllerDescription | None = None
    address: str | None = None

    discovery_kind: DiscoveryKind_
    connection_kind: ConnectionKind_ | None = None
    connection_status: ConnectionStatus_
    firmware_error: FirmwareError_ | None = None
    identity_error: IdentityError_ | None = None


class BlockRelation(BaseModel):
    source: str
    target: str
    claimed: bool = False
    relation: list[str]


class BlockClaim(BaseModel):
    source: str
    target: str
    intermediate: list[str]


class BackupIdentity(BaseModel):
    name: str


class Backup(BaseModel):
    # Older backups won't have these fields
    # They will not be used when loading backups
    name: str | None = None
    timestamp: str | None = None
    firmware: FirmwareDescription | None = None
    device: DeviceDescription | None = None

    # Deprecated fields
    store: list | None = None

    blocks: list[Block]


class BackupApplyResult(BaseModel):
    messages: list[str]


class AutoconnectSettings(BaseModel):
    enabled: bool


class ErrorResponse(BaseModel):
    error: str
    validation: list | None = None
    traceback: list[str] | None = None


class FirmwareFlashResponse(BaseModel):
    address: str
    version: str


class PingResponse(BaseModel):
    ping: Literal['pong'] = 'pong'


class UsbProxyResponse(BaseModel):
    enabled: bool
    devices: list[str]


class DatastoreSingleQuery(BaseModel):
    namespace: str
    id: str


class DatastoreMultiQuery(BaseModel):
    namespace: str
    ids: list[str] | None = None
    filter: str | None = None


class DatastoreValue(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )

    namespace: str
    id: str


class DatastoreSingleValueBox(BaseModel):
    value: DatastoreValue | None


class DatastoreMultiValueBox(BaseModel):
    values: list[DatastoreValue]


class TwinKeyEntriesValue(DatastoreValue):
    namespace: str = const.SERVICE_NAMESPACE

    data: list[TwinKeyEntry]


class StoredServiceSettingsValue(DatastoreValue):
    namespace: str = const.SERVICE_NAMESPACE

    enabled: bool = True


class StoredUnitSettingsValue(DatastoreValue):
    namespace: str = const.GLOBAL_NAMESPACE
    id: str = const.GLOBAL_UNITS_ID

    temperature: Literal['degC', 'degF'] = 'degC'


class StoredTimezoneSettingsValue(DatastoreValue):
    namespace: str = const.GLOBAL_NAMESPACE
    id: str = const.GLOBAL_TIME_ZONE_ID

    name: str = 'Etc/UTC'
    posixValue: str = 'UTC0'


class TwinKeyEntriesBox(DatastoreSingleValueBox):
    value: TwinKeyEntriesValue | None


class StoredServiceSettingsBox(DatastoreSingleValueBox):
    value: StoredServiceSettingsValue | None


class StoredUnitSettingsBox(DatastoreSingleValueBox):
    value: StoredUnitSettingsValue | None


class StoredTimezoneSettingsBox(DatastoreSingleValueBox):
    value: StoredTimezoneSettingsValue | None


class DatastoreEvent(BaseModel):
    changed: list[DatastoreValue] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class HistoryEvent(BaseModel):
    key: str
    data: dict


class ServiceStateEventData(BaseModel):
    status: StatusDescription
    blocks: list[Block]
    relations: list[BlockRelation]
    claims: list[BlockClaim]


class ServiceStateEvent(BaseModel):
    key: str
    type: Literal['Spark.state'] = 'Spark.state'
    data: ServiceStateEventData


class ServicePatchEventData(BaseModel):
    changed: list[Block] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class ServicePatchEvent(BaseModel):
    key: str
    type: Literal['Spark.patch'] = 'Spark.patch'
    data: ServicePatchEventData


class ServiceUpdateEventData(BaseModel):
    log: list[str]


class ServiceUpdateEvent(BaseModel):
    key: str
    type: Literal['Spark.update'] = 'Spark.update'
    data: ServiceUpdateEventData
