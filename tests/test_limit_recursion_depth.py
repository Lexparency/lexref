import unittest
from lexref.utils import limit_recursion_depth


def get_cumbersome_identity(limit):
    @limit_recursion_depth(limit)
    def cumbersome_identity(n):
        if n <= 1:
            return n
        return 1 + cumbersome_identity(n - 1)

    return cumbersome_identity


class TestLimitRecursionDepth(unittest.TestCase):

    def test(self):
        ci = get_cumbersome_identity(2)
        self.assertRaises(RecursionError, ci, 3)
        self.assertEqual(2, ci(2))
        for k in range(1, 10):
            ci = get_cumbersome_identity(k)
            self.assertRaises(RecursionError, ci, k + 1)
            self.assertEqual(k, ci(k))
        self.assertRaises(RecursionError, get_cumbersome_identity(0), 0)


if __name__ == '__main__':
    unittest.main()
