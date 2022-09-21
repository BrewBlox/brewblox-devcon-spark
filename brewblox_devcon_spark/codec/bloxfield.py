"""
Reflection on bloxtype objects
"""


def is_bloxfield(obj):
    return isinstance(obj, dict) and '__bloxtype' in obj


def is_link(obj):
    return isinstance(obj, dict) and obj.get('__bloxtype') == 'Link'


def is_defined_link(obj):
    return is_link(obj) \
        and obj.get('id') \
        and obj.get('type')


def is_quantity(obj):
    return isinstance(obj, dict) and obj.get('__bloxtype') == 'Quantity'


def is_defined_quantity(obj):
    return is_quantity(obj) \
        and obj.get('value') is not None \
        and obj.get('unit')
