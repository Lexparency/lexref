import json
import os
import unittest

from lexref.token_sequences import TokenSequences


class TestNesting(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')

    def setUp(self):
        with open(os.path.join(self.DATA_PATH, 'nested.json'),
                  encoding='utf-8') as f:
            self.nested = json.load(f)
        with open(os.path.join(self.DATA_PATH, 'tokenized.json'),
                  encoding='utf-8') as f:
            self.tokenized = json.load(f)

    @staticmethod
    def _sequences_to_dict(tss: TokenSequences, text):
        item = {'input': text, 'ref_groups': []}
        for ts in tss:
            span = ts.span
            item['ref_groups'].append({
                'text': text[span.start:span.end],
                'ref_trees': '\n'.join(str(r) for r in ts.iter_roots())
            })
        return item

    def _test_nesting(self, language):
        for pair in self.nested[language]:
            text = pair['input']
            actual = TokenSequences(language, text)
            expected = pair['ref_groups']
            self.assertEqual(
                len(actual), len(expected),
                json.dumps(self._sequences_to_dict(actual, text),
                           indent=2,
                           ensure_ascii=False))
            for e, a in zip(expected, actual):
                span = a.span
                self.assertEqual(e['text'], text[span.start:span.end])
                self.assertEqual(
                    e['ref_trees'],
                    '\n'.join(str(r) for r in a.iter_roots()))

    def _create_output(self, language):
        output = []
        for pair in self.tokenized[language]:
            text = pair['text']
            output.append(self._sequences_to_dict(
                TokenSequences(language, text),
                text
            ))
            # for group in output[-1]['ref_groups']:
            #     print(group['text'])
            #     print(group['ref_trees'])
        print(json.dumps({language: output}, indent=2, ensure_ascii=False))

    def test_en(self):
        self._test_nesting('EN')

    def test_de(self):
        self._test_nesting('DE')


if __name__ == '__main__':
    unittest.main()
