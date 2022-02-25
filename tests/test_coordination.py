import json
import os
import unittest

from lexref.token_sequences import TokenSequences, TokenSequence
from lexref.model import Group
from unittest.mock import Mock


class TestCoordinate(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
    ts_nest = TokenSequence._nesting

    @classmethod
    def setUpClass(cls):
        TokenSequence._nesting = Mock()
        with open(os.path.join(cls.DATA_PATH, 'tokenized.json'),
                  encoding='utf-8') as f:
            cls.tokenized = json.load(f)

    @classmethod
    def tearDownClass(cls):
        TokenSequence._nesting = cls.ts_nest

    def _test_lang(self, language):
        for pair in self.tokenized[language]:
            text = pair['text']
            ts = TokenSequences(language, text)
            for s in ts:
                self.assertTrue(
                    set(s.groups).issubset(
                        {Group.coordinate.value, Group.connector.value}),
                    json.dumps({
                        'text': text,
                        'sequence': s.to_dict(text)
                    }, indent=2)
                )

    def test_de(self):
        self._test_lang('DE')

    def test_en(self):
        self._test_lang('EN')


if __name__ == '__main__':
    unittest.main()
