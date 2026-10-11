"""
System-wide constant values
"""

BREWBLOX_DNS_TYPE = '_brewblox._tcp.local.'

USER_NID_START = 100
OBJECT_LINK_POSTFIX_START = '<'
OBJECT_LINK_POSTFIX_END = '>'

# The longest request the controller takes: its base64 line, without the newline.
# The firmware's cbox::MAX_REQUEST_SIZE, the same on every link.
# A longer request closes the TCP connection, or is dropped on USB, serial and MQTT.
MAX_REQUEST_SIZE = 8192

SERVICE_NAMESPACE = 'spark-service'
GLOBAL_NAMESPACE = 'brewblox-global'
GLOBAL_UNITS_ID = 'units'
GLOBAL_TIME_ZONE_ID = 'timeZone'

# Relevant block types
SEQUENCE_BLOCK_TYPE = 'Sequence'
SYSINFO_BLOCK_TYPE = 'SysInfo'

# IDs and names of system blocks for all platforms.
# This includes deprecated system blocks,
# to ensure backwards compatibility when loading backups.
SYS_BLOCK_IDS = {
    'SysInfo': 2,
    'OneWireBus': 4,  # Deprecated
    'WiFiSettings': 5,  # Spark 2 and 3 only
    'DisplaySettings': 7,
    'SparkPins': 19,  # Spark 2 and 3 only
}
