from __future__ import annotations
from abc import ABCMeta
from collections import namedtuple
from functools import lru_cache
from typing import List, Union

from anytree import NodeMixin, RenderTree

from .model import Group, Axis, Value, NamedEntity, AxisRole
from .utils import Span, CacheWrapper
from .celex_handling import celexer, get_doc_type


class Cycle(list):

    def __init__(self, length, *args):
        super().__init__(*args)
        self.length = length

    def turn(self, item):
        self.insert(0, item)
        if len(item) > self.length:
            self.pop()


class StdCoordinate(namedtuple('SC', ['axis', 'value', 'role'])):

    @property
    def collated(self) -> str:
        if self.value is None:
            return self.axis
        value = self.value.strip('()')
        if self.role in (AxisRole.paragraph, AxisRole.document):
            return value
        if self.role in (AxisRole.container, AxisRole.leaf):
            return f'{self.axis}_{value}'
        raise RuntimeError(f'Strange role for StdCoordinate: {self.role}')

    @lru_cache()
    def get_spoken(self, language) -> Union[str, None]:
        t2s = Axis.tag_2_standard(language)
        if self.axis == 'PND':
            return NamedEntity.tag_2_abbreviation(language)[self.value]
        if self.value is None and self.axis == 'ANX':
            return ' ' + t2s['ANX']
        if self.axis in celexer.cases:
            return ' {} {}'.format(t2s[self.axis],
                                   celexer.invert(self.value, language)[1])
        axis = t2s.get(self.axis, '')
        if axis is None:
            return
        if axis == '':
            return self.value
        return f" {axis} {self.value}"


_t2r = CacheWrapper(Axis.tag_2_role)


@lru_cache(maxsize=1024)
def _standardize(axis_tag, value_tag, value, language) -> StdCoordinate:
    if value_tag in Value.backref:
        return StdCoordinate(axis_tag, value_tag, _t2r.get(axis_tag))
    if axis_tag == 'ANX':
        if value_tag == 'ANX':
            return StdCoordinate('ANX', None, AxisRole.container)
        return StdCoordinate('ANX', value, AxisRole.leaf)
    if axis_tag in celexer.cases:
        if value_tag == 'EUFCOO':
            # "Framework Decisions" are sometimes referred to as just "Decisions".
            # Therefore, we need an override.
            axis_tag = 'FDC'
        return StdCoordinate(axis_tag, celexer.convert(axis_tag, value, language),
                             AxisRole.document)
    if value_tag in ('SRNK', 'SPN'):
        return StdCoordinate(axis_tag,
                             Value.extract_as_number(value, value_tag, language),
                             _t2r.get(axis_tag, AxisRole.paragraph))
    if axis_tag == Group.named_entity.name:
        for key, pattern in NamedEntity.key_pattern(language):
            if pattern.match(value) is not None:
                return StdCoordinate('PND', key, AxisRole.document)
    return StdCoordinate(axis_tag, value, _t2r.get(axis_tag, AxisRole.paragraph))


class NestingError(Exception):
    pass


class InconsistentTargetError(Exception):
    pass


class UnsupportedRole(Exception):
    pass


class JoiningError(Exception):
    pass


class ReferenceTag(namedtuple('RT', ['group', 'value'])):

    def to_dict(self):
        """ for unittest purposes """
        result = dict(self._asdict())
        result['group'] = self.group.name
        return result


class ReferenceToken:
    __slots__ = ['tag', 'span', 'text', 'tail', 'suffix']

    def __init__(self, tag: ReferenceTag, span: Span, text: str = None,
                 tail: str = None):
        self.tag = tag
        self.span = span
        self.text = text
        self.tail = tail
        self.suffix = None  # for handling the spoken latin

    @property
    def group_tag(self):
        return self.tag.group.value

    @property
    def tag_value(self):
        return self.tag.value

    @property
    def sort_key(self):
        return self.span.start, - self.span.length

    def __repr__(self):
        return type(self).__name__ + '({})'.format(
            ', '.join(f"{name}=" + repr(getattr(self, name))
                      for name in self.__slots__))\
            .replace(', suffix=None', '')

    def to_dict(self, text=False) -> dict:
        result = {"tag": self.tag.to_dict(),
                  "span": self.span.to_dict()}
        if text:
            result['text'] = self.text
        return result

    @classmethod
    def anonymous_axis(cls, position: int, tag=''):
        return cls(ReferenceTag(Group.axis, tag), Span(position, position))

    @classmethod
    def quasi_value(cls, value, span: Span, text: str):
        return cls(ReferenceTag(Group.value, value), span, text)

    def __eq__(self, other):
        if self.span != other.span:
            return False
        if self.tag != other.tag:
            return False
        return True


class Target(list):
    """ List of StdCoordinate to handle the reference target """

    @property
    def ultimate_role(self):
        try:
            return self[0].role
        except IndexError:
            return

    @classmethod
    def create(cls, input_) -> Union[Target[StdCoordinate], None]:
        if input_ is None:
            return
        t = type(input_)
        if t is cls:
            return input_
        if t is list:
            # Needed for the REST API, when container_context is provided
            # as list of objects with "value" and "axis" properties.
            assert type(input_[0]) is dict  # and the other items as well.
            return Target(StdCoordinate(i['axis'], i['value'], _t2r[i['axis']])
                          for i in input_)
        if t is str:
            if input_ == 'toc':
                return
            if input_.startswith('toc-'):
                input_ = input_.replace('toc-', '')
                if input_ == 'ANX':
                    return Target([StdCoordinate('ANX', None, AxisRole.container)])
                return Target(
                    StdCoordinate(*level.split('_', 1), role=AxisRole.container)
                    for level in input_.split('-'))
            elif input_.startswith('/eu/'):
                celex = input_.split('/')[2]
                return Target([StdCoordinate(get_doc_type(celex), celex,
                                             AxisRole.document)])

    @property
    def roles(self):
        return [c.role for c in self]

    @property
    def role(self) -> AxisRole:
        roles = set(self.roles)
        if len(roles) == 1:
            return roles.pop()
        if AxisRole.container in roles:
            if roles != {AxisRole.container, AxisRole.document}:
                if 'ANX' not in (c.axis for c in self):
                    raise InconsistentTargetError(
                        'Mixed container and other roles')
        return AxisRole.mixed

    def _add_container_context(self, container: List[StdCoordinate]):
        start_axis = self[0].axis
        t2l = Axis.tag_2_level()
        if self.role != AxisRole.container:
            return
        if t2l[start_axis] <= t2l[container[0].axis]:
            return
        for k, coordinate in enumerate(container):
            if coordinate.axis == start_axis:
                return
            self.insert(k, coordinate)

    def _add_document(self, document: StdCoordinate):
        if self[0].role in (AxisRole.paragraph, AxisRole.document):
            return
        self.insert(0, document)

    def contextualize(self, container: Target = None,
                      document: StdCoordinate = None):
        """ Modifies itself, by adding context to
        :param container: Target. Container context.
        :param document: Default document.
            In the future, the context can be extended to handle also other
            contexts, e.g.:
                - Legislative domains (e.g. EU)
                - Entire documents (e.g. CRR)
            But for now, this is only relevant for container contexts
        """
        if self[-1].role == AxisRole.phrase:
            raise UnsupportedRole('AxisRole.phrase elements are not supported')
        for k, coordinate in reversed(list(enumerate(self))):
            if coordinate.role == AxisRole.phrase:
                self.pop(k)  # "phrase" coordinates will be ignored.
        if self[0].role == AxisRole.document:
            # If the reference includes the document context, why bother
            return
        if container is not None:
            self._add_container_context(container)
        if document is not None:
            self._add_document(document)

    def _external_href(self):
        result = '/eu/{}/'.format(self[0].collated)
        if len(self) == 1:
            return result
        if self[1].role == AxisRole.container:
            result += 'TOC/#toc-{}'.format(self[1].collated)
            if len(self) > 2:
                result += '-'
        else:
            assert self[1].role == AxisRole.leaf
            result += '{}/'.format(self[1].collated)
            if len(self) > 2:
                result += '#'
        if len(self) == 2:
            return result
        return '{}{}'.format(result, '-'.join(c.collated for c in self[2:]))

    def _insider_href(self):
        main = '-'.join(c.collated for c in self)
        if self[0].role == AxisRole.container:
            return f'#toc-{main}'
        else:
            return f'#{main}'

    def get_href(self, domain):
        if self[0].role == AxisRole.document:
            if self[0].value[:7] in ('http://', 'https:/'):
                assert len(self) == 1
                return self[0].value
            # TODO: consider using url_join here.
            return domain + self._external_href()
        return self._insider_href()

    def join(self, previous: Cycle[Target[StdCoordinate]]):
        backref = self[0]
        if backref.axis == 'TRT':  # Treaties are PNDs ... typically
            backref = StdCoordinate('PND', *backref[1:])
        if backref.role is None:  # case: Anonymous back-reference
            for p in previous:
                sc = None
                for sc in p:
                    if sc.axis == self[1].axis:
                        break
                    backref = sc
                if sc is not None:
                    if sc.axis == self[1].axis:
                        break
            else:  # let's try with this one
                backref = previous[0][0]
        for target in previous:
            if backref.axis in {co.axis for co in target}:
                other = target
                break
        else:
            raise JoiningError('Joining did not work out well.')
        for i, coordinate in enumerate(other):
            self.insert(i, coordinate)
            if coordinate.role != backref.role:
                continue
            if backref.role in (AxisRole.document, AxisRole.leaf):
                break
            if backref.role == AxisRole.container:
                if backref.axis == coordinate.axis:
                    break
        else:
            raise JoiningError('Joining did not work out well.')
        self.pop(i+1)  # remove backref

    @property
    def has_backref(self) -> bool:
        try:
            return self[0].value in Value.backref
        except IndexError:
            return False

    def get_spoken(self, language):
        return ''.join(
            text for text in (c.get_spoken(language) for c in self)
            if text is not None).strip()


class SyntaxNode(NodeMixin, metaclass=ABCMeta):
    level = None

    def __init__(self, parent=None):
        if parent is not None:
            self.parent = parent

    def append(self, node: SyntaxNode):
        assert node.level > self.level
        children = self.children
        if not children:
            node.parent = self
        elif len(children) == 1:
            child = children[0]
            if child.level < node.level:
                child.append(node)
            elif child.level == node.level:
                node.parent = self
            else:
                # TODO: Implement insertion of node
                #  with a level between parent and child.
                raise NestingError('Inconsistent levels')
        else:
            levels = set(c.level for c in children)
            if len(levels) == 1 and levels.pop() == node.level:
                node.parent = self
            else:
                raise RuntimeError('Inconsistent Children levels')


class Coordinate(SyntaxNode):
    group_tag = Group.coordinate.value
    tag_value = '#'

    @property
    def span(self) -> Span:
        return Span(min(self.axis.span.start, self.value.span.start),
                    max(self.axis.span.end, self.value.span.end))

    def __init__(self, axis: ReferenceToken, value: ReferenceToken, parent=None):
        self.axis = axis
        self.value = value
        super().__init__(parent)
        self._level = None

    @lru_cache(maxsize=8)
    def standardized(self, language) -> StdCoordinate:
        result = _standardize(self.axis.tag_value, self.value.tag_value,
                              self.value.text, language)
        if self.value.suffix is not None:
            return StdCoordinate(
                result.axis, result.value + self.value.suffix, result.role)
        return result

    def get_target(self, language, container=None, document=None) -> Target:
        target = Target(c.standardized(language) for c in self.path
                        if c.value.tag_value != 'XTHISX')
        if not target:
            return Target()
        target.contextualize(container=container, document=document)
        return target

    def __repr__(self):
        result = type(self).__name__ + f"(axis={self.axis}, value={self.value})"
        for name in ('axis', 'value'):
            result.replace(f"{name}=None", "")
        return result

    def to_dict(self, text=False) -> dict:
        result = {
            'group_tag': self.group_tag,
            'axis': self.axis.to_dict(text) if self.axis is not None else None,
            'value':
                self.value.to_dict(text) if self.value is not None else None,
        }
        try:
            result['level'] = self.level
        except KeyError:
            result['level'] = None
        return result

    def _infer_level(self) -> int:
        try:
            return Axis.tag_2_level()[self.axis.tag.value]
        except KeyError:
            if self.value.tag.group == Group.named_entity:
                return 10
            else:
                raise

    @property
    def level(self) -> int:
        if type(self._level) is int:
            return self._level
        self._level = self._infer_level()
        return self._level

    @level.setter
    def level(self, value):
        self._level = value

    def __str__(self):
        return str(RenderTree(self))
