"""
Tests brewblox_codec_spark.codec
"""

from brewblox_codec_spark import codec


def create_obj():
    return {
        'type': 6,
        'obj': {
            'settings': {
                'address': 'address',
                'offset': 0
            }
        }
    }


def test_modify_if_present():
    input = create_obj()
    output = codec._modify_if_present(input, ['obj', 'settings', 'offset'], lambda x: x+1)
    assert output['obj']['settings'] == {
        'offset': 1,
        'address': 'address'
    }
    assert input == create_obj()

    output = codec._modify_if_present(input, ['type'], lambda x: x+1)
    assert output['type'] == 7

    output = codec._modify_if_present(input, ['gnome_count'], lambda x: x+1)
    assert output == create_obj()


def test_modify_if_present_no_copy():
    input = create_obj()
    output = codec._modify_if_present(input, ['type'], lambda x: x+1, mutate_input=True)

    assert output['type'] == 7
    assert input == output
    assert input != create_obj()
