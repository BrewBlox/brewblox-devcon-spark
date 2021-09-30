"""
Calculate block metadata
"""

from itertools import chain
from typing import Any, Generator, TypedDict

from brewblox_devcon_spark.types import Block

# Relations to these blocks should be ignored,
# as they have no impact on control logic
IGNORED_RELATION_TYPES = [
    'DisplaySettings',
]

# Relations with this field name should be ignored
# This may be a duplicate driven field, or a meaningless link to a system object
IGNORED_RELATION_FIELDS = [
    'drivenOutputId',  # PID
    'drivenTargetId',  # Setpoint, Setpoint Driver, Logic Actuator
    'drivenActuatorId',  # PWM
    'oneWireBusId',  # OneWireTempSensor, DS2408, DS2413
]

# Relations with this field name should be inverted
# The block that owns the link is best graphed as being the target in the relation
INVERTED_RELATION_FIELDS = [
    'inputId',  # PID
    'referenceId',  # Setpoint Driver
    'sensorId',  # Setpoint
    'analog',  # Logic Actuator
    'digital',  # Logic Actuator
]


class BlockRelation(TypedDict):
    source: str
    target: str
    relation: list[str]


class BlockDriveChain(TypedDict):
    source: str
    target: str
    intermediate: list[str]


def is_blox_field(obj):
    return isinstance(obj, dict) and '__bloxtype' in obj


def is_link(obj):
    return isinstance(obj, dict) and obj.get('__bloxtype') == 'Link'


def is_defined_link(obj):
    return is_link(obj) \
        and obj.get('id') \
        and obj.get('type')


def _find_nested_relations(
    parent_id: str,
    relation: list[str],
    field: Any,
) -> list[BlockRelation]:
    """
    Recursively traverses `field` to find all valid and defined links.

    If the link is owned by the target block, the relation must be inverted.
    Fields where this happens are listed explicitly in INVERTED_RELATION_FIELDS.

    Args:
        parent_id (str): Owning block ID. Is relation source if not inverted
        relation (list[str]): Path to the link that defines the relation.
        field (Any): (sub-)field in evaluated block's data

    Returns:
        list[BlockRelation]: relations detected in `field` and its children.
    """
    if relation and relation[0] in IGNORED_RELATION_FIELDS:
        return []

    elif is_defined_link(field):
        source, target = parent_id, field['id']
        if relation and relation[0] in INVERTED_RELATION_FIELDS:
            source, target = target, source

        return [
            BlockRelation(source=source,
                          target=target,
                          relation=relation)
        ]

    elif is_blox_field(field):
        # Ignored:
        # - driven links
        # - unset links
        # - quantities
        return []

    elif isinstance(field, dict):
        # Increase recursion level for nested values
        # Flatten output at each level to discard empty results
        output = []
        for key, value in field.items():
            output += _find_nested_relations(parent_id, [*relation, key], value)
        return output

    elif isinstance(field, list):
        # Increase recursion level for list values
        # Flatten output at each level to discard empty results
        output = []
        for idx, value in enumerate(field):
            output += _find_nested_relations(parent_id, [*relation, str(idx)], value)
        return output

    else:
        return []


def calculate_relations(blocks: list[dict]) -> list[dict]:
    """
    Identifies all relation edges between blocks.
    One-sided relations (undefined links) are ignored.

    Args:
        blocks (list[dict]): Set of blocks that will be evaluated

    Returns:
        list[dict]: Valid relations between blocks in `blocks`.
    """
    output = []
    for block in blocks:
        if block['type'] in IGNORED_RELATION_TYPES:
            continue
        output += _find_nested_relations(block['id'], [], block['data'])

    return output


def _generate_chains(
    drivers: dict[str, list[str]],
    chain: list[str],
    block_id: str,
) -> Generator[list[str], None, None]:
    """
    Recursively constructs driver chains for all driven blocks
    The chain ends when `block_id` is not driven, or a circular reference is detected

    Args:
        drivers (dict[str, list[str]]): key: driven ID, value: driver IDs.
        chain (list[str]): [description] Drive chain leading to `block_id`.
        block_id (str): [description] Evaluated ID. Not necessarily driven.

    Yields:
        list[list[str]]: list of chains terminating at `block_id`.
            A chain is generated for every initial driver.
    """
    # check if driving block is itself driven
    super_drivers = drivers.get(block_id)

    if block_id in chain:
        # Circular relation detected
        # Add block ID to complete the circle, and then end recursion
        yield [*chain, block_id]
    elif super_drivers:
        # Increase recursion level until initial driver is found
        for driver_id in super_drivers:
            yield from _generate_chains(drivers, [*chain, block_id], driver_id)
    else:
        # We've reached the initial driver
        yield [*chain, block_id]


def calculate_drive_chains(blocks: list[Block]) -> list[BlockDriveChain]:
    """
    Finds driving links in `blocks`, and constructs end-to-end drive chains.

    All driven blocks get at least one chain.
    If any block in the chain is driven by multiple blocks,
    a chain is generated for every connected initial driver (a driving block that is not driven).

    Given a typical fermentation control scheme with these blocks...
        - Heat PID
        - Heat PWM
        - Heat Actuator
        - Cool PID
        - Cool PWM
        - Cool Actuator
        - Spark Pins

    ...the following drive chains will be generated
        - target=Spark Pins, source=Heat PID, intermediate=[Heat Actuator, Heat PWM]
        - target=Heat Actuator, source=Heat PID, intermediate=[Heat PWM]
        - target=Heat PWM, source=Heat PID, intermediate=[]
        - target=Spark Pins, source=Cool PID, intermediate=[Cool Actuator, Cool PWM]
        - target=Cool Actuator, source=Cool PID, intermediate=[Cool PWM]
        - target=Cool PWM, source=Cool PID, intermediate=[]

    Args:
        blocks (list[Block]): Input block array. Expected to be complete.

    Returns:
        list[BlockDriveChain]: All detected drive chains.
    """
    # First map all driven blocks to their drivers
    drivers: dict[str, list[str]] = {}  # key: driven, value: drivers
    for block in blocks:
        for field in block['data'].values():
            if is_defined_link(field) and field.get('driven') is True:
                # Link is driven, append block ID to drivers
                drivers.setdefault(field['id'], []).append(block['id'])

    # Generate and collect all drive chains
    output: list[BlockDriveChain] = []
    for drive_chain in chain.from_iterable(
        _generate_chains(drivers, [], driven_id)
        for driven_id in drivers.keys()
    ):
        output.append(BlockDriveChain(
            target=drive_chain[0],
            source=drive_chain[-1],
            intermediate=drive_chain[1:-1]
        ))
    return output
