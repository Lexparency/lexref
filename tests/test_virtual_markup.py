import unittest
from collections import namedtuple

from lxml import etree as et

from lexref.utils import Reference, VirtualMarkup, Span


class TestVirtualMarkup(unittest.TestCase):
    text = "Instrumente wurden von der Kommission gemäß " \
            "Artikel 107 AEUV als mit dem Binnenmarkt " \
            "vereinbar angesehen."
    out_text = '<div>{}Instrumente wurden von der Kommission gemäß ' \
               '<a title="Artikel 107 halt" href="/eu/AEUV/ART_107">' \
               'Artikel 107 AEUV</a> als mit dem Binnenmarkt vereinbar ' \
               '<a title="Ansehen means ansehen" href="http://ansehen.com">' \
               'angesehen</a>.</div>'

    def setUp(self) -> None:
        self.content1 = et.Element('div')
        self.content1.text = self.text
        self.references = [Reference(Span(44, 60),
                                     '/eu/AEUV/ART_107',
                                     'Artikel 107 halt'),
                           Reference(Span(95, 104),
                                     'http://ansehen.com',
                                     'Ansehen means ansehen')]
        self.content2 = et.SubElement(et.Element('div'), 'br')
        self.content2.tail = self.text

    def test(self):
        before_text = et.tostring(self.content1, encoding='unicode')
        VirtualMarkup.add_markups('text', self.text,
                                  self.content1, [])
        self.assertEqual(
            before_text,
            et.tostring(self.content1, encoding='unicode'))
        VirtualMarkup.add_markups('text', self.text,
                                  self.content1, self.references)
        self.assertEqual(
            self.out_text.format(''),
            et.tostring(self.content1, encoding='unicode'))
        VirtualMarkup.add_markups('tail', self.text,
                                  self.content2, self.references)
        self.assertEqual(
            self.out_text.format('<br/>'),
            et.tostring(self.content2.getparent(), encoding='unicode'))

    def test_raise(self):
        r = self.references[0]
        self.assertRaises(
            IndexError,
            lambda: VirtualMarkup.add_markups(
                'text', self.text, self.content1,
                [Reference(Span(r.span.start, 500), 'dummy',
                           'Fails anyway')])
        )


if __name__ == '__main__':
    unittest.main()
