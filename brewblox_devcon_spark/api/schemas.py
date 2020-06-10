"""
Schemas used in API endpoints
"""

from marshmallow import Schema, fields


class AliasCreateSchema(Schema):
    sid = fields.String(required=True)
    nid = fields.Integer(required=True)


class StringIdSchema(Schema):
    id = fields.String(required=True)


class InterfaceIdSchema(Schema):
    interface = fields.String(required=True)


class ManualCommandSchema(Schema):
    command = fields.String(required=True)
    data = fields.Dict(required=True)


class BlockSchema(Schema):
    id = fields.String(required=True)
    nid = fields.Integer(required=False)
    groups = fields.List(fields.Integer(), required=True)
    type = fields.String(required=True)
    data = fields.Dict(required=True)


class BlockIdSchema(Schema):
    id = fields.String(required=False)
    nid = fields.Integer(required=False)


class BlockRenameSchema(Schema):
    existing = fields.String(required=True)
    desired = fields.String(required=True)


class BlockValidateSchema(Schema):
    type = fields.String(required=True)
    data = fields.Dict(required=True)


class GroupsSchema(Schema):
    groups = fields.List(fields.Integer(), required=True)


class StoreEntrySchema(Schema):
    keys = fields.Tuple((fields.String(), fields.Integer()), required=True)
    data = fields.Dict(required=True)


class SparkExportSchema(Schema):
    store = fields.Nested(StoreEntrySchema(many=True), required=True)
    blocks = fields.Nested(BlockSchema(many=True), required=True)


class SparkExportResultSchema(Schema):
    messages = fields.List(fields.String(), required=True)


class UserUnitsSchema(Schema):
    Temp = fields.String(required=True)


class AutoconnectingSchema(Schema):
    enabled = fields.Bool(required=True)


class FirmwareInfoSchema(Schema):
    firmware_version = fields.String(required=True)
    proto_version = fields.String(required=True)
    firmware_date = fields.String(required=True)
    proto_date = fields.String(required=True)
    device_id = fields.String(required=True)


class DeviceInfoSchema(FirmwareInfoSchema):
    system_version = fields.String(required=True)
    platform = fields.String(required=True)
    reset_reason = fields.String(required=True)


class StatusSchema(Schema):
    type = fields.String(required=True)
    address = fields.String(required=True)
    connection = fields.String(required=True)
    compatible = fields.Bool(required=True)
    latest = fields.Bool(required=True)
    valid = fields.Bool(required=True)
    service = fields.Nested(FirmwareInfoSchema(), required=False)
    device = fields.Nested(DeviceInfoSchema(), required=False)
    info = fields.String(many=True)

    autoconnecting = fields.Bool(required=True)
    connect = fields.Bool(required=True)
    handshake = fields.Bool(required=True)
    synchronize = fields.Bool(required=True)
