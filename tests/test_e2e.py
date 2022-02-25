import json
import os
import unittest
from lxml import etree as et

from lexref.structures import Target, StdCoordinate
from lexref.model import AxisRole
from lexref.reflector import Reflector

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'e2e_1.json')


problematics = {
    'EN': ['Acting in accordance with the procedure laid down in Article 251 '
           'of the Treaty',
           'The Commission shall adopt each year by means of a Regulation a '
           'complete version of the list of substances.'],
    'DE': [],
    'ES': []
}


class TestEnd2End(unittest.TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        with open(DATA_PATH, encoding='utf-8') as f:
            self.data = json.load(f)

    def _test_language(self, language):
        reflector = Reflector(language, 'markup')
        for item in self.data[language]:
            markup = reflector(item['input'])
            self.assertEqual(item['markup'], markup)
        self.assertEqual(problematics[language], reflector.problematics)

    def test_de(self):
        self._test_language('DE')

    def test_de_document_context(self):
        text = "In Titel IV wird folgendes Kapitel eingefügt:"
        reflector = Reflector('DE', 'markup', internet_domain='',
                              document_context='/eu/32012R0648/')
        self.assertEqual(
            'In Titel <a title="Verordnung 648/2012 Titel IV" '
            'href="/eu/32012R0648/TOC/#toc-TIT_IV">IV</a> '
            'wird folgendes Kapitel eingefügt:',
            reflector(text))

    def test_extra_en(self):
        cc = Target([
            StdCoordinate(axis='PRT', value='1', role=AxisRole.container),
            StdCoordinate(axis='TIT', value='I', role=AxisRole.container)])
        reflector = Reflector(
            'EN', 'markup', internet_domain='',
            container_context=cc)
        self.assertEqual(
            'Service referred to in point <a title="Directive 2004/39/EC Annex '
            'I Section B point (1)" href="/eu/32004L0039/ANX_I/#SEC_B-1">(1)</a>'
            ' of Section <a title="Directive 2004/39/EC Annex I '
            'Section B" href="/eu/32004L0039/ANX_I/#SEC_B">B</a> of Annex <a '
            'title="Directive 2004/39/EC Annex I" '
            'href="/eu/32004L0039/ANX_I/">I</a> to Directive '
            '<a title="Directive 2004/39/EC" href="/eu/32004L0039/">2004/39/EC'
            '</a>, which provide.',
            reflector(
                'Service referred to in point (1) of Section B of Annex I to '
                'Directive 2004/39/EC, which provide.'))

    def test_extra_en_2(self):
        cc = Target([
            StdCoordinate(axis='ANX', value=None, role=AxisRole.container)])
        reflector = Reflector(
            'EN', 'markup', internet_domain='',
            container_context=cc)
        text = 'See Annex III, Part A.'
        self.assertEqual(
            'See Annex <a title="Annex III" href="#ANX_III">III</a>, '
            'Part <a title="Annex III Part A" href="#ANX_III-PRT_A">A</a>.',
            reflector(text))

    def test_extra_en_3(self):
        reflector = Reflector('EN', 'markup', internet_domain='',
                              only_treaty_names=True)  # this is the specialty
        text = "Liabilities to another existing UCITS or an investment " \
               "compartment."
        self.assertEqual(text, reflector(text))

    def test_min_role(self):
        reflector = Reflector('EN', 'markup', min_role=AxisRole.leaf)
        text = "reporting requirements related to points (a), (b) and (c) " \
               "and to leverage;"
        self.assertEqual(text, reflector(text))

    def test_memory(self):
        reflector = Reflector('EN', 'markup', internet_domain='')
        e = et.fromstring(
            '<div>'
            '<p>Having regard to the Treaty establishing the European Economic '
            'Community, and other issues</p>'
            '<p>Acting in accordance with the procedure laid down in Article '
            '251 of the Treaty</p>'
            '</div>',
            parser=et.XMLParser())
        self.assertEqual(
            '<div><p>Having regard to the <a title="Treaty establishing the '
            'European Economic Community" href="/eu/TEEC/">'
            'Treaty establishing the European Economic Community</a>, and other '
            'issues</p><p>Acting in accordance with the procedure laid down in '
            'Article <a title="Treaty establishing the European Economic '
            'Community Article 251" href="/eu/TEEC/ART_251/">251</a> of the '
            'Treaty</p></div>',
            et.tostring(reflector(e), encoding='unicode')
        )

    def test_memory_de(self):
        reflector = Reflector('DE', 'markup', internet_domain='')
        e = et.fromstring(
            '<div><p>gestützt auf den Vertrag zur Gründung der Europäischen '
            'Gemeinschaft, insbesondere auf Artikel 61 Buchstabe c und Artikel '
            '67 Absatz 5, zweiter Gedankenstrich,</p><p>auf Vorschlag der '
            'Kommission,</p><p>nach Stellungnahme des Europäischen Wirtschafts- '
            'und Sozialausschusses(1),</p><p>gemäß dem Verfahren des Artikels '
            '251 des Vertrags,</p></div>',
            parser=et.XMLParser())
        self.assertEqual(
            '<div><p>gestützt auf den <a title="EGV" href="/eu/TEEC/">Vertrag '
            'zur Gründung der Europäischen Gemeinschaft</a>, insbesondere auf '
            'Artikel <a title="EGV Art. 61" href="/eu/TEEC/ART_61/">61</a> '
            'Buchstabe <a title="EGV Art. 61 Buchst. c" '
            'href="/eu/TEEC/ART_61/#c">c</a> und Artikel <a title="EGV Art. 67" '
            'href="/eu/TEEC/ART_67/">67</a> Absatz <a title="EGV Art. 67 Abs. 5" '
            'href="/eu/TEEC/ART_67/#5">5</a>, zweiter Gedankenstrich,</p>'
            '<p>auf Vorschlag der Kommission,</p><p>nach Stellungnahme des '
            'Europäischen Wirtschafts- und Sozialausschusses(1),</p><p>gemäß '
            'dem Verfahren des Artikels <a title="EGV Art. 251" '
            'href="/eu/TEEC/ART_251/">251</a> des Vertrags,</p></div>',
            et.tostring(reflector(e), encoding='unicode')
        )

    def test_en(self):
        self._test_language('EN')

    def test_es(self):
        self._test_language('ES')

    def test_mixed_de(self):
        text = "So wird auch in Gesetzen eine wesentliche Beteiligung an einem " \
               "Unternehmen ab dem Überschreiten von unterschiedlichen " \
               "Schwellenwerten angenommen (vgl. § 74 Abs. 2 AO, § 43 WpHG, " \
               "Art. 43 VO (EU) 575/2013)."
        reflector = Reflector('DE', 'markup', internet_domain='', min_role='document')
        self.assertEqual(
            'So wird auch in Gesetzen eine wesentliche Beteiligung an einem '
            'Unternehmen ab dem Überschreiten von unterschiedlichen '
            'Schwellenwerten angenommen (vgl. § 74 Abs. 2 AO, § 43 WpHG, '
            'Art. <a title="Verordnung (EU) 575/2013 Art. 43" '
            'href="/eu/32013R0575/ART_43/">43</a> VO '
            '<a title="Verordnung (EU) 575/2013" href="/eu/32013R0575/">(EU) '
            '575/2013</a>).',
            reflector(text)
        )

    def test_unclose_anchors(self):
        text = 'Article 2(1)(a)'
        reflector = Reflector('EN', 'markup', internet_domain='',
                              min_role='leaf', unclose=True)
        self.assertEqual(
            'Article <a title="Article 2(1)(a)" href="#ART_2-1-a">2(1)(a)</a>',
            reflector(text)
        )

    def test_shortcut(self):
        text = "Artikel 22"
        reflector = Reflector('DE', 'markup',
                              document_context='/eu/52021PC0206',
                              internet_domain='')
        self.assertEqual(
            'Artikel <a title="52021PC0206 Art. 22" '
            'href="/eu/52021PC0206/ART_22/">22</a>',
            reflector(text)
        )


if __name__ == '__main__':
    unittest.main()
