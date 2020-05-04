"""
User-configurable unit conversion
"""

from typing import Dict, List, Tuple

from brewblox_service import brewblox_logger
from pint import UnitRegistry

from brewblox_devcon_spark.exceptions import InvalidInput

LOGGER = brewblox_logger(__name__)

# Pint makes multiple I/O calls while constructing its UnitRegistry
# As long as we never modify the unit registry, we can keep it in module scope
# This significantly reduces setup time for unit tests
_UREG = UnitRegistry()

SYSTEM_TEMP = 'degC'

FORMATS = {
    'Temp': '{temp}',
    'InverseTemp': '1 / {temp}',
    'Second': 'second',
    'Minute': 'minute',
    'Hour': 'hour',
    'DeltaTemp': 'delta_{temp}',
    'DeltaTempPerSecond': 'delta_{temp} / second',
    'DeltaTempPerMinute': 'delta_{temp} / minute',
    'DeltaTempPerHour': 'delta_{temp} / hour',
    'DeltaTempMultSecond': 'delta_{temp} * second',
    'DeltaTempMultMinute': 'delta_{temp} * minute',
    'DeltaTempMultHour': 'delta_{temp} * hour',
}


def derived_table(user_temp) -> Dict[str, Tuple[str, str]]:
    # Python 3.6+ guarantees values being insertion-ordered
    sys_vals = [s.format(temp=SYSTEM_TEMP) for s in FORMATS.values()]
    user_vals = [s.format(temp=user_temp) for s in FORMATS.values()]

    return {
        k: [sys_val, user_val]
        for (k, sys_val, user_val)
        in zip(FORMATS.keys(), sys_vals, user_vals)
    }


class UnitConverter():

    def __init__(self):
        # UnitType: [system_unit, user_unit]
        # Init with system temp
        self._table = derived_table(SYSTEM_TEMP)

    @property
    def unit_alternatives(self) -> Dict[str, List[str]]:
        return {'Temp': ['degC', 'degF']}

    @property
    def user_units(self) -> Dict[str, str]:
        return {'Temp': self._table['Temp'][1]}

    @user_units.setter
    def user_units(self, newV: Dict[str, str]):
        temp = newV.get('Temp', SYSTEM_TEMP)
        cfg = derived_table(temp)

        for id, units in cfg.items():
            try:
                _UREG.Quantity(1, units[0]).to(units[1])
            except Exception as ex:
                raise InvalidInput(f'Invalid new unit config "{id}:{units}", {ex}')

        self._table = cfg

    def to_sys_value(self, amount: float, id: str, custom=None) -> float:
        conversion = self._table[id]
        return _UREG.Quantity(amount, custom or conversion[1]).to(conversion[0]).magnitude

    def to_user_value(self, amount: float, id: str) -> float:
        conversion = self._table[id]
        return _UREG.Quantity(amount, conversion[0]).to(conversion[1]).magnitude

    def to_sys_unit(self, id):
        return self._table[id][0]

    def to_user_unit(self, id):
        return self._table[id][1]
