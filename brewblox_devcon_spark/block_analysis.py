"""
Calculate block metadata
"""

from typing import Any, Optional, TypedDict

from brewblox_devcon_spark.codec import bloxfield
from brewblox_devcon_spark.models import Block

# Relations to these blocks should be ignored,
# as they have no impact on control logic
IGNORED_RELATION_TYPES = [
    'DisplaySettings',
]

# Relations with this field name should be ignored
IGNORED_RELATION_FIELDS = [
    'claimedBy',  # Always mirror an existing target link
    'oneWireBusId',  # OneWireBus system blocks are not rendered
    'clients',  # Balancer clients are mirrored in client constraints
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
    claimed: Optional[bool]
    relation: list[str]


class BlockClaim(TypedDict):
    source: str
    target: str
    intermediate: list[str]


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
    if relation and relation[-1] in IGNORED_RELATION_FIELDS:
        return []

    elif bloxfield.is_defined_link(field):
        source, target = parent_id, field['id']
        if relation and relation[0] in INVERTED_RELATION_FIELDS:
            source, target = target, source

        return [
            BlockRelation(source=source,
                          target=target,
                          relation=relation)
        ]

    elif bloxfield.is_bloxfield(field):
        # Ignored:
        # - claim links
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


def calculate_relations(blocks: list[Block]) -> list[BlockRelation]:
    """
    Identifies all relation edges between blocks.
    One-sided relations (undefined links) are ignored.

    Args:
        blocks (list[Block]): Set of blocks that will be evaluated

    Returns:
        list[BlockRelation]: Valid relations between blocks in `blocks`.
    """
    relations = []
    for block in blocks:
        if block.type in IGNORED_RELATION_TYPES:
            continue
        relations += _find_nested_relations(block.id, [], block.data)

    for block in blocks:
        claim = block.data.get('claimedBy')
        if claim and claim['id']:
            target = block.id
            source = claim['id']
            for r in relations:  # pragma: no branch
                if r['target'] == target and r['source'] == source:
                    r['claimed'] = True
                    break

    return relations


def calculate_claims(blocks: list[Block]) -> list[BlockClaim]:
    claim_dict: dict[str, BlockClaim] = {}
    channel_claims: list[BlockClaim] = []

    for block in blocks:
        # Claims to the entire block
        link = block.data.get('claimedBy')
        if link and link['id']:
            claim_dict[block.id] = BlockClaim(source=link['id'],
                                              target=block.id,
                                              intermediate=[])

        # On IoArrays, individual channels are claimed
        channels = block.data.get('channels', [])
        for c in channels:
            link = c['claimedBy']
            if link and link['id']:
                channel_claims.append(BlockClaim(source=link['id'],
                                                 target=block.id,
                                                 intermediate=[]))

    def extended_claim(claim: BlockClaim) -> BlockClaim:
        source_claim = claim_dict.get(claim['source'])
        if not source_claim:
            return claim

        grand_source = source_claim['source']
        if grand_source in claim['intermediate']:
            return claim  # Circular claim

        # Shift claim, look further up the tree
        return extended_claim(
            BlockClaim(source=grand_source,
                       target=claim['target'],
                       intermediate=[*claim['intermediate'], claim['source']]))

    return [extended_claim(c)
            for c in [*claim_dict.values(), *channel_claims]]
