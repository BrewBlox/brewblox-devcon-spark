"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from . import const, controller, mqtt, state_machine, utils
from .block_analysis import calculate_claims, calculate_relations

LOGGER = logging.getLogger(__name__)


class Broadcaster:

    def __init__(self):
        self.config = utils.get_config()
        self.controller = controller.CV.get()

        self.state_topic = f'{self.config.state_topic}/{self.config.name}'
        self.history_topic = f'{self.config.history_topic}/{self.config.name}'

    async def run(self):
        mqtt_client = mqtt.CV.get()
        state = state_machine.CV.get()
        blocks = []

        try:
            if state.is_synchronized():
                blocks, logged_blocks = await self.controller.read_all_broadcast_blocks()

                # Convert list to key/value format suitable for history
                history_data = {
                    block.id: block.data
                    for block in logged_blocks
                    if not block.id.startswith(const.GENERATED_ID_PREFIX)
                }

                mqtt_client.publish(self.history_topic,
                                    {
                                        'key': self.config.name,
                                        'data': history_data,
                                    })

        finally:
            # State event is always published
            mqtt_client.publish(self.state_topic,
                                {
                                    'key': self.config.name,
                                    'type': 'Spark.state',
                                    'data': {
                                        'status': state.desc().model_dump(mode='json'),
                                        'blocks': [v.model_dump(mode='json') for v in blocks],
                                        'relations': calculate_relations(blocks),
                                        'claims': calculate_claims(blocks),
                                    },
                                },
                                retain=True)

    async def repeat(self):
        if self.config.broadcast_interval <= timedelta():
            LOGGER.warning(f'Cancelling broadcaster (interval={self.config.broadcast_interval})')
            return

        while True:
            await asyncio.sleep(self.config.broadcast_interval.total_seconds())
            try:
                await self.run()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)


@asynccontextmanager
async def lifespan():
    bc = Broadcaster()
    async with utils.task_context(bc.repeat()):
        yield
