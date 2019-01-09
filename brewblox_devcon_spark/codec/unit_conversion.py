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
        'degC',
        'degF',
        'degK',
    ],
    'Time': [
        'millisecond',
        'second',
        'minute',
        'hour',
    ],
    'LongTime': [
        'hour',
        'day',
    ],
}


def derived_cfg(base_cfg):
    temps = base_cfg['Temp']
    times = base_cfg['Time']
    long_times = base_cfg['LongTime']
    inverse_temps = [f'1 / {temp}' for temp in temps]
    delta_temps = [temp if temp in ['degK', 'kelvin'] else f'delta_{temp}' for temp in temps]
    delta_temp_per_times = [f'{delta_temp} / {time}' for delta_temp, time in zip(delta_temps, times)]
    delta_temp_times = [f'{delta_temp} * {time}' for delta_temp, time in zip(delta_temps, times)]
    delta_temp_per_long_times = [f'{delta_temp} / {time}' for delta_temp, time in zip(delta_temps, long_times)]
    delta_temp_long_times = [f'{delta_temp} * {time}' for delta_temp, time in zip(delta_temps, long_times)]

    return {
        'Temp': temps,
        'Time': times,
        'LongTime': long_times,
        'InverseTemp': inverse_temps,
        'DeltaTemp': delta_temps,
        'DeltaTempPerTime': delta_temp_per_times,
        'DeltaTempTime': delta_temp_times,
        'DeltaTempPerLongTime': delta_temp_per_long_times,
        'DeltaTempLongTime': delta_temp_long_times,
    }


class UnitConverter():

    def __init__(self):
        # ID: [system_unit, user_unit]
        self._table = derived_cfg({k: [v, v] for k, v in self.system_units.items()})

    @property
    def system_units(self):
        return {
            'Temp': 'degC',
            'Time': 'second',
            'LongTime': 'hour',
        }

    @property
    def user_units(self):
        return {k: self._table[k][1] for k in self.system_units.keys()}

    @user_units.setter
    def user_units(self, new_cfg: dict):
        cfg = derived_cfg({k: [v, new_cfg.get(k, v)] for k, v in self.system_units.items()})

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
