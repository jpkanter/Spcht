import unittest

from SpchtDescriptorFormat import Spcht, SpchtIterator


class TestFunc(unittest.TestCase):
    bird = Spcht()

    def test_listwrapper1(self):
        self.assertEqual(self.bird.list_wrapper(["OneElementList"]), ["OneElementList"])

    def test_listwrapper2(self):
        self.assertEqual( self.bird.list_wrapper("OneElement"), ["OneElement"])

    def test_listwrapper3(self):
        self.assertEqual(self.bird.list_wrapper(["Element1", "Element2"]), ["Element1", "Element2"])

    def test_listwrapper4(self):
        self.assertEqual(self.bird.list_wrapper(None), [None])



if __name__ == '__main__':
    unittest.main()