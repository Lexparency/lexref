"""
The model.tables module depends (a priori) on sqlalchemy. But
this is only needed for building mappings and regexes in a more
sustainable manner, i.e. such that the language configuration
can be better extended and maintained. For the users of this package,
the sqlalchemy dependency can be avoided by replacing that module
with automatically generated python code that provides the exact
same mappings and functions but without using sqlalchemy.
This alternative tables module is generated with this script.
"""
import inspect
import os
import pprint
import re
from collections import defaultdict
from itertools import product

from lexref.model import tables as dm

sm = dm.SessionManager()
pp = pprint.PrettyPrinter(indent=4)

LANGUAGES = dm.AxisPattern.languages()
LANGS_X = LANGUAGES | {'XX'}
with sm() as s:
    VALUE_TAGS = {r[0] for r in s.query(dm.Value.tag).distinct()}

maps = defaultdict(list)


def repr_object(o):
    if type(o) in (dict, defaultdict):
        result = ', '.join(repr(k) + ': ' + repr_object(v) for k, v in o.items())
        return '{' + result + '}'
    elif type(o) is re.Pattern:
        return f"re.compile(r'{o.pattern}', flags={int(o.flags)})"
    else:
        return repr(o)


for cls in dm.Base.__subclasses__():
    maps[cls.__name__].append({'name': '__tablename__',
                               'value': cls.__tablename__})
    for name in dir(cls):
        if name.startswith('_') or name in ('metadata', 'registry'):
            continue
        a = getattr(cls, name)
        if type(a) in (str, int, tuple, list):
            maps[cls.__name__].append({'name': name, 'value': a})
        if type(a).__name__ != 'method':
            continue
        s = inspect.signature(a)
        if len(s.parameters) == 0:
            maps[cls.__name__].append({'name': name, 'result': a()})
        else:
            item = {
                'parameters': list(s.parameters.keys()),
                'name': name,
                'signature': str(s),
                'map': {}
            }
            if item['parameters'] == ['language']:
                for language in LANGUAGES:
                    item['map'][language] = a(language)
            elif set(item['parameters']) == {'language', 'only_treaties'}:
                for lang, b in product(LANGUAGES, (True, False)):
                    item['map'][(lang, b)] = a(lang, only_treaties=b)
            elif name == 'get_pattern_map' and cls == dm.Value:
                for tag, language in product(VALUE_TAGS, LANGS_X):
                    item['map'][(tag, language)] = a(tag, language)
            else:
                raise RuntimeError(
                    f'>>>> Handle: {cls.__name__}.{name} << {s} >>')
            maps[cls.__name__].append(item)

# pp.pprint(maps)

TABLES_PY = [
    "import re",
    "from typing import Dict, Pattern, List, Tuple",
    "from .group import AxisRole"
]


def append_line(statement, indent=0):
    TABLES_PY.append(" " * indent * 4 + statement)


def new_block(separation=1):
    for _ in range(separation):
        TABLES_PY.append('')


for class_name, methods in maps.items():
    new_block(2)
    TABLES_PY.append(f"class {class_name}:")
    for method in methods:
        if 'value' in method:
            append_line(f"{method['name']} = " + repr(method['value']), indent=1)
            continue
        new_block()
        append_line("@staticmethod", indent=1)
        if 'signature' in method:
            append_line(
                f"def {method['name']}{method['signature']}:", indent=1)
            if len(method['parameters']) == 1:
                key = method['parameters'][0]
            else:
                key = "({})".format(', '.join(method['parameters']))
            append_line(
                f"return " + repr_object(method['map']) + f"[{key}]",
                indent=2)
        else:
            append_line(f"def {method['name']}():", indent=1)
            append_line(f"return " + repr_object(method['result']), indent=2)

new_block()


OUTFILE_PATH = os.path.join(os.path.dirname(dm.__file__), 'tables_auto.py')


with open(OUTFILE_PATH, mode='w', encoding='utf-8') as f:
    f.write('\n'.join(TABLES_PY))


if __name__ == '__main__':
    print('Done!')
