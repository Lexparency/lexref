"""
Reference tag taxonomy
======================
References are built up by tokens which come in four groups "axis", "value",
"general expression", and "named_entity"; i.e.
Each group has several possible tag-values
  1) axis: Specifies the type of referred snippet.
     Implemented by class RefAxis
     E.g.: Article, Absatz, Part, ...
  2) value: Specifies the label of the reference within the corresponding
      labeling system. E.g. (a), First, 1), ...
  3) "connectors" are generic expressions, such as the words "and" or "or"
  4) named_entity: Documents with proper names.
     In this case. The "type" attribute refers directly to the local ID of the
     corresponding document.
"""
import re
import string
from functools import lru_cache
from operator import attrgetter
from typing import List, Tuple, Iterator, Any, Dict, Iterable

from .model import NamedEntity, Connector, Value, Group, \
    Axis, AxisRole
from .structures import Span, ReferenceToken, Coordinate, ReferenceTag, \
    Target, StdCoordinate, InconsistentTargetError, Cycle, UnsupportedRole
from .utils import MetaPatternHandler, repeat_until_true, Reference
from .settings import LANG_2_DOMAIN


def list_enum(seq: list, reverse=False) -> Iterator[Tuple[int, Any]]:
    if not reverse:
        return enumerate(seq)
    return reversed(list(enumerate(seq)))


class GroupPattern(MetaPatternHandler):
    _base = {
        'coordinates': '(axis:value|named_entity)',
        'connector_value': '(?P<leader>coordinate)value*'
                           '(?P<buddies>(connector:value+)+)'
                           '(?P<after>coordinate)?',
        'coordinate_connector_value':
        'coordinate(connector:value)+',
        'value_n': '(?P<leader>coordinate)value+',
        'axis_connector': '^axis:connector',
        'adjacent_coordinates': 'coordinate+'
    }

    @property
    @lru_cache()
    def mapping(self):
        return {g.name: g.value for g in Group}


class TagPattern(MetaPatternHandler):
    _base = {
        'spoken_latin': '(?<=Group.value)LATIN',
        'fourth_directive': 'SRNK[REG:DIR:DEC]',
        'spoken_rank':  # first and second point of ...
        'SRNK(?P<followers>Group.connector:SRNK)*Group.axis',
        're_reference': '[XPREVX]Group.axis',
        'orphan_axes': '(?<![XPREVX:SRNK])Group.axis$',
        'orphan_annex': '(?<![XPREVX:SRNK])ANX(?!Group.value)',
        'generic_context': '[BRCRPL:THEREOF]',
        'range_connected':  # e.g. "points (k)(ii) to (v)"
        'Group.coordinate:Group.value:RC:Group.value(?!Group.value)',
        'of_day': 'SPCLPR:NM$',  # e.g. of 12 December 2001 on Community designs
        'co_and_co': '^Group.coordinate:AND:Group.coordinate$',
        'co_desu_co': 'Group.coordinate:XDESUX:Group.coordinate',
        'first_end': 'SRNK$',
        'left_of_right':
        '(?P<subs>Group.coordinate+)[SPCLPR:XDESUX]:Group.coordinate(?!Group.coordinate)',
        'co_underthe_co': 'Group.coordinate:SPPLCR:Group.coordinate',
        'comma_stairway': '(Group.coordinate:COM)+Group.coordinate'
    }

    @property
    @lru_cache()
    def mapping(self) -> Dict[str, str]:
        t2g = Value.tag_2_group()
        letters = list(string.ascii_letters + string.digits) \
            + [chr(k) for k in range(913, 938)] \
            + [chr(k) for k in range(945, 970)]
        letters.reverse()
        result = {}
        for tag, group in t2g.items():
            if group == Group.named_entity.name:
                continue
            letter = letters.pop()
            result[tag] = letter
            result[f'Group.{group}'] = \
                result.get(f'Group.{group}', '') + letter
        for group in Group:
            try:
                result[f'Group.{group.name}'] = \
                    "[{}]".format(result[f'Group.{group.name}'])
            except KeyError:
                pass
        result['Group.coordinate'] = Coordinate.tag_value
        result[Coordinate.tag_value] = Coordinate.tag_value  # not alphabetic
        return result


class TokenSequence(list):
    """ A TokenSequence instance is a gathering of reference tokens. """
    sep = ':'
    white_spaces = re.compile(r'^\s*$')

    def __init__(self, rt: ReferenceToken):
        super().__init__([rt])
        self.gp = GroupPattern()
        self.tp = TagPattern()
        self._finalized = False

    @property
    def groups(self):
        return ''.join(child.group_tag for child in self)

    @property
    def values(self) -> str:
        # noinspection PyTypeChecker
        return ''.join(self.tp.mapping.get(child.tag_value, ' ')
                       for child in self)

    def append(self, rt: ReferenceToken):
        assert self[-1].span.end <= rt.span.start
        super().append(rt)

    @property
    def span(self) -> Span:
        return Span(self[0].span.start, self[-1].span.end)

    def __repr__(self):
        return type(self).__name__ + f"[{self.span}]"

    def __str__(self):
        return repr(self) + '\n  ' + '\n  '.join(map(repr, self))

    def to_dict(self, text: str = None) -> dict:
        result = {"span": self.span.to_dict(),
                  "children": [t.to_dict(text is not None) for t in self]}
        if text is not None:
            result['text'] = text[self.span.start:self.span.end]
        return result

    def single_token_2_coordinate(self, i, group):
        value = self.pop(i)
        coordinate = Coordinate(
            axis=ReferenceToken.anonymous_axis(value.span.start, tag=group.name),
            value=value)
        self.insert(i, coordinate)
        return coordinate

    def _handle_pattern_generic_context(self):
        """ Handling special kinds of back-references, such as
            - "... dessen erster Paragraph"
            - "... sus Articulos 7 y 8"
        """
        for i, m in self.tp.finditer('generic_context', self.values):
            coordinate = self.single_token_2_coordinate(i, Group.connector)
            coordinate.level = 10

    def finalize(self):
        if self._finalized:
            return
        self._cleanup()
        self._coordination()
        if not self:
            return
        self._nesting()
        self._finalized = True

    def _handle_pattern_fourth_directive(self):
        """ These have to be merged. """
        for i, m in self.tp.finditer('fourth_directive', self.values):
            this, axis = self[i:i+2]
            self[i] = ReferenceToken(
                axis.tag, Span(this.span.start, axis.span.end),
                axis.text + axis.tail + this.text, tail=axis.tail)

    def _handle_pattern_spoken_latin(self):
        for i, m in self.tp.finditer('spoken_latin', self.values):
            prev = self[i-1]
            this = self[i]
            suffix = Value.extract_as_number(this.text, 'LATIN', 'XX')
            if prev.tag.value != 'NM':
                if prev.text == prev.text.upper():
                    suffix = suffix.upper()
            prev.span = Span(prev.span.start, this.span.end)
            prev.tail = this.tail
            prev.suffix = suffix
            self.pop(i)

    def _handle_pattern_spoken_rank(self):
        for i, m in self.tp.finditer('spoken_rank', self.values):
            span = Span(*m.span())
            axis = self.pop(span.end - 1)
            for k in range(i, span.end - 1):
                if self[k].group_tag == Group.connector.value:
                    continue
                self.insert(k, Coordinate(value=self.pop(k), axis=axis))

    def _handle_pattern_re_reference(self):
        for i, _ in self.tp.finditer('re_reference', self.values):
            # TODO: move the self-reference and back-reference pattern to the
            #  axis-table and get rid of this loop.
            value = self.pop(i)
            self.insert(i, Coordinate(
                value=ReferenceToken.quasi_value(value.tag.value,
                                                 value.span,
                                                 value.text),
                axis=self.pop(i)))

    def _handle_pattern_coordinates(self):
        for i, m in self.gp.finditer('coordinates', self.groups):
            if m.group() == Group.named_entity.value:
                self.single_token_2_coordinate(i, Group.named_entity)
            else:
                self.insert(i, Coordinate(axis=self.pop(i), value=self.pop(i)))

    def _handle_pattern_range_connected(self):
        for i, m in self.tp.finditer('range_connected', self.values):
            leader, first, to, last = self[i:i+4]
            if not Value.compatible(first.tag.value, last.tag.value):
                continue
            first = Coordinate(ReferenceToken.anonymous_axis(first.span.start),
                               self.pop(i+1))
            first.level = leader.level + 1
            self.insert(i + 1, first)
            self.insert(i + 3, Coordinate(first.axis, self.pop(i + 3)))
            self[i+3].level = first.level

    def _handle_pattern_connector_value(self):
        for i, m in self.gp.finditer('connector_value', self.groups):
            leader = self[i]
            if m.group('after') is not None:
                after = self[m.span('after')[0]]
                if after.axis.tag.value == leader.axis.tag.value:
                    leader = self[i-1]
            start, end = m.span('buddies')
            for con in range(end - 1, start - 1, -1):
                connector = self[con]
                if connector.group_tag != Group.connector.value:  # -> self.gp.mapping['connector']
                    continue
                assert connector.tag.value in ('RC', 'COM', 'AND', 'OTHERX', 'LF')
                if not Value.compatible(self[con+1].tag.value,
                                        leader.value.tag.value):
                    continue
                self.insert(
                    con + 1,
                    Coordinate(axis=leader.axis, value=self.pop(con + 1)))

    def _handle_pattern_value_n(self):
        for i, m in self.gp.finditer('value_n', self.groups):
            leader = self[i]
            for index in range(i + 1, m.span()[1]):
                coordinate = Coordinate(
                    axis=ReferenceToken.anonymous_axis(self[index].span.start),
                    value=self.pop(index))
                coordinate.level = leader.level + 1
                self.insert(index, coordinate)
                leader = coordinate

    def _handle_pattern_coordinate_connector_value(self):
        for i, m in self.gp.finditer('coordinate_connector_value', self.groups):
            coordinate = self[i]
            end = m.span()[1]
            for j, (connector, value) in enumerate(zip(self[i+1:end:2],
                                                       self[i+2:end:2])):
                if connector.tag.value not in ('RC', 'AND', 'OTHERX', 'COM'):
                    break
                assert Value.compatible(coordinate.value.tag.value,
                                        value.tag.value)
                index = i + 2 * j + 2
                sibling = Coordinate(axis=coordinate.axis,
                                     value=self.pop(index))
                sibling.level = coordinate.level
                self.insert(index, sibling)

    def _handle_pattern_orphan_annex(self):
        for i, m in self.tp.finditer('orphan_annex', self.values):
            annex = self.pop(i)
            self.insert(i, Coordinate(
                axis=annex,
                value=ReferenceToken.quasi_value(
                    'ANX', annex.span, annex.text)))

    @property
    def coordinated(self) -> bool:
        return set(self.groups).issubset({Group.coordinate.value,
                                          Group.connector.value})

    def _coordination(self):
        for pattern_key in ('generic_context', 'fourth_directive', 'spoken_latin',
                            'spoken_rank', 'coordinates', 're_reference',
                            'range_connected', 'connector_value', 'value_n',
                            'coordinate_connector_value', 'orphan_annex'):
            getattr(self, f"_handle_pattern_{pattern_key}")()
            if self.coordinated:
                return

    def iter_coordinates(self) -> Iterable[Coordinate]:
        for item in self:
            if type(item) is Coordinate:
                yield item

    def iter_roots(self) -> Iterable[Coordinate]:
        for coordinate in self.iter_coordinates():
            if coordinate.parent is None:
                yield coordinate

    def _iter_siblings(self, leader: Coordinate) -> Iterable[Coordinate]:
        """ Iterate over coordinates that share the same Axis-Token. """
        for follower in self.iter_coordinates():
            if follower.axis == leader.axis:
                if follower.value != leader.value:
                    yield follower

    @staticmethod
    def nest_neighbours(precursor, iterator: Iterable[Coordinate]):
        effect = False
        for coordinate in iterator:
            if precursor.level < coordinate.level:
                precursor.append(coordinate)
                precursor = coordinate
                effect = True
            elif coordinate.level < precursor.level \
                    and precursor.parent is None \
                    and Axis.compatible(coordinate.axis.tag.value,
                                        precursor.axis.tag.value):
                coordinate.append(precursor)
                effect = True
            else:
                precursor = coordinate
        return effect

    def _nest_siblings(self):
        effect = False
        for coordinate in self.iter_coordinates():
            if coordinate.parent is None:
                for sibling in self._iter_siblings(coordinate):
                    if sibling.parent is not None:
                        parent = sibling.parent
                        coordinate.parent = parent
                        effect = True
                        break
                else:
                    continue
            else:
                parent = coordinate.parent
            for sibling in self._iter_siblings(coordinate):
                if sibling.parent is None:
                    sibling.parent = parent
                    effect = True
        return effect

    @repeat_until_true(4)
    def _nest_rest(self):
        effect = self._nest_siblings()
        effect = self.nest_neighbours(self[0], self.iter_roots()) or effect
        return not effect

    def _nest_adjacent(self):
        for i, m in self.gp.finditer('adjacent_coordinates', self.groups):
            self.nest_neighbours(self[i], self[i+1:m.span()[1]])

    def _nest_co_underthe_co(self):
        for i, _ in self.tp.finditer('co_underthe_co', self.values, reverse=False):
            self[i].append(self[i+2])
            for sibling in self._iter_siblings(self[i+2]):
                self[i].append(sibling)

    def _nest_left_of_right(self):
        for i, m in self.tp.finditer('left_of_right', self.values):
            child = self[i]
            new_parent = self[m.span()[1]-1]
            if len(m.group('subs')) > 1:  # this is more complicated
                last_sub = self[m.span('subs')[1]-1]
                if last_sub in child.ancestors:
                    child = last_sub
                else:
                    assert child in last_sub.ancestors
            if child.parent is not None:
                # noinspection PyUnresolvedReferences
                if child.parent.axis.tag_value != new_parent.axis.tag_value:
                    continue
            child.parent = new_parent

    def _nest_comma_stairways(self):
        """ E.g. "*Chapter 4, Section 3* of Regulation ..." """
        for i, m in self.tp.finditer('comma_stairway', self.values, reverse=False):
            end = m.span()[1]
            if len(self) == end:
                return
            parent = self[i]
            for j in range(i + 2, m.span()[1], 2):
                if parent.level >= self[j].level:
                    break
                parent.append(self[j])
                parent = self[j]

    def _nesting(self):
        if len(self) == 1:
            return
        if self.tp['co_and_co'].match(self.values):
            return  # e.g. Chapter VII and Article 83
        self._nest_adjacent()
        self._nest_desu()
        self._nest_co_underthe_co()
        self._nest_siblings()
        self._nest_comma_stairways()
        self._nest_left_of_right()
        self._nest_rest()

    def _nest_desu(self):
        for i, _ in self.tp.finditer('co_desu_co', self.values):
            # finding referred parent coordinate
            su_level = self[i+2].level
            for j in range(i-1, -1, -1):
                if self[j].group_tag == Group.coordinate.value:
                    if self[j].level < su_level:
                        self[j].append(self[i+2])
            self[i+2].append(self[i])

    def groups_representation(self, text: str) -> dict:
        """ Good for debugging. """
        return {
            'text': text[self.span.start:self.span.end],
            'groups': ':'.join(Group.value_2_name()[t.group_tag] for t in self),
        }

    def _pop_for(self, token_test, break_on_false=True, revert=None):
        removables = set()
        if revert is None:
            reverts = (True, False)
        else:
            reverts = (revert,)
        for revert in reverts:
            for i, token in list_enum(self, reverse=revert):
                if token_test(token):
                    removables.add(i)
                elif break_on_false:
                    break
        for i in sorted(removables, reverse=True):
            del self[i]
        return bool(removables)

    @repeat_until_true()
    def _cleanup(self):
        # 1.a. remove leading and trailing connectors
        effect = self._pop_for(lambda t: t.tag.group == Group.connector
                               and t.tag.value not in ('THEREOF', 'BRCRPL'))
        # TODO: One could "formally" move these backref tokens to the named_entity.
        #  This way one can get rid fo this special treatment.
        # 1.b. remove leading value-tokens, if not spoken rank.
        effect = self._pop_for(
            lambda t: t.tag.group == Group.value and t.tag.value != 'SRNK',
            revert=False) or effect
        if self.tp['orphan_axes'].search(self.values):
            if self[-1].tag.value != 'ANX':
                effect = True
                self.pop()
                if len(self) != 0:
                    self.pop()
        if self.gp['axis_connector'].search(self.groups):
            if self[0].tag.value != 'ANX':
                # Annex can be understood as coordinate directly.
                effect = True
                self.pop(0)
                self.pop(0)
        if len(self) == 1:
            if self[0].tag.group != Group.named_entity:
                if self[0].tag.value != 'ANX':
                    effect = True
                    self.pop(0)
        if self.tp['of_day'].search(self.values):
            self.pop()
            self.pop()
        if self.tp['first_end'].search(self.values) and len(self) != 2:
            self.pop()
        return not effect


class TokenSequences(list):
    """ Manages all encountered TokenSequence instances. """

    def __init__(self, language: str, text: str, only_treaties=False,
                 recents: Cycle = None):
        """
        :param text: Plain text. I.e. no html-markup.
        :param language: e.g. EN, DE; ES
        """
        super().__init__()
        self.text = text
        self.language = language
        self.only_treaties = only_treaties
        self.errors = 0
        self._extract()
        if recents is not None:
            self.recent = recents
        else:
            self.recent = Cycle(4)
        for i, sequence in list_enum(self, reverse=True):
            # noinspection PyBroadException
            try:
                sequence.finalize()
            except Exception:
                # TODO: log a warning here
                self.errors += 1
                del self[i]
                # raise  # Comment-in for debugging
            else:
                if not sequence:
                    del self[i]

    def iter_references(self, container: Target = None,
                        document: StdCoordinate = None,
                        min_role: AxisRole = None,
                        internet_domain: str = None) -> Iterable[Reference]:
        """
        :param container: Container context in form of a Target instance
        :param document: Default document (context aspect) in form of a
            StdCoordinate instance
        :param min_role: Minimum role level to be included. All Target
            instances, with ultimate_role.value < min_role.value will be skipped.
        :param internet_domain: https://...
        """
        if internet_domain is None:
            internet_domain = LANG_2_DOMAIN[self.language]
        for sequence in self:
            deepest = Target()
            for coordinate in sequence.iter_coordinates():
                # noinspection PyBroadException
                try:
                    target = coordinate.get_target(
                        self.language, container, document)
                    assert target
                    assert len(target) > 1 or not target.has_backref
                    if len(target) > len(deepest):
                        deepest = target
                    if target.has_backref:
                        target.join(self.recent)
                    assert not(self.recent is None and target.has_backref)
                    assert target.ultimate_role.value <= min_role.value
                    yield Reference(
                        coordinate.value.span,
                        target.get_href(internet_domain),
                        target.get_spoken(self.language)
                    )
                except InconsistentTargetError:
                    self.errors += 1
                    break
                except (AssertionError, UnsupportedRole):
                    continue
                except Exception:
                    self.errors += 1
                    # raise  # for debugging
                else:
                    self.recent.turn(deepest)

    def to_dict(self) -> dict:
        """ For unittest purposes. """
        return {"text": self.text,
                "language": self.language,
                "hoods": [hood.to_dict() for hood in self]}

    def _extract(self):
        refs = sorted(self._find_tokens(), key=attrgetter('sort_key'))
        if len(refs) == 0:
            return

        self.append(TokenSequence(refs[0]))
        for r in refs[1:]:
            inter_span = Span(self[-1][-1].span.end, r.span.start)
            if inter_span.start > inter_span.end:
                continue  # TODO: raise a warning here
            tail = self.text[inter_span.start:inter_span.end]
            if TokenSequence.white_spaces.match(tail) is None \
                    or r.tag.value == 'SEPARATE':
                self.append(TokenSequence(r))
            else:
                self[-1][-1].tail = tail
                self[-1].append(r)
        for i, token_sequence in list_enum(self, reverse=True):
            # remove neighbourhoods that consist of a single token,
            # if that token is not of type named tuple
            if len(token_sequence) == 1:
                if token_sequence[0].tag.group != Group.named_entity:
                    if token_sequence[0].tag.value != 'ANX':
                        del self[i]

    name_2_group = {g.name: g for g in Group}

    def _find_tokens(self) -> List[ReferenceToken]:
        # Assign named entities first
        references = []
        for cls in (NamedEntity, Connector, Axis, Value):
            if cls is NamedEntity:
                iterator = NamedEntity.tag_2_pattern(
                    self.language, self.only_treaties).items()
            else:
                iterator = cls.tag_2_pattern(self.language).items()
            for key, pattern in iterator:
                for match in pattern.finditer(self.text):
                    references.append(ReferenceToken(
                        ReferenceTag(self.name_2_group[cls.__tablename__], key),
                        Span(*match.span()),
                        match.group()
                    ))
        return references

    def __str__(self):
        return self.text + '\n    ' + \
               ('\n'.join(map(str, self))).replace('\n', '\n    ')
