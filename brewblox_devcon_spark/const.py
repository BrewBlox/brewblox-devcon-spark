"""
System-wide constant values
"""

USER_NID_START = 100
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'
GENERATED_ID_PREFIX = 'New|'

SPARK_NAMESPACE = 'spark-service'
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
]

# Relevant block types
SEQUENCE_BLOCK_TYPE = 'Sequence'
