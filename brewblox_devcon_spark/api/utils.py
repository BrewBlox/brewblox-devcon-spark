"""
API utility functions
"""


from contextlib import contextmanager

from brewblox_devcon_spark import exceptions


@contextmanager
def collecting_input():
    try:
        yield
    except KeyError as ex:
        raise exceptions.MissingInput(ex)


def strex(ex):
    return f'{type(ex).__name__}({str(ex)})'
