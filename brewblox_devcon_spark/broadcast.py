"""
Intermittently broadcasts status and blocks to the eventbus
"""


import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from . import const, mqtt, spark_api, state_machine, utils
from .block_analysis import calculate_claims, calculate_relations
from .models import HistoryEvent, ServiceStateEvent, ServiceStateEventData

LOGGER = logging.getLogger(__name__)


class Broadcaster:

    def __init__(self):
        self.config = utils.get_config()
        self.api = spark_api.CV.get()

        self.state_topic = f'{self.config.state_topic}/{self.config.name}'
        self.history_topic = f'{self.config.history_topic}/{self.config.name}'

    async def run(self):
        mqtt_client = mqtt.CV.get()
        state = state_machine.CV.get()
        blocks = []

        try:
            if state.is_synchronized():
                blocks = await self.api.read_all_blocks()
                logged_blocks = await self.api.read_all_logged_blocks()

                # Convert list to key/value format suitable for history
                history_data = {
                    block.id: block.data
                    for block in logged_blocks
                    if not block.id.startswith(const.GENERATED_ID_PREFIX)
                }

                mqtt_client.publish(self.history_topic,
                                    HistoryEvent(
                                        key=self.config.name,
                                        data=history_data,
                                    ).model_dump(mode='json'))

        finally:
            # State event is always published
            mqtt_client.publish(self.state_topic,
                                ServiceStateEvent(
                                    key=self.config.name,
                                    data=ServiceStateEventData(
                                        status=state.desc(),
                                        blocks=blocks,
                                        relations=calculate_relations(blocks),
                                        claims=calculate_claims(blocks)
                                    )
                                ).model_dump(mode='json'),
                                retain=True)

    async def repeat(self):
        interval = self.config.broadcast_interval

        if interval <= timedelta():
            LOGGER.warning(f'Cancelling broadcaster (interval={interval})')
            return

        while True:
            try:
                await asyncio.sleep(interval.total_seconds())
                await self.run()
            except Exception as ex:
                LOGGER.error(utils.strex(ex), exc_info=self.config.debug)


@asynccontextmanager
async def lifespan():
    bc = Broadcaster()
    async with utils.task_context(bc.repeat()):
        yield
