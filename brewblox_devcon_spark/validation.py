"""
Defines formal schemas for various API objects.
This improves error messages when handling JSON blobs as input data.
"""

from schema import And, Optional, Schema

API_SID_KEY = 'id'
API_NID_KEY = 'nid'
API_INTERFACE_KEY = 'interface'
API_TYPE_KEY = 'type'
API_DATA_KEY = 'data'
API_OBJECT_LIST_KEY = 'objects'
API_GROUP_LIST_KEY = 'groups'

OBJECT_SID_KEY = 'object_sid'
OBJECT_NID_KEY = 'object_nid'
OBJECT_INTERFACE_KEY = 'object_if'
OBJECT_TYPE_KEY = 'object_type'
OBJECT_DATA_KEY = 'object_data'
OBJECT_LIST_KEY = 'objects'
GROUP_LIST_KEY = 'groups'
OBJECT_ID_LIST_KEY = 'object_ids'

SYSTEM_GROUP = 7
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'
GENERATED_ID_PREFIX = 'New|'

_api_data = {
    API_TYPE_KEY: str,
    API_DATA_KEY: {Optional(str): object},
}

_api_keys = {
    Optional(API_SID_KEY): str,
    Optional(API_NID_KEY): int,
}

_command_data = {
    OBJECT_TYPE_KEY: str,
    OBJECT_DATA_KEY: {Optional(str): object}
}

APIDataObject: Schema = Schema(_api_data)

ApiObject: Schema = Schema({
    **_api_keys,
    API_GROUP_LIST_KEY: [And(int, lambda v: 0 <= v <= 7)],
    **_api_data,
})

StoreObject: Schema = Schema({
    'keys': [str, int],
    'data': dict,  # Always empty right now
})

ExportedObjects: Schema = Schema({
    'blocks': [ApiObject],
    'store': [StoreObject]
})
