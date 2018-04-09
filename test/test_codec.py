"""
Tests brewblox_codec_spark.codec
"""

from brewblox_codec_spark import codec


def create_obj():
    return {
        "type": 6,
        "obj": {
            "settings": {
                "address": "KP7p/ggAABc=",
                "offset": 0
            }
        }
    }


def test_modify_if_present():
    obj = codec._modify_if_present(create_obj(), ['obj', 'settings', 'offset'], lambda x: x+1)
    assert obj['obj']['settings']['offset'] == 1

    obj = codec._modify_if_present(create_obj(), ['type'], lambda x: x+1)
    assert obj['type'] == 7

    obj = codec._modify_if_present(create_obj(), ['gnome_count'], lambda x: x+1)
    assert obj == create_obj()
