"""
User-configurable unit conversion
"""

from brewblox_service import brewblox_logger
from pint import UnitRegistry

from brewblox_devcon_spark.exceptions import InvalidInput

LOGGER = brewblox_logger(__name__)


class UnitConverter():

    def __init__(self):
        self._ureg: UnitRegistry = UnitRegistry()
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
                self._ureg.Quantity(1, units[0]).to(units[1])
            except Exception as ex:
                raise InvalidInput(f'Invalid new unit config "{id}:{units}", {ex}')

        self._table = cfg

    def to_sys(self, amount, id, custom=None):
        conversion = self._table[id]
        return self._ureg.Quantity(amount, custom or conversion[1]).to(conversion[0]).magnitude

    def to_user(self, amount, id):
        conversion = self._table[id]
        return self._ureg.Quantity(amount, conversion[0]).to(conversion[1]).magnitude

    def user_unit(self, id):
        return self._table[id][1]
