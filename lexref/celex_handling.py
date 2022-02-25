from datetime import datetime
from functools import partial, lru_cache

from lexref.utils import limit_recursion_depth

MAX_YEAR = datetime.now().year
MIN_YEAR = 1944


def _year_test(n):
    """ Tests whether it is plausible to assume that n is a date's year """
    return MAX_YEAR >= n >= MIN_YEAR


def _build_celex(year, number, pre, inter):
    if year < 100:
        year += 1900
    if _year_test(number) and not _year_test(year):
        return ''.join([pre, str(number).zfill(4), inter, str(year)])
    return ''.join([pre, str(year), inter, str(number).zfill(4)])


@limit_recursion_depth(1)
def _celex_getter_reg(ordinate):
    try:
        number, year = [int(n) for n in ordinate.split()[-1].split('/')]
    except ValueError:
        return _celex_getter_direc('R', ordinate)
    try:
        document_sub_domains = [
            dd.strip().lower()
            for dd in ordinate.split('(')[1].split(')')[0].split(',')]
    except IndexError:
        pass
    else:
        if document_sub_domains[0] in ('eu', 'ue'):
            if number >= 2015:
                year, number = number, year
    pre, inter = '3', 'R'
    return _build_celex(year, number, pre, inter)


def _celex_getter_direc(inter, ordinate):
    try:
        year, number = [int(n) for n in ordinate.split()[-1].split('/')[:2]]
    except ValueError:
        # Somtimes they use Directive (EU) .../...
        celex = _celex_getter_reg(ordinate)
        year = int(celex[1:5])
        number = int(celex[6:10])
    pre, inter = '3', inter
    return _build_celex(year, number, pre, inter)


INTER_2_DOC_TYPE = {
    'R': 'REG',
    'D': 'DEC',
    'L': 'DIR',
    'F': 'FDC',
}


def get_doc_type(celex: str):
    try:
        return INTER_2_DOC_TYPE[celex[5]]
    except (KeyError, IndexError):
        return 'DOC'


class CelexHandler:

    cases = {
        'REG': _celex_getter_reg,
        'DEC': partial(_celex_getter_direc, 'D'),
        'DIR': partial(_celex_getter_direc, 'L'),
        'FDC': partial(_celex_getter_direc, 'F')
    }

    def __init__(self):
        self._inverse = {}

    @lru_cache()
    def convert(self, axis_tag, value, language):
        celex = self.cases[axis_tag](value)
        self._inverse[(celex, language)] = (axis_tag, value)
        return celex

    @staticmethod
    @lru_cache()
    def _fall_back_inversion(celex):
        inter = celex[5]
        number = str(int(celex[6:10]))
        year = celex[1:5]
        doc_type = INTER_2_DOC_TYPE[inter]
        if inter in 'R':
            return doc_type, '{}/{}'.format(number, year)
        else:
            return doc_type, '{}/{}'.format(year, number)

    def invert(self, celex, language):
        try:
            return self._inverse[(celex, language)]
        except KeyError:
            return self._fall_back_inversion(celex)


celexer = CelexHandler()
