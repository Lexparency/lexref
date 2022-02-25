from enum import Enum, Enum as BuiltinEnum
from functools import lru_cache


class Group(Enum):
    named_entity = 'a'
    connector = 'b'
    axis = 'c'
    value = 'd'
    coordinate = 'e'

    def __repr__(self):
        return "{}.{}".format(type(self).__name__, self.name)

    @classmethod
    @lru_cache()
    def value_2_name(cls):
        return {g.value: g.name for g in cls}


class AxisRole(BuiltinEnum):
    domain = 0     # A legislative corpus, like "European Law"
    document = 1   # Regulation, Directive, Treaty
    container = 2  # Part, Chapter, ...
    annex = 3      # Special handling, due to ambivalent role
    leaf = 4       # Article, Preamble, Annex.
    paragraph = 5  # Point, Paragraph. "Phrase" is not considered
    phrase = 6     # Typically not numbered. Just a phrase
    mixed = 10     # Only for later handling
    token = 20     # Used as default for "min_role" in Reflector

    @classmethod
    @lru_cache()
    def from_name(cls, name):
        for g in cls:
            if g.name == name:
                return g

    def __repr__(self):
        return type(self).__name__ + '.' + self.name