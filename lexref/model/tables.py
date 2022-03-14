import os
import re
from contextlib import contextmanager
from functools import lru_cache
from operator import attrgetter
from typing import Dict, Pattern, List, Tuple

from sqlalchemy import Column, String, Integer, ForeignKey, create_engine, \
    Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from .group import AxisRole, Group

from ..utils import Singleton


Base = declarative_base()

group = Enum(*[g.name for g in Group])


class SessionManager(metaclass=Singleton):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'patterns.db')

    def __init__(self):
        self.engine = create_engine('sqlite:///' + self.DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def __call__(self):
        s = self.Session()
        try:
            yield s
            s.commit()
        except Exception as e:
            s.rollback()
            raise e
        finally:
            s.close()


class Tag(Base):
    __tablename__ = 'tag'

    tag = Column(String(10), primary_key=True)
    group = Column(group)


class Axis(Base):
    __tablename__ = 'axis'

    tag = Column(String(10), ForeignKey(Tag.tag), primary_key=True)
    level = Column(Integer)
    # Indicates conventional hierarchy level of item type. E.g. paragraphs are
    #   typically below article level; or Chapter are typically below Parts.
    role = Column(Enum(*(r.name for r in AxisRole)))
    description = Column(String(200))

    patterns = relationship("AxisPattern")

    @classmethod
    @lru_cache()
    def tag_2_level(cls) -> Dict[str, int]:
        with SessionManager()() as s:
            result = {r.tag: r.level for r in s.query(cls)}
        return result

    @classmethod
    @lru_cache()
    def tag_2_pattern(cls, language) -> Dict[str, Pattern]:
        with SessionManager()() as s:
            result = {r.tag: re.compile(r.pattern, flags=(re.I | re.U))
                      for a in s.query(cls) for r in a.patterns
                      if r.language == language}
        return result

    @classmethod
    @lru_cache()
    def tag_2_standard(cls, language) -> Dict[str, str]:
        with SessionManager()() as s:
            result = {r.tag: r.standard
                      for a in s.query(cls) for r in a.patterns
                      if r.language == language}
        return result

    @classmethod
    @lru_cache()
    def tag_2_role(cls) -> Dict[str, AxisRole]:
        name_2_role = {g.name: g for g in AxisRole}
        with SessionManager()() as s:
            result = {r.tag: name_2_role.get(r.role) for r in s.query(cls)}
        result[Group.named_entity.name] = AxisRole.document
        result[''] = AxisRole.paragraph
        return result


class AxisPattern(Base):
    __tablename__ = 'axis_pattern'

    tag = Column(String(10), ForeignKey(Axis.tag), primary_key=True)
    language = Column(String(2), primary_key=True)
    pattern = Column(String(60), nullable=False)
    # generic pattern, i.e. all cases and any genus
    standard = Column(String(60))
    # Expression to be used for building the reference title (no pattern).

    @classmethod
    def languages(cls):
        with SessionManager()() as s:
            result = {r[0] for r in s.query(cls.language).distinct()}
        return result


class Value(Base):
    __tablename__ = 'value'

    order = Column(Integer, nullable=False)
    tag = Column(String(10), ForeignKey(Tag.tag), primary_key=True)
    description = Column(String(100))
    examples = Column(String(50))
    decorable = Column(Boolean)
    # Indicates whether token could be equipped with brackets.
    #   This would lead to variations of this value type: _B, _BB
    caseable = Column(Boolean)
    # indicates if by applying the .upper or the .lower method, one could
    # obtain further different patterns. This would lead to variations of this
    # type with the suffix _U and _L
    capitalizable = Column(Boolean)
    # indicates if the application of the .capitalize() method makes sense, e.g.
    # "First", or "One". Capitalizable values are stored in the capitalized
    # version as default value.
    convert = Column(Boolean)
    # indicates if the expression should be converted to the number it
    # represents, when building the reference target.

    _value_patterns = relationship('ValuePattern', backref='type')

    backref = ('XPREVX', 'BRCRPL', 'THEREOF')

    def full_pattern(self, language) -> str:
        # noinspection PyTypeChecker
        patterns = {vp.pattern
                    for vp in self._value_patterns
                    if vp.language in {language, 'XX'}}
        if len(patterns) == 0:
            raise NotImplementedError(
                f"No patterns for {self.tag} ({language})")
        return '|'.join(patterns)

    def iter_sub_patterns(self, language):
        full_pattern = self.full_pattern(language)
        if self.capitalizable:
            assert not self.decorable
            yield self.tag, \
                re.compile(rf'\b({full_pattern})\b', flags=(re.I | re.U))
        else:
            if self.caseable:
                cases = (('_L', full_pattern.lower()),
                         ('_U', full_pattern.upper()))
            else:
                cases = (('', full_pattern),)
            for s1, case in cases:
                tag = self.tag + s1
                if tag in ('EURCOO', 'EULCOO'):
                    # TODO: make this decision depending on, either a further
                    #   config parameter, within this table, or on the internals
                    #   of the pattern.
                    yield tag, re.compile(rf'({case})', flags=re.I)
                else:
                    if s1 == '_U' and self.tag == 'ROM':
                        yield tag, re.compile(rf'\b({case})[A-Ha-h]?\b')
                    else:
                        yield tag, re.compile(rf'\b({case})\b')
                if self.decorable:
                    for s2, decoration in (('_B', r'\b({})\)'),
                                           ('_BB', r'\(({})\)')):
                        yield tag + s2, re.compile(decoration.format(case))

    @classmethod
    @lru_cache()
    def get_pattern_map(cls, tag, language) -> Dict[str, Pattern]:
        with SessionManager()() as s:
            self = s.query(cls).get((tag,))
            result = {
                r.as_number: re.compile(r.pattern, flags=(re.I | re.U))
                for r in self._value_patterns
                if r.language == language and r.as_number != '-1'
            }
        return result

    @classmethod
    @lru_cache()
    def tag_2_pattern(cls, language):
        with SessionManager()() as s:
            rows = sorted(s.query(cls), key=attrgetter('order'))
            result = {tag: pattern
                      for r in rows
                      for tag, pattern in r.iter_sub_patterns(language)}
        return result

    @classmethod
    @lru_cache()
    def tag_2_group(cls) -> dict:
        with SessionManager()() as s:
            result = {r.tag: r.group for r in s.query(Tag)}
        for tag in cls.tag_2_pattern('EN'):
            # Making sure to get all the decorated versions as well.
            result[tag] = Group.value.name
        return result


class ValuePattern(Base):
    __tablename__ = 'value_pattern'

    tag = Column(String(10), ForeignKey(Value.tag), primary_key=True)
    as_number = Column(String(3), primary_key=True)
    # XX for language un-specific patterns
    language = Column(String(2), primary_key=True)
    pattern = Column(String(200), nullable=False)


class NamedEntity(Base):
    __tablename__ = 'named_entity'

    tag = Column(String(100), ForeignKey(Tag.tag), primary_key=True)
    language = Column(String(2), primary_key=True)
    title_pattern = Column(String(100))
    abbreviation = Column(String(10))
    title = Column(String(100))

    @classmethod
    @lru_cache()
    def tag_2_abbreviation(cls, language):
        with SessionManager()() as s:
            result = {r.tag: r.abbreviation or r.title
                      for r in s.query(cls).filter(cls.language == language)}
        return result

    @classmethod
    @lru_cache()
    def key_pattern(cls, language, only_treaties=False) -> List[Tuple[str, Pattern]]:
        with SessionManager()() as s:
            rows = s.query(cls).filter(cls.language == language)
            if only_treaties:
                # noinspection PyUnresolvedReferences
                rows = rows.filter(~cls.tag.like('3_________')) \
                    .filter(~cls.tag.like('http%'))
            result = []
            for r in rows:
                for pattern, f in ((r.title_pattern, re.I | re.U),
                                   (r.abbreviation, re.U)):
                    if pattern is None:
                        continue
                    result.append((
                        r.tag, re.compile(rf'\b({pattern})\b', flags=f)))
        return result

    @classmethod
    @lru_cache()
    def tag_2_pattern(cls, language, only_treaties=False) -> Dict[str, Pattern]:
        result = {}
        with SessionManager()() as s:
            rows = s.query(cls).filter(cls.language == language)
            if only_treaties:
                # noinspection PyUnresolvedReferences
                rows = rows.filter(~cls.tag.like('3_________')) \
                    .filter(~cls.tag.like('http%'))
            result['PND_ABBREV'] = re.compile(
                r'\b({})\b'.format('|'.join(
                    r.abbreviation
                    for r in rows if r.abbreviation is not None)),
                flags=re.U)
            result['PND_TITLE'] = re.compile(
                r'\b({})\b'.format('|'.join(
                    r.title_pattern
                    for r in rows if r.title_pattern is not None)),
                flags=re.U)
        return result


class Connector(Base):
    __tablename__ = 'connector'

    tag = Column(String(10), ForeignKey(Tag.tag), primary_key=True)
    language = Column(String(2), primary_key=True)
    pattern = Column(String(50))
    add_stopper = Column(Boolean)
    # Indicates whether the pattern is meant to be padded with word-marks "\b".
    description = Column(String(100))

    @property
    @lru_cache()
    def compiled_pattern(self) -> Pattern:
        if self.add_stopper:
            pattern = rf'\b{self.pattern}\b'
        else:
            pattern = self.pattern
        return re.compile(pattern)

    @classmethod
    @lru_cache()
    def tag_2_pattern(cls, language) -> Dict[str, Pattern]:
        with SessionManager()() as s:
            # noinspection PyUnresolvedReferences
            result = {r.tag: r.compiled_pattern
                      for r in s.query(cls)
                      .filter(cls.language.in_((language, 'XX')))}
        return result
