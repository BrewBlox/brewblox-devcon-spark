"""
MQTT endpoints for Spark blocks
"""

import logging

from .. import mqtt, spark_api, utils
from ..models import Block, BlockIdentity

LOGGER = logging.getLogger(__name__)


def setup():
    config = utils.get_config()
    mqtt_client = mqtt.CV.get()
    api = spark_api.CV.get()

    @mqtt_client.subscribe(config.blocks_topic + '/create')
    async def on_create(client, topic, payload, qos, properties):
        block = Block.model_validate_json(payload)
        if block.serviceId == config.name:
            await api.create_block(block)

    @mqtt_client.subscribe(config.blocks_topic + '/write')
    async def on_write(client, topic, payload, qos, properties):
        block = Block.model_validate_json(payload)
        if block.serviceId == config.name:
            await api.write_block(block)

    @mqtt_client.subscribe(config.blocks_topic + '/patch')
    async def on_patch(client, topic, payload, qos, properties):
        block = Block.model_validate_json(payload)
        if block.serviceId == config.name:
            await api.patch_block(block)

    @mqtt_client.subscribe(config.blocks_topic + '/delete')
    async def on_delete(client, topic, payload, qos, properties):
        ident = BlockIdentity.model_validate_json(payload)
        if ident.serviceId == config.name:
            await api.delete_block(ident)
