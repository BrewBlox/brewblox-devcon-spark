"""
User-configurable unit conversion
"""

from brewblox_service import brewblox_logger
from pint import UnitRegistry

from brewblox_devcon_spark.exceptions import InvalidInput

LOGGER = brewblox_logger(__name__)

# Pint makes multiple I/O calls while constructing its UnitRegistry
# As long as we never modify the unit registry, we can keep it in module scope
# This significantly reduces setup time for unit tests
_UREG = UnitRegistry()


UNIT_ALTERNATIVES = {
    'Temp': [
        'celsius',
        'degC',
        'fahrenheit',
        'degF',
        'kelvin',
        'degK',
    ],
    'DeltaTemp': [
        'delta_degC',
        'delta_degF',
        'kelvin',
    ],
    'Time': [
        'millisecond',
        'second',
        'minute',
        'hour',
    ]
}

UNIT_ALTERNATIVES['DeltaTempPerTime'] = [
    f'{delta} / {time}'
    for delta in UNIT_ALTERNATIVES['DeltaTemp']
    for time in UNIT_ALTERNATIVES['Time']
]


class UnitConverter():

    def __init__(self):
        # ID: [system_unit, user_unit]
        self._table = {k: [v, v] for k, v in self.system_units.items()}

    @property
    def system_units(self):
        return {
            'Temp': 'degC',
            'DeltaTemp': 'delta_degC',
            'DeltaTempPerTime': 'delta_degC / second',
            'Time': 'second',
        }

    @property
    def user_units(self):
        return {k: v[1] for k, v in self._table.items()}

    @user_units.setter
    def user_units(self, new_cfg: dict):
        cfg = {k: [v, new_cfg.get(k, v)] for k, v in self.system_units.items()}

        for id, units in cfg.items():
            try:
                _UREG.Quantity(1, units[0]).to(units[1])
            except Exception as ex:
                raise InvalidInput(f'Invalid new unit config "{id}:{units}", {ex}')

        self._table = cfg

    def to_sys(self, amount, id, custom=None):
        conversion = self._table[id]
        return _UREG.Quantity(amount, custom or conversion[1]).to(conversion[0]).magnitude

    def to_user(self, amount, id):
        conversion = self._table[id]
        return _UREG.Quantity(amount, conversion[0]).to(conversion[1]).magnitude

    def user_unit(self, id):
        return self._table[id][1]
