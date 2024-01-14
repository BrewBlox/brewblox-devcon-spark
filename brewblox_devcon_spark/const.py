"""
System-wide constant values
"""

USER_NID_START = 100
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'
GENERATED_ID_PREFIX = 'New|'

SERVICE_NAMESPACE = 'spark-service'
GLOBAL_NAMESPACE = 'brewblox-global'
GLOBAL_UNITS_ID = 'units'
GLOBAL_TIME_ZONE_ID = 'timeZone'

# Numeric IDs of system objects
SYSINFO_NID = 2
ONEWIREBUS_NID = 4
WIFI_SETTINGS_NID = 5
TOUCH_SETTINGS_NID = 6
DISPLAY_SETTINGS_NID = 7
SPARK_PINS_NID = 19

# Default SID/NID for system objects
SYS_OBJECT_KEYS: list[tuple[str, int]] = [
    ['SystemInfo', SYSINFO_NID],
    ['OneWireBus', ONEWIREBUS_NID],
    ['WiFiSettings', WIFI_SETTINGS_NID],
    ['TouchSettings', TOUCH_SETTINGS_NID],
    ['DisplaySettings', DISPLAY_SETTINGS_NID],
    ['SparkPins', SPARK_PINS_NID],
    ['GPIO-1', 50], # kvdw blocks below
    ['GPIO-2', 51],
    ['ANALOG-1', 52],
    ['SENSOR-1', 53],
    ['SENSOR-2', 54],
    ['SENSOR-3', 55],
    ['SENSOR-4', 56],
    ['SENSOR-5', 57],
    ['SENSOR-6', 58],
    ['SENSOR-7', 59],
    ['SENSOR-8', 60],
]

# Relevant block types
SEQUENCE_BLOCK_TYPE = 'Sequence'
SYSINFO_BLOCK_TYPE = 'SysInfo'
