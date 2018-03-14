"""
Example of how to import and use the brewblox service
"""

import logging

from brewblox_service import service

LOGGER = logging.getLogger(__name__)


def main():
    app = service.create_app(default_name='spark')

    service.furnish(app)

    # service.run() will start serving clients async
    service.run(app)


if __name__ == '__main__':
    main()
