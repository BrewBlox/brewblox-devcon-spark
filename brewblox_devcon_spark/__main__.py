"""
Example of how to import and use the brewblox service
"""

import logging
from configparser import ConfigParser

from brewblox_service import brewblox_logger, events, scheduler, service

from brewblox_devcon_spark import (broadcaster, commander, commander_sim,
                                   communication, couchdb_client, datastore,
                                   device, http_client, seeder, status)
from brewblox_devcon_spark.api import (alias_api, codec_api, debug_api,
                                       error_response, object_api, remote_api,
                                       sse_api, system_api)
from brewblox_devcon_spark.codec import codec

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='spark'):
    parser = service.create_parser(default_name=default_name)

    # Device options
    group = parser.add_argument_group('Device communication')
    group.add_argument('--simulation',
                       help='Start in simulation mode. Will not connect to a physical device. [%(default)s]',
                       action='store_true')
    group.add_argument('--device-host',
                       help='Spark device URL host. '
                       'Will connect to this URL regardless of advertised device ID. [%(default)s]')
    group.add_argument('--device-port',
                       help='Spark device URL port when accessing a device over WiFi. [%(default)s]',
                       type=int,
                       default=8332)
    group.add_argument('--device-serial',
                       help='Spark device serial port. Takes precedence over URL connections. '
                       'Will only connect if device ID matches advertised ID, or is not set. [%(default)s]')
    group.add_argument('--device-id',
                       help='Spark serial number. Any spark is valid if not set. '
                       'This will be ignored if --device-host is used. [%(default)s]')
    group.add_argument('--discovery',
                       help='Enabled types of device discovery. '
                       '--device-serial and --device-host disable discovery. '
                       '--device-id specifies which discovered device is valid. ',
                       choices=['all', 'usb', 'wifi'],
                       default='all')
    group.add_argument('--list-devices',
                       action='store_true',
                       help='List connected devices and exit. [%(default)s]')

    # Service network options
    group = parser.add_argument_group('Service communication')
    group.add_argument('--broadcast-exchange',
                       help='Eventbus exchange to which controller state should be broadcasted. [%(default)s]',
                       default='brewcast')
    group.add_argument('--broadcast-interval',
                       help='Interval (in seconds) between broadcasts of controller state.'
                       'Set to a value <= 0 to disable broadcasting. [%(default)s]',
                       type=float,
                       default=5)
    group.add_argument('--sync-exchange',
                       help='Eventbus exchange used to synchronize remote blocks. [%(default)s]',
                       default='syncast')
    group.add_argument('--mdns-host',
                       help='Address of the BrewBlox mdns discovery service. [%(default)s]',
                       default='172.17.0.1')
    group.add_argument('--mdns-port',
                       help='Port of the BrewBlox mdns discovery service. [%(default)s]',
                       type=int,
                       default=5000)
    group.add_argument('--volatile',
                       action='store_true',
                       help='Disable all outgoing network calls. [%(default)s]')

    # Updater options
    group = parser.add_argument_group('Firmware')
    group.add_argument('--skip-version-check',
                       help='Skip firmware version check: will not raise error on mismatch',
                       action='store_true')
    group.add_argument('--firmware-port',
                       help='Port used for firmware updates. [%(default)s]',
                       type=int,
                       default=8333)
    return parser


def parse_ini(app):  # pragma: no cover
    parser = ConfigParser()
    parser.read(['config/protobuf.ini', 'binaries/firmware.ini'])
    return {
        **dict(parser['PROTOBUF'].items()),
        **dict(parser['FIRMWARE'].items()),
    }


def main():
    app = service.create_app(parser=create_parser())
    logging.captureWarnings(True)
    config = app['config']
    app['ini'] = parse_ini(app)

    if config['list_devices']:
        LOGGER.info('Listing connected devices: ')
        for dev in [[v for v in p] for p in communication.all_ports()]:
            LOGGER.info(f'>> {" | ".join(dev)}')
        # Exit application
        return

    LOGGER.info('INI: ' + ', '.join([f"{k}='{v}'" for k, v in app['ini'].items()]))
    LOGGER.info('CONFIG: ' + ', '.join([f"{k}='{v}'" for k, v in app['config'].items()]))

    status.setup(app)
    http_client.setup(app)

    if config['simulation']:
        commander_sim.setup(app)
    else:
        communication.setup(app)
        commander.setup(app)

    scheduler.setup(app)
    events.setup(app)

    couchdb_client.setup(app)
    datastore.setup(app)
    codec.setup(app)
    device.setup(app)
    broadcaster.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)
    remote_api.setup(app)
    codec_api.setup(app)
    sse_api.setup(app)

    seeder.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
