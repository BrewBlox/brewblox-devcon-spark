"""
User-configurable unit conversion
"""

from dataclasses import dataclass
from typing import Dict

from aiohttp import web
from brewblox_service import brewblox_logger, features
from pint import UnitRegistry

from brewblox_devcon_spark.exceptions import InvalidInput

LOGGER = brewblox_logger(__name__)

# Pint makes multiple I/O calls while constructing its UnitRegistry
# As long as we never modify the unit registry, we can keep it in module scope
# This significantly reduces setup time for unit tests
_UREG = UnitRegistry()

SYSTEM_TEMP = 'degC'

FORMATS = {
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
}


@dataclass(frozen=True)
class UnitMapping:
    key: str
    system_value: str
    user_value: str


def derived_table(user_temp) -> Dict[str, UnitMapping]:
    # Python 3.6+ guarantees values being insertion-ordered
    sys_vals = [s.format(temp=SYSTEM_TEMP) for s in FORMATS.values()]
    user_vals = [s.format(temp=user_temp) for s in FORMATS.values()]

    return {
        k: UnitMapping(k, sys_val, user_val)
        for (k, sys_val, user_val)
        in zip(FORMATS.keys(), sys_vals, user_vals)
    }


class UnitConverter(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)
        # Init with system temp. All mappings will have system_value == user_value
        self._table = derived_table(SYSTEM_TEMP)

    async def startup(self, app: web.Application):
        pass

    async def shutdown(self, app: web.Application):
        pass

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
        return _UREG.Quantity(amount, custom or mapping.user_value).to(mapping.system_value).magnitude

    def to_user_value(self, amount: float, id: str) -> float:
        mapping = self._table[id]
        return _UREG.Quantity(amount, mapping.system_value).to(mapping.user_value).magnitude

    def to_sys_unit(self, id):
        return self._table[id].system_value

    def to_user_unit(self, id):
        return self._table[id].user_value


def setup(app: web.Application):
    features.add(app, UnitConverter(app))


def get_converter(app: web.Application) -> UnitConverter:
    return features.get(app, UnitConverter)
