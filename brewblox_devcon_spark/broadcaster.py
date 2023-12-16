"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from . import const, controller, mqtt, service_status, utils
from .block_analysis import calculate_claims, calculate_relations

LOGGER = logging.getLogger(__name__)


class Broadcaster:

    def __init__(self):
        config = utils.get_config()
        self.name = config.name
        self.interval = config.broadcast_interval
        self.isolated = self.interval.total_seconds() <= 0
        self.state_topic = f'{config.state_topic}/{config.name}'
        self.history_topic = f'{config.history_topic}/{config.name}'

    async def run(self):
        mqtt_client = mqtt.CV.get()
        status = service_status.CV.get()
        blocks = []

        try:
            if status.is_synchronized():
                blocks, logged_blocks = await controller.CV.get().read_all_broadcast_blocks()

                # Convert list to key/value format suitable for history
                history_data = {
                    block.id: block.data
                    for block in logged_blocks
                    if not block.id.startswith(const.GENERATED_ID_PREFIX)
                }

                mqtt_client.publish(self.history_topic,
                                    {
                                        'key': self.name,
                                        'data': history_data,
                                    })

        finally:
            # State event is always published
            mqtt_client.publish(self.state_topic,
                                {
                                    'key': self.name,
                                    'type': 'Spark.state',
                                    'data': {
                                        'status': status.desc().model_dump(mode='json'),
                                        'blocks': [v.model_dump(mode='json') for v in blocks],
                                        'relations': calculate_relations(blocks),
                                        'claims': calculate_claims(blocks),
                                    },
                                },
                                retain=True)

    async def repeat(self):
        config = utils.get_config()
        while True:
            await asyncio.sleep(self.interval.total_seconds())
            try:
                await self.run()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=config.debug)


@asynccontextmanager
async def lifespan():
    bc = Broadcaster()
    task = asyncio.create_task(bc.repeat())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
