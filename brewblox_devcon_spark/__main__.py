"""
Example of how to import and use the brewblox service
"""

from brewblox_service import brewblox_logger, events, scheduler, service

from brewblox_codec_spark import codec
from brewblox_devcon_spark import (broadcaster, commander, commander_sim,
                                   communication, device, twinkeydict)
from brewblox_devcon_spark.api import (alias_api, debug_api, error_response,
                                       object_api, profile_api, remote_api,
                                       system_api)

LOGGER = brewblox_logger(__name__)


def create_parser(default_name='spark'):
    parser = service.create_parser(default_name=default_name)
    parser.add_argument('--database',
                        help='Backing file for the object database. [%(default)s]',
                        default='brewblox_db.json')
    parser.add_argument('--system-database',
                        help='Backing file for the system object database. [%(default)s]',
                        default='config/brewblox_sys_db.json')
    parser.add_argument('--device-port',
                        help='Spark device port. Automatically determined if not set. [%(default)s]')
    parser.add_argument('--device-url-port',
                        help='Spark port when accessing a device over WiFi. [%(default)s]',
                        type=int,
                        default=8332)
    parser.add_argument('--device-url',
                        help='Spark device URL. Takes precedence over serial connections. [%(default)s]')
    parser.add_argument('--device-id',
                        help='Spark serial number. Any spark is valid if not set. '
                        'This will be ignored if --device-port is specified. [%(default)s]')
    parser.add_argument('--simulation',
                        help='Start in simulator mode. Will not connect to a physical device. [%(default)s]',
                        action='store_true')
    parser.add_argument('--broadcast-interval',
                        help='Interval (in seconds) between broadcasts of controller state.'
                        'Set to a value <= 0 to disable broadcasting. [%(default)s]',
                        type=float,
                        default=5)
    parser.add_argument('--broadcast-exchange',
                        help='Eventbus exchange to which controller state should be broadcasted. [%(default)s]',
                        default='brewcast')
    parser.add_argument('--sync-exchange',
                        help='Eventbus exchange used to synchronize remote blocks. [%(default)s]',
                        default='syncast')
    parser.add_argument('--unit-system-file',
                        help='User configuration for units [%(default)s]')
    parser.add_argument('--list-devices',
                        action='store_true',
                        help='List connected devices and exit. [%(default)s]')
    return parser


def main():
    app = service.create_app(parser=create_parser())

    if app['config']['list_devices']:
        LOGGER.info('Listing connected devices: ')
        for dev in [[v for v in p] for p in communication.all_ports()]:
            LOGGER.info(f'>> {" | ".join(dev)}')
        # Exit application
        return

    if app['config']['simulation']:
        commander_sim.setup(app)
    else:
        communication.setup(app)
        commander.setup(app)

    scheduler.setup(app)
    events.setup(app)

    codec.setup(app)
    twinkeydict.setup(app)
    device.setup(app)
    broadcaster.setup(app)

    error_response.setup(app)
    debug_api.setup(app)
    alias_api.setup(app)
    object_api.setup(app)
    profile_api.setup(app)
    system_api.setup(app)
    remote_api.setup(app)

    service.furnish(app)
    service.run(app)


if __name__ == '__main__':
    main()
