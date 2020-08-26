"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio
from time import monotonic

from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt, repeater, strex

from brewblox_devcon_spark import const, exceptions, service_status
from brewblox_devcon_spark.api.blocks_api import BlocksApi

LOGGER = brewblox_logger(__name__)


class Broadcaster(repeater.RepeaterFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        config = app['config']
        self.name = config['name']
        self.interval = config['broadcast_interval']
        self.volatile = self.interval <= 0 or config['volatile']
        self.timeout = config['broadcast_timeout']
        self.validity = str(config['broadcast_valid']) + 's'
        self.state_topic = config['state_topic'] + f'/{self.name}'
        self.history_topic = config['history_topic'] + f'/{self.name}'
        self.blocks_topic = f'{self.state_topic}/blocks'

        self._synched = False
        self._last_ok = monotonic()

        self._will_message = {
            'key': self.name,
            'type': 'Spark.state',
            'ttl': '7d',
            'data': {
                'status': None,
                'blocks': [],
            },
        }

        # A will is published if the client connection is broken
        mqtt.set_client_will(app,
                             self.state_topic,
                             self._will_message)

    async def prepare(self):
        if self.volatile:
            raise repeater.RepeaterCancelled()

    async def before_shutdown(self, app: web.Application):
        await self.end()
        # This is an orderly shutdown - MQTT will won't be published
        await mqtt.publish(self.app,
                           self.state_topic,
                           err=False,
                           retain=True,
                           message=self._will_message)

    async def run(self):
        try:
            await asyncio.sleep(self.interval)
            self._synched = await service_status.wait_synchronized(self.app, wait=False)

            status_data = service_status.desc_dict(self.app)
            blocks_data = []
            history_data = {}

            try:
                if self._synched:
                    api = BlocksApi(self.app)
                    blocks_data = await api.read_all()
                    history_data = {
                        block['id']: block['data']
                        for block in await api.read_all_logged()
                        if not block['id'].startswith(const.GENERATED_ID_PREFIX)
                    }
                self._last_ok = monotonic()

            finally:
                # State event
                await mqtt.publish(self.app,
                                   self.state_topic,
                                   err=False,
                                   retain=True,
                                   message={
                                       'key': self.name,
                                       'type': 'Spark.state',
                                       'ttl': self.validity,
                                       'data': {
                                           'status': status_data,
                                           'blocks': blocks_data,
                                       },
                                   })

                # History event
                await mqtt.publish(self.app,
                                   self.history_topic,
                                   err=False,
                                   message={
                                       'key': self.name,
                                       'data': history_data,
                                   })

                # backwards compatibility mode for external subscribers
                await mqtt.publish(self.app,
                                   self.blocks_topic,
                                   err=False,
                                   retain=True,
                                   message={
                                       'key': self.name,
                                       'type': 'Spark.blocks',
                                       'ttl': self.validity,
                                       'data': blocks_data,
                                   })

        except exceptions.ConnectionPaused:
            LOGGER.debug(f'{self} interrupted: connection paused')

        except Exception as ex:
            LOGGER.debug(f'{self} exception: {strex(ex)}')
            if self._synched \
                    and self.timeout > 0 \
                    and self._last_ok + self.timeout < monotonic():  # pragma: no cover
                LOGGER.error('Broadcast retry attemps exhaused. Exiting now.')
                raise web.GracefulExit()
            raise


def setup(app: web.Application):
    features.add(app, Broadcaster(app))


def get_broadcaster(app: web.Application) -> Broadcaster:
    return features.get(app, Broadcaster)
