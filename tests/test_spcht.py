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

    def test_insert_into1(self):
        """"normal test"""
        inserts = ["one", "two", "three"]
        sentence = "{} entry, {} variants and {} things"
        goal = "one entry, two variants and three things"
        trial = Spcht.insert_list_into_str(inserts, sentence)
        self.assertEqual(trial, goal)

    def test_insert_into2(self):
        """test with changed placeholder and new regex length"""
        inserts = ["one", "two", "three"]
        sentence = "[--] entry, [--] variants and [--] things"
        goal = "one entry, two variants and three things"
        trial = Spcht.insert_list_into_str(inserts, sentence, regex_pattern=r'\[--\]', pattern_len=4)
        self.assertEqual(trial, goal)

    def test_insert_into3(self):
        """test with only two inserts"""
        inserts = ["one", "two"]
        sentence = "{} and {}"
        goal = "one and two"
        trial = Spcht.insert_list_into_str(inserts, sentence)
        self.assertEqual(trial, goal)

    def test_insert_into4(self):
        """"test with more inserts than spaces"""
        inserts = ["one", "two", "three"]
        sentence = "Space1: {}, Space2 {}."
        self.assertRaises(TypeError, Spcht.insert_list_into_str(inserts, sentence))

    def test_insert_into5(self):
        """test with less inserts than slots"""
        inserts = ["one", "two"]
        sentence = "Space1: {}, Space2 {}, Space3 {}"
        print(Spcht.insert_list_into_str(inserts, sentence))
        self.assertRaises(TypeError, Spcht.insert_list_into_str(inserts, sentence))

if __name__ == '__main__':
    unittest.main()