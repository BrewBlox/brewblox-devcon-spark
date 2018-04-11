"""
Example of how to import and use the brewblox service
"""

from brewblox_devcon_spark import api, brewblox_logger, device, datastore
from brewblox_service import service

LOGGER = brewblox_logger(__name__)


def main():
    parser = service.create_parser(default_name='spark')
    parser.add_argument('--database',
                        help='Backing file for the object database. [%(default)s]',
                        default='brewblox_db.json')

    app = service.create_app(parser=parser)

    datastore.setup(app)
    device.setup(app)
    api.setup(app)

    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
