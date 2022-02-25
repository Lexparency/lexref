from functools import lru_cache

from .group import Group, AxisRole
from .tables import (
    Axis,
    AxisPattern,
    AxisRole,
    Value,
    NamedEntity,
    Connector,
)

__all__ = [
    'Group',
    'Axis',
    'AxisPattern',
    'AxisRole',
    'Value',
    'NamedEntity',
    'Connector',
]


# noinspection PyPep8Naming
@lru_cache()
def _Axis_compatible(ax1, ax2):
    try:
        roles = {Axis.tag_2_role()[ax1], Axis.tag_2_role()[ax2]}
    except KeyError:
        return True
    if AxisRole.container in roles:
        if len(roles) == 1 or AxisRole.document in roles:
            return True
        return False
    return True


# noinspection PyPep8Naming
@lru_cache(maxsize=1024)
def _Value_extract_as_number(expression, tag, language):
    for number, pattern in Value.get_pattern_map(tag, language).items():
        if pattern.match(expression) is not None:
            return number


@lru_cache(maxsize=2024)
def _compatible(key1, key2) -> bool:
    """ Check if given value-keys could refer to same axis. """
    if key1 == key2:
        return True
    if '_' in key1:
        key1, s1 = key1.split('_', 1)
    else:
        s1 = ''
    if '_' in key2:
        key2, s2 = key2.split('_', 1)
    else:
        s2 = ''
    if 'AMBRA' not in (key1, key2):
        return False
    if s1 != s2:
        return False
    other = key1 if key1 != 'AMBRA' else key2
    return other in ('AL', 'ROM')


Axis.compatible = _Axis_compatible
Value.extract_as_number = _Value_extract_as_number
Value.compatible = _compatible
