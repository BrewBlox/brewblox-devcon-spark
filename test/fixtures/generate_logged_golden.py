"""
Generates logged_golden.json: the reference for Codec.logged_view().

This was run once, against the pre-change post_decode(mode=ReadMode.LOGGED) (proto 7af0c7e2),
before ReadMode.LOGGED was replaced by CHANGED. It can not be run again: the LOGGED decode
path no longer exists. It is kept to document how the fixture was made.
One edit since: proto 5bab8b2d dropped `logged` from Pid.integralReset, so it left the Pid
expectations, as the LOGGED filter would have dropped it.
The message builder is in messages.py, which the codec tests reuse.

For every block type in the codec lookup, it stores the payload of a fully populated message
(a non-zero value for every leaf, one element in each repeated field and map, the first member
of each oneof), an empty message, and zero variants where zero decodes differently
(GpioModule with an all-zero analogChannels[0], TempSensorExternal with lastUpdated 0).

Run from the repository root: `python -m test.fixtures.generate_logged_golden`
"""

import json
from base64 import b64encode
from pathlib import Path

from google.protobuf.message import Message

from brewblox_devcon_spark import codec
from brewblox_devcon_spark.codec import lookup
from brewblox_devcon_spark.models import EncodedPayload, ReadMode
from test.fixtures.messages import populate

FIXTURE = Path(__file__).parent / 'logged_golden.json'


def variants(entry: lookup.ObjectLookup) -> dict[str, Message]:
    full = populate(entry.message_cls())
    out = {
        'full': full,
        'empty': entry.message_cls(),
    }

    if entry.type_str == 'GpioModule':
        zero = populate(entry.message_cls())
        del zero.analogChannels[:]
        zero.analogChannels.add()
        populate(zero.analogChannels.add())
        out['zero'] = zero

    if entry.type_str == 'TempSensorExternal':
        zero = populate(entry.message_cls())
        zero.lastUpdated = 0
        out['zero'] = zero

    return out


def main():
    codec.setup()
    cdc = codec.CV.get()
    logged_mode = ReadMode['LOGGED']
    cases = []

    for entry in lookup.CV_OBJECTS.get():
        for variant, message in variants(entry).items():
            content = b64encode(message.SerializeToString()).decode()
            decoded = cdc.decode_payload(
                EncodedPayload(blockId=100, blockType=entry.type_int, content=content),
                mode=logged_mode,
            )
            assert decoded.blockType == entry.type_str, decoded
            cases.append(
                {
                    'blockType': entry.type_str,
                    'variant': variant,
                    'payload': content,
                    'logged': decoded.content,
                }
            )

    FIXTURE.write_text(json.dumps(cases, indent=2) + '\n')
    print(f'wrote {len(cases)} cases to {FIXTURE}')


if __name__ == '__main__':
    main()
