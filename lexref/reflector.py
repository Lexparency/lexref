from typing import Union, Optional, Any, List, Dict

from lxml import etree as et

from lexref.celex_handling import get_doc_type, celexer, CelexHandler
from lexref.model import Axis, AxisRole
from lexref.structures import Target, Cycle, StdCoordinate, \
    _standardize
from lexref.utils import Reference, VirtualMarkup, iter_texts
from lexref.token_sequences import TokenSequences


class Reflector:
    """ Putting it all together """

    MEM_SIZE = 5

    def __init__(self, language: str, mode,
                 container_context=None, document_context=None,
                 min_role=None, internet_domain=None,
                 only_treaty_names=False, unclose=False):
        """
        :param language: EN, DE, ES, ...
        :param mode: The mode steers the type of return value. The following
            values are considered:
            - "annotate" Just provide a list of objects specifying location,
                target, and title of the encountered reference.
            - "markup" Equip the input text with HTML markup.
        :param container_context: Target, or list instance specifying the
            container context. Or None.
        :param document_context: StdCoordinate or dict instance specifying the
            document that is considered per default.
        :param min_role: Minimum role level to be included. All Target
            instances, with ultimate_role.value < min_role.value will be skipped.
        :param internet_domain: https://...
        :param only_treaty_names: If set to true, don't use popular titles of
            Regulations or Directives
        :param unclose: If True, join neighbouring anchors, if one of both is close
            to the other.
        """
        assert mode in ('annotate', 'markup')
        self.language = language
        self.container = Target.create(container_context)
        self.document = self.create_document_context(document_context)
        self.mode = mode
        self.min_role = self.create_role(min_role)
        self.internet_domain = internet_domain
        self.only_treaty_names = only_treaty_names
        self.memory = Cycle(self.MEM_SIZE)
        self.problematics = []
        self.unclose = unclose

    @staticmethod
    def create_role(role) -> AxisRole:
        if role is None:
            return AxisRole.token
        t = type(role)
        if t is AxisRole:
            return role
        if t is str:
            return AxisRole.from_name(role)

    @staticmethod
    def create_document_context(dc) -> Union[Optional[StdCoordinate], Any]:
        if dc is None:
            return
        t = type(dc)
        if t is StdCoordinate:
            return dc
        if t is dict:
            return StdCoordinate(dc['axis'], dc['value'], AxisRole.document)
        if t is str:
            assert dc.startswith('/eu/')
            celex = dc.split('/')[2]
            return StdCoordinate(get_doc_type(celex), celex, AxisRole.document)

    def _get_annotations(self, text: str, remember=False) -> List[Reference]:
        ts = TokenSequences(self.language, text,
                            only_treaties=self.only_treaty_names,
                            recents=self.memory if remember else None)
        result = list(ts.iter_references(
            container=self.container,
            document=self.document,
            min_role=self.min_role,
            internet_domain=self.internet_domain))
        if ts.errors:
            self.problematics.append(text)
        return result

    @staticmethod
    def _markup_string(text: str, annotations: Dict[str, List[Reference]]) -> str:
        return et.tostring(VirtualMarkup.add_all_markups(et.fromstring(
            f'<OUTER>{text}</OUTER>', parser=et.XMLParser()),
            annotations), encoding='unicode')[7:-8]

    def _get_annotations_map(self, inputs, remember=False) -> Dict[str, List[Reference]]:
        t = type(inputs)
        if t is str:
            return {inputs: self._get_annotations(inputs)}
        elif t is list:
            if remember:
                self.memory = Cycle(self.MEM_SIZE)
            return {inp: self._get_annotations(inp, remember) for inp in inputs}
        elif et.iselement(inputs):
            return self._get_annotations_map(
                [text for _, text, __ in iter_texts(inputs)], remember=True)
        else:
            raise ValueError(f'type {t} not supported for reflecting.')

    @staticmethod
    def _unclose(amap: Dict[str, List[Reference]]):
        for refs in amap.values():
            if len(refs) == 0:
                continue
            ultimate = refs[-1]
            uk = len(refs) - 1
            for k, ref in reversed(list(enumerate(refs[:-1]))):
                if ref.join(ultimate):
                    refs.pop(uk)
                ultimate = ref
                uk = k

    def __call__(self, inputs):
        t = type(inputs)
        annotation_map = self._get_annotations_map(inputs)
        if self.unclose:
            self._unclose(annotation_map)
        if self.mode == 'annotate':
            return [{'text': text,
                     'references': [r.to_dict() for r in references]}
                    for text, references in annotation_map.items()]
        else:
            if et.iselement(inputs):
                return VirtualMarkup.add_all_markups(inputs, annotation_map)
            elif t is str:
                return self._markup_string(inputs, annotation_map)
            elif t is list:
                # TODO: use multi-threading
                return [{'raw': text,
                         'markup': self._markup_string(text, annotation_map)}
                        for text, _ in annotation_map.items()]

    @staticmethod
    def reset():
        """ Clear all caches and memories! """
        celexer._inverse = {}  # No memory, no interference
        # noinspection PyProtectedMember
        CelexHandler._fall_back_inversion.cache_clear()
        CelexHandler.convert.cache_clear()
        StdCoordinate.get_spoken.cache_clear()
        _standardize.cache_clear()


def celex_2_id_human(celex, language):
    dt, value = celexer.invert(celex, language)
    t2s = Axis.tag_2_standard(language)
    return '{} {}'.format(t2s[dt], value)
