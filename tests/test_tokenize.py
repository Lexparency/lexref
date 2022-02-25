import json
import os
import unittest
from unittest.mock import Mock

from lexref.token_sequences import TokenSequences, TokenSequence


class TestTokenizer(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
    to_co = TokenSequence._coordination
    to_nst = TokenSequence._nesting

    def setUp(self):
        TokenSequence._coordination = Mock()
        TokenSequence._nesting = Mock()
        with open(os.path.join(self.DATA_PATH, 'tokenized.json'),
                  encoding='utf-8') as f:
            self.tokenized = json.load(f)

    def tearDown(self):
        TokenSequence._coordination = self.to_co
        TokenSequence._nesting = self.to_nst

    def _test_lang(self, language):
        for pair in self.tokenized[language]:
            text = pair['text']
            t = TokenSequences(language, text)
            self.assertEqual(
                pair['hoods'],
                t.to_dict()['hoods'],
                f"Trouble with >>{text}<<\n" + str(t)
            )

    def test_de(self):
        self._test_lang('DE')

    def test_en(self):
        self._test_lang('EN')


if __name__ == '__main__':
    unittest.main()
