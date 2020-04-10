"""
Example of how to import and use the brewblox service
"""

import logging
from configparser import ConfigParser

from brewblox_service import (brewblox_logger, couchdb, events, http,
                              scheduler, service)

from brewblox_devcon_spark import (broadcaster, commander, communication,
                                   datastore, device, seeder, simulator, state)
from brewblox_devcon_spark.api import (alias_api, codec_api, debug_api,
                                       error_response, object_api, system_api)
from brewblox_devcon_spark.codec import codec

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='spark'):
    parser = service.create_parser(default_name=default_name)

    # Device options
    group = parser.add_argument_group('Device communication')
    group.add_argument('--simulation',
                       help='Start in simulation mode. Will not connect to a physical device. '
                       'This option takes precedence over other connection options. '
                       'The simulator is assigned the --device-id value if set or 123456789012345678901234. '
                       'If you are using multiple simulators, you need to assign them unique device IDs. '
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
                       choices=['all', 'usb', 'wifi'],
                       default='all')

    # Service network options
    group = parser.add_argument_group('Service communication')
    group.add_argument('--history-exchange',
                       help='Eventbus exchange to which logged controller state should be broadcast. [%(default)s]',
                       default='brewcast.history')
    group.add_argument('--state-exchange',
                       help='Eventbus exchange to which volatile controller state should be broadcast. [%(default)s]',
                       default='brewcast.state')
    group.add_argument('--command-timeout',
                       help='Timeout period (in seconds) for controller commands. [$(default)s]',
                       type=float,
                       default=10)
    group.add_argument('--broadcast-interval',
                       help='Interval (in seconds) between broadcasts of controller state. '
                       'Set to a value <= 0 to disable broadcasting. [%(default)s]',
                       type=float,
                       default=5)
    group.add_argument('--broadcast-timeout',
                       help='Timeout period (in seconds) for the broadcaster. '
                       'This is measured from the last successful broadcast. '
                       'If the timeout triggers, the service restarts. '
                       'Set to a value <= 0 to prevent timeouts. [%(default)s]',
                       type=float,
                       default=60)
    group.add_argument('--broadcast-valid',
                       help='Period after which broadcast data should be discarded. '
                       'This does not apply to history data. [%(default)s]',
                       type=float,
                       default=60)
    group.add_argument('--read-timeout',
                       help='Timeout period (in seconds) for communication. '
                       'The timeout is triggered if no data is received for this duration'
                       'If the timeout triggers, the service attempts to reconnect. '
                       'Set to a value <= 0 to prevent timeouts. [%(default)s]',
                       type=float,
                       default=30)
    group.add_argument('--mdns-host',
                       help='Address of the Brewblox mdns discovery service. [%(default)s]',
                       default='172.17.0.1')
    group.add_argument('--mdns-port',
                       help='Port of the Brewblox mdns discovery service. [%(default)s]',
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

    return parser


def parse_ini(app):  # pragma: no cover
    parser = ConfigParser()
    parser.read('binaries/firmware.ini')
    return dict(parser['FIRMWARE'].items())


def main():
    app = service.create_app(parser=create_parser())
    logging.captureWarnings(True)
    config = app['config']
    app['ini'] = parse_ini(app)

    # Logs a debug message for every event
    logging.getLogger('aioamqp.channel').setLevel(logging.CRITICAL)
    # Logs stack traces when the connection is closed
    logging.getLogger('aioamqp.protocol').setLevel(logging.CRITICAL)

    LOGGER.info('INI: ' + ', '.join([f"{k}='{v}'" for k, v in app['ini'].items()]))
    LOGGER.info('CONFIG: ' + ', '.join([f"{k}='{v}'" for k, v in app['config'].items()]))

    if config['simulation']:
        config['device_id'] = config['device_id'] or '123456789012345678901234'
        config['device_host'] = 'localhost'
        config['device_port'] = 8332
        config['device_serial'] = None
        simulator.setup(app)

    state.setup(app)
    http.setup(app)

    communication.setup(app)
    commander.setup(app)

    scheduler.setup(app)
    events.setup(app)

    couchdb.setup(app)
    datastore.setup(app)
    codec.setup(app)
    device.setup(app)
    broadcaster.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)
    codec_api.setup(app)

    seeder.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
