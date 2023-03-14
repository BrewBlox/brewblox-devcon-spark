from aiohttp import web
from brewblox_service import brewblox_logger, features, repeater

from brewblox_devcon_spark.models import ServiceConfig

from .base import ConnectionBase


async def connect(app: web.Application) -> ConnectionBase:
    config: ServiceConfig = app['config']

    simulation = config['simulation']
    device_serial = config['device_serial']
    device_host = config['device_host']
    device_port = config['device_port']

    # if simulation:
    #     return await connect_simulation(app)
    # if device_serial:
    #     return await connect_serial(device_serial)
    # elif device_host:
    #     return await connect_tcp(device_host, device_port)
    # else:
    #     return await connect_discovered(app)
