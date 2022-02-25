import unittest

from lexref.model import NamedEntity


class TestOnlyTreaties(unittest.TestCase):

    def test(self):
        keys_1 = set(key for key, _ in NamedEntity.key_pattern('EN', only_treaties=False))
        for key in keys_1:
            if key.startswith('3'):
                break
        else:
            raise AssertionError('No normal documents?')
        keys_2 = set(key for key, _ in NamedEntity.key_pattern('EN', only_treaties=True))
        for key in keys_2:
            if key.startswith('3'):
                raise AssertionError('What??')


if __name__ == '__main__':
    unittest.main()
