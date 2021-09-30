"""
Defines formal schemas for various API objects.
This improves error messages when handling JSON blobs as input data.
"""


SID_KEY = 'id'
NID_KEY = 'nid'
INTERFACE_KEY = 'interface'
TYPE_KEY = 'type'
GROUPS_KEY = 'groups'
DATA_KEY = 'data'
OBJECT_LIST_KEY = 'objects'
ID_LIST_KEY = 'object_ids'

SYSTEM_GROUP = 7
USER_NID_START = 100
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'
GENERATED_ID_PREFIX = 'New|'

WELCOME_PREFIX = 'BREWBLOX'
UPDATER_PREFIX = 'FIRMWARE_UPDATER'
CBOX_ERR_PREFIX = 'CBOXERROR'
SETUP_MODE_PREFIX = 'SETUP_MODE'

SPARK_NAMESPACE = 'spark-service'
GLOBAL_NAMESPACE = 'brewblox-global'
GLOBAL_UNITS_ID = 'units'
GLOBAL_TIME_ZONE_ID = 'timeZone'

GROUPS_NID = 1
SYSINFO_NID = 2
SYSTIME_NID = 3
ONEWIREBUS_NID = 4
WIFI_SETTINGS_NID = 5
TOUCH_SETTINGS_NID = 6
DISPLAY_SETTINGS_NID = 7
SPARK_PINS_NID = 19

SYS_OBJECT_KEYS: list[tuple[str, int]] = [
    ['ActiveGroups', GROUPS_NID],
    ['SystemInfo', SYSINFO_NID],
    ['SystemTime', SYSTIME_NID],
    ['OneWireBus', ONEWIREBUS_NID],
    ['WiFiSettings', WIFI_SETTINGS_NID],
    ['TouchSettings', TOUCH_SETTINGS_NID],
    ['DisplaySettings', DISPLAY_SETTINGS_NID],
    ['SparkPins', SPARK_PINS_NID],
]
