"""
Example of how to import and use the brewblox service
"""

import logging
from configparser import ConfigParser
from os import getenv

from brewblox_service import brewblox_logger, http, mqtt, scheduler, service

from brewblox_devcon_spark import (backup_storage, block_store, broadcaster,
                                   codec, commander, connection, controller,
                                   global_store, service_status, service_store,
                                   synchronization, time_sync)
from brewblox_devcon_spark.api import (backup_api, blocks_api, debug_api,
                                       error_response, mqtt_api, settings_api,
                                       sim_api, system_api)
from brewblox_devcon_spark.models import ServiceConfig, ServiceFirmwareIni

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='spark'):
    parser = service.create_parser(default_name=default_name)

    # Device options
    group = parser.add_argument_group('Device communication')
    group.add_argument('--simulation',
                       help='Start in simulation mode. Will not connect to a physical device. '
                       'This option takes precedence over other connection options except --mock. '
                       'The simulator is assigned the --device-id value if set or 123456789012345678901234. '
                       'If you are using multiple simulators or mocks, you need to assign them unique device IDs. '
                       '[%(default)s]',
                       action='store_true')
    group.add_argument('--mock',
                       help='Start in mocked mode. Will not connect to a controller or simulation process. '
                       'This option takes precedence over other connection options and --simulation. '
                       'The mock is assigned the --device-id value if set or 123456789012345678901234. '
                       'If you are using multiple simulators or mocks, you need to assign them unique device IDs. '
                       '[%(default)s]',
                       action='store_true')
    group.add_argument('--device-host',
                       help='Spark device URL host. '
                       'Will only connect if device ID matches advertised ID, or is not set. [%(default)s]')
    group.add_argument('--device-port',
                       help='Spark device URL port when accessing a device over WiFi. [%(default)s]',
                       type=int,
                       default=8332)
    group.add_argument('--device-serial',
                       help='Spark device serial port. Takes precedence over URL connections. '
                       'Will only connect if device ID matches advertised ID, or is not set. [%(default)s]')
    group.add_argument('--device-id',
                       help='Spark serial number. Any spark is valid if not set. [%(default)s]')
    group.add_argument('--discovery',
                       help='Enabled types of device discovery. '
                       '--device-serial and --device-host disable discovery. '
                       '--device-id specifies which discovered device is valid. ',
                       choices=['all', 'usb', 'wifi', 'lan', 'mqtt'],
                       default='all')

    # Service network options
    group = parser.add_argument_group('Service communication')
    group.add_argument('--command-timeout',
                       help='Timeout period (in seconds) for controller commands. [$(default)s]',
                       type=float,
                       default=20)
    group.add_argument('--broadcast-interval',
                       help='Interval (in seconds) between broadcasts of controller state. '
                       'Set to a value <= 0 to disable broadcasting. [%(default)s]',
                       type=float,
                       default=5)
    group.add_argument('--isolated',
                       action='store_true',
                       help='Disable all outgoing network calls. [%(default)s]')
    group.add_argument('--datastore-topic',
                       help='Synchronization topic for datastore updates',
                       default='brewcast/datastore')

    # Updater options
    group = parser.add_argument_group('Firmware')
    group.add_argument('--skip-version-check',
                       help='Skip firmware version check: will not raise error on mismatch',
                       action='store_true')

    # Backup options
    group = parser.add_argument_group('Backup')
    group.add_argument('--backup-interval',
                       help='Interval (in seconds) between backups of controller state. '
                       'Set to a value <= 0 to disable. [%(default)s]',
                       type=float,
                       default=3600)
    group.add_argument('--backup-retry-interval',
                       help='Interval (in seconds) between backups of controller state '
                       'after startup, or after a failed backup. '
                       'Set to a value <= 0 to always use the value of --backup-interval. [%(default)s]',
                       type=float,
                       default=300)

    # Time sync options
    group = parser.add_argument_group('Time Sync')
    group.add_argument('--time-sync-interval',
                       help='Interval (in seconds) between sending UTC time to the controller. '
                       'Set to a value <= 0 to disable. [%(default)s]',
                       type=float,
                       default=900)

    return parser


def parse_ini(app) -> ServiceFirmwareIni:  # pragma: no cover
    parser = ConfigParser()
    parser.read('firmware/firmware.ini')
    config = dict(parser['FIRMWARE'].items())
    LOGGER.info(f'firmware.ini: {config}')
    return config


def main():
    app = service.create_app(parser=create_parser())
    logging.captureWarnings(True)
    config: ServiceConfig = app['config']
    app['ini'] = parse_ini(app)

    if getenv('ENABLE_DEBUGGER', False):  # pragma: no cover
        import debugpy
        debugpy.listen(('0.0.0.0', 5678))
        LOGGER.info('Debugger is enabled and listening on 5678')

    if config['simulation'] or config['mock']:
        config['device_id'] = config['device_id'] or '123456789012345678901234'

    scheduler.setup(app)
    mqtt.setup(app)
    http.setup(app)

    global_store.setup(app)
    service_store.setup(app)
    block_store.setup(app)

    service_status.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    synchronization.setup(app)
    controller.setup(app)

    backup_storage.setup(app)
    broadcaster.setup(app)
    time_sync.setup(app)

    error_response.setup(app)
    blocks_api.setup(app)
    system_api.setup(app)
    settings_api.setup(app)
    mqtt_api.setup(app)
    sim_api.setup(app)
    backup_api.setup(app)
    debug_api.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
