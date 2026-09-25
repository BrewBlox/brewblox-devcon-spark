"""
User-configurable unit conversion
"""

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache

from pint import Unit, UnitRegistry

from brewblox_devcon_spark.exceptions import InvalidInput

SYSTEM_TEMP = 'degC'
FORMATS = {
    'NotSet': '',
    'Celsius': '{temp}',
    'InverseCelsius': '1 / {temp}',
    'Second': 'second',
    'Minute': 'minute',
    'Hour': 'hour',
    'DeltaCelsius': 'delta_{temp}',
    'DeltaCelsiusPerSecond': 'delta_{temp} / second',
    'DeltaCelsiusPerMinute': 'delta_{temp} / minute',
    'DeltaCelsiusPerHour': 'delta_{temp} / hour',
    'DeltaCelsiusMultSecond': 'delta_{temp} * second',
    'DeltaCelsiusMultMinute': 'delta_{temp} * minute',
    'DeltaCelsiusMultHour': 'delta_{temp} * hour',
    'MilliBar': 'millibar',
    'Volt': 'volt',
    'Ohm': 'ohm',
    'MilliLiter': 'milliliter',
    'MilliLiterPerSecond': 'milliliter / second',
    'Millisecond': 'millisecond',
}

# Pint makes multiple I/O calls while constructing its UnitRegistry
# As long as we never modify the unit registry, we can keep it in module scope
# This significantly reduces setup time for unit tests
_UREG = UnitRegistry()

LOGGER = logging.getLogger(__name__)
CV: ContextVar['UnitConverter'] = ContextVar('unit_conversion.UnitConverter')


@cache
def _unit(name: str) -> Unit:
    # Parsing the unit string is most of the cost of a conversion
    return _UREG.Unit(name)


def _convert(amount: float, src: str, dst: str) -> float:
    # Pint returns the amount as is when the units are the same: skip it.
    # Values are converted on every read, and users that keep the system units are the common case.
    if src == dst:
        return amount
    return _UREG.Quantity(amount, _unit(src)).to(_unit(dst)).magnitude


@dataclass(frozen=True)
class UnitMapping:
    key: str
    system_value: str
    user_value: str


def derived_table(user_temp) -> dict[str, UnitMapping]:
    # Python 3.7+ guarantees values being insertion-ordered
    sys_vals = [s.format(temp=SYSTEM_TEMP) for s in FORMATS.values()]
    user_vals = [s.format(temp=user_temp) for s in FORMATS.values()]

    return {
        k: UnitMapping(k, sys_val, user_val)
        for (k, sys_val, user_val) in zip(FORMATS.keys(), sys_vals, user_vals, strict=False)
    }


class UnitConverter:
    def __init__(self):
        # Init with system temp. All mappings will have system_value == user_value
        self._table = derived_table(SYSTEM_TEMP)

    @property
    def temperature(self) -> str:
        return self._table['Celsius'].user_value

    @temperature.setter
    def temperature(self, temp: str = SYSTEM_TEMP):
        cfg = derived_table(temp)

        for id, mapping in cfg.items():
            try:
                _UREG.Quantity(1, mapping.user_value).to(mapping.system_value)
            except Exception as ex:
                raise InvalidInput(f'Invalid new unit config {mapping}, {ex}')

        self._table = cfg

    def to_sys_value(self, amount: float, id: str, custom=None) -> float:
        mapping = self._table[id]
        return _convert(amount, custom or mapping.user_value, mapping.system_value)

    def to_user_value(self, amount: float, id: str) -> float:
        mapping = self._table[id]
        return _convert(amount, mapping.system_value, mapping.user_value)

    def to_sys_unit(self, id):
        return self._table[id].system_value

    def to_user_unit(self, id):
        return self._table[id].user_value


def setup():
    CV.set(UnitConverter())
