import unittest

from temperature import at_threshold


class FanTests(unittest.TestCase):
    def test_fan_at_70(self):
        self.assertTrue(at_threshold(70))
