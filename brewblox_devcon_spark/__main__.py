"""
Example of how to import and use the brewblox service
"""


from brewblox_devcon_spark import api, brewblox_logger, device
from brewblox_service import service

LOGGER = brewblox_logger(__name__)


def main():
    app = service.create_app(default_name='spark')

    device.setup(app)
    api.setup(app)

    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
