import unittest

from lexref.utils import repeat_until_true


class Dummy:
    def __init__(self, threshold):
        self.threshold = threshold
        self.count = 0

    def __call__(self):
        self.count += 1
        if self.count == self.threshold:
            return True
        return False


class TestRepeatUntilTrue(unittest.TestCase):

    def test_1(self):
        bare = Dummy(4)
        decorated = repeat_until_true()(bare)
        self.assertTrue(decorated())
        self.assertEqual(bare.count, 4)

    def test_2(self):
        bare = Dummy(20)
        decorated = repeat_until_true()(bare)
        self.assertFalse(decorated())
        self.assertEqual(bare.count, 16)


if __name__ == '__main__':
    unittest.main()
