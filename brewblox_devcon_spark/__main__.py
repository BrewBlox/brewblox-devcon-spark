"""
Example of how to import and use the brewblox service
"""

from brewblox_service import brewblox_logger, events, scheduler, service

from brewblox_devcon_spark import (broadcaster, commander, commander_sim,
                                   communication, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.api import (alias_api, codec_api, debug_api,
                                       error_response, object_api, remote_api,
                                       system_api)
from brewblox_devcon_spark.codec import codec

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='spark'):
    parser = service.create_parser(default_name=default_name)

    # Local config
    group = parser.add_argument_group('Local configuration')
    group.add_argument('--database',
                       help='Backing file for the object database. [%(default)s]',
                       default='brewblox_db.json')
    group.add_argument('--config',
                       help='Backing file for service configuration. [%(default)s]',
                       default='brewblox_cfg.json')
    group.add_argument('--seed-objects',
                       help='A file of objects that should be created on connection. [%(default)s]')
    group.add_argument('--seed-profiles',
                       nargs='+',
                       type=int,
                       help='Profiles that should be made active on connection. [%(default)s]')

    # Device options
    group = parser.add_argument_group('Device communication')
    group.add_argument('--simulation',
                       help='Start in simulation mode. Will not connect to a physical device. [%(default)s]',
                       action='store_true')
    group.add_argument('--device-host',
                       help='Spark device URL host. Takes precedence over serial connections. [%(default)s]')
    group.add_argument('--device-port',
                       help='Spark device URL port when accessing a device over WiFi. [%(default)s]',
                       type=int,
                       default=8332)
    group.add_argument('--device-serial',
                       help='Spark device serial port. Automatically determined if not set. [%(default)s]')
    group.add_argument('--device-id',
                       help='Spark serial number. Any spark is valid if not set. '
                       'This will be ignored if --device-port is specified. [%(default)s]')
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

    return parser


def main():
    app = service.create_app(parser=create_parser())
    config = app['config']

    if config['list_devices']:
        LOGGER.info('Listing connected devices: ')
        for dev in [[v for v in p] for p in communication.all_ports()]:
            LOGGER.info(f'>> {" | ".join(dev)}')
        # Exit application
        return

    status.setup(app)

    if config['simulation']:
        commander_sim.setup(app)
    else:
        communication.setup(app)
        commander.setup(app)

    scheduler.setup(app)
    events.setup(app)

    codec.setup(app)
    datastore.setup(app)
    device.setup(app)
    broadcaster.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    system_api.setup(app)
    remote_api.setup(app)
    codec_api.setup(app)

    seeder.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
