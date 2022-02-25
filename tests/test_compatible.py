import unittest

from lexref.model import Value


class TestCompatible(unittest.TestCase):

    def test(self):
        self.assertTrue(Value.compatible('AMBRA', 'AMBRA'))
        self.assertFalse(Value.compatible('AMBRA_B', 'AMBRA_BB'))
        self.assertTrue(Value.compatible('AMBRA_B', 'AL_B'))
        self.assertTrue(Value.compatible('AL_B', 'AMBRA_B'))
        self.assertFalse(Value.compatible('AL_B', 'ROM_B'))
        self.assertFalse(Value.compatible('AL_B', 'ROM'))
        self.assertFalse(Value.compatible('ROM', 'AL_B'))


if __name__ == '__main__':
    unittest.main()
