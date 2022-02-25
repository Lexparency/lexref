from __future__ import annotations
import re
from lxml import etree as et
from functools import wraps, partial
from collections import namedtuple
from typing import Dict, List, Callable, Tuple, Iterable


class Span(namedtuple('S', ['start', 'end'])):

    def to_dict(self):
        return dict(self._asdict())

    @property
    def length(self):
        return self.end - self.start


class Reference:

    __slots__ = ['span', 'href', 'title']

    def __init__(self, span, href, title):
        self.span = span
        self.href = href
        self.title = title

    def attrib_dict(self):
        return {'title': self.title, 'href': self.href}

    def to_dict(self):
        result = {s: getattr(self, s) for s in self.__slots__}
        # noinspection PyUnresolvedReferences
        result['span'] = result['span'].to_dict()
        return result

    def join(self, other: Reference):
        """ Joins two references, if one of the URLs is a sub-element of the other
        """
        if not (self.href.startswith(other.href) or other.href.startswith(self.href)):
            return False

        def _ref_join(this, that):
            if that.href.startswith(this.href):
                this.href = that.href
                this.title = that.title

        if other.span.start == self.span.end:
            self.span = Span(self.span.start, other.span.end)
            _ref_join(self, other)
            return True
        elif self.span.start == other.span.end:
            self.span = Span(other.span.start, self.span.end)
            _ref_join(self, other)
            return True
        return False


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class MetaPatternHandler(dict, metaclass=Singleton):
    _base: Dict[str, str] = {}
    # TODO: actually, it is not necessary, that the mapping is imposed from
    #  outside. It is sufficient to provide names. The mapped characters are
    #  arbitrary anyway.

    def __hash__(self):
        """ It's a singleton, so it can be hashed! """
        return id(self)

    @property
    def mapping(self) -> Dict[str, str]:
        return {}

    def __init__(self):
        super().__init__()
        for key, pattern in self._base.items():
            for name, value in self.mapping.items():
                pattern = re.sub(rf'\b{name}\b', value, pattern)
            self[key] = re.compile(pattern.replace(':', ''), flags=re.U)

    def finditer(self, key: str, text: str, reverse=True):

        def direction(iterable):
            if reverse:
                return reversed(list(iterable))
            return iterable

        for m in direction(self[key].finditer(text)):
            yield m.span()[0], m


def repeat_until_true(limit=16):
    def rut(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            for _ in range(limit):
                if f(*args, **kwargs):
                    return True
            return False
        return wrapped
    return rut


def iter_texts(element: et.ElementBase) -> Iterable[Tuple[str, str, et.ElementBase]]:
    for descendant in [element] + element.xpath('.//*'):
        for attrib_name in ['text', 'tail']:
            if getattr(descendant, attrib_name) is None:
                continue
            text = getattr(descendant, attrib_name)
            yield attrib_name, text, descendant


class SupMarker:

    def __init__(self, basis, tag, text, tail, attrib):
        self.basis = basis
        self.tag = tag
        self.text_span = text
        self.tail_span = tail
        self.attrib = attrib

    @property
    def text(self):
        return self.basis.string[self.text_span.start:self.text_span.end]

    @property
    def tail(self):
        return self.basis.string[self.tail_span.start:self.tail_span.end]


class VirtualMarkup(list):

    def __init__(self, base_string):
        super().__init__()
        self.string = base_string
        self.text_span = Span(0, len(self.string))
        self.len = len(self.string)
        self.SupMarker = partial(SupMarker, self)

    @property
    def text(self):
        return self.string[self.text_span.start:self.text_span.end]

    def attach(self, span, tag, attrib=None):
        if span.end > self.len:
            raise IndexError
        if len(self) == 0:
            self.text_span = Span(0, span.start)
        else:
            pre = self[-1]
            pre.tail_span = Span(pre.tail_span.start, span.start)
        self.append(self.SupMarker(tag, span, Span(span.end, self.len), attrib))

    @classmethod
    def add_markups(
            cls, attrib_name: str, before_text: str, descendant: et.ElementBase,
            references: List[Reference],
            get_attribs: Callable[[Reference], Dict] = Reference.attrib_dict,
            tag='a'):
        """
        :param attrib_name: "text" or "tail"
        :param before_text: content of the attrib <attrib_name> cleansed by
            superfluous blanks
        :param descendant: et.ElementBase, element whose text or tail is being
            processed.
        :param references: list of References
        :param get_attribs: function to return an attribute dictionary for
            given input from references
        :param tag: tag of the elements to be created
        """
        if len(references) == 0 \
                or (attrib_name == 'text' and descendant.tag == tag):  # no nested anchors.
            return
        self = cls(before_text)
        for ref in references:
            self.attach(ref.span, tag, attrib=get_attribs(ref))
        setattr(descendant, attrib_name, self.text)
        if attrib_name == 'tail':
            container = descendant.getparent()
            start_index = container.index(descendant) + 1
        else:
            container = descendant
            start_index = 0
        for k, ref in enumerate(self):
            container.insert(start_index + k,
                             et.Element(tag, attrib=ref.attrib))
            container[start_index + k].text = ref.text
            container[start_index + k].tail = ref.tail

    @classmethod
    def add_all_markups(cls, element: et.ElementBase,
                        annotations_: Dict[str, List[Reference]],
                        **kwargs) -> et.ElementBase:
        for attrib_name, text, descendant in iter_texts(element):
            cls.add_markups(
                attrib_name, text, descendant, annotations_[text], **kwargs)
        return element


def limit_recursion_depth(limit: int):
    """ Decorator factory to limit a function's recursion depth. """

    def track_recursion_depth(f):
        f.recursion_depth = 0

        @wraps(f)
        def wrapped(*args, **kwargs):
            f.recursion_depth += 1
            if f.recursion_depth > limit:
                depth = f.recursion_depth
                f.recursion_depth = 0
                raise RecursionError(
                    f"Maximal recursion depth of function {f.__name__} "
                    f"reached: depth={depth}, limit={limit}.")
            try:
                result = f(*args, **kwargs)
            finally:
                if f.recursion_depth > 0:
                    # otherwise fails for, e.g. Document 32020R0411
                    f.recursion_depth -= 1
            return result
        return wrapped
    return track_recursion_depth


class CacheWrapper:
    """ Helper class to make sure cached methods are not called before preparation """

    def __init__(self, cached_callable):
        self._source = cached_callable
        self._d = None

    def _set_cache(self):
        if self._d is None:
            self._d = self._source()

    def __getitem__(self, item):
        self._set_cache()
        return self._d[item]

    def get(self, *args, **kwargs):
        self._set_cache()
        return self._d.get(*args, **kwargs)
