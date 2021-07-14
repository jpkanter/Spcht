#!/usr/bin/env python
# coding: utf-8

# Copyright 2021 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of the Solr2Triplestore Tool.
#
# This program is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Solr2Triplestore Tool.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

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

    def test_is_dictkey1(self):
        """tests with one key that is actually there"""
        dict = {1: 42, 2: 67, 3: 99}
        key = 1
        self.assertEqual(True, Spcht.is_dictkey(dict, key))

    def test_is_dictkey2(self):
        """tests with one key that is not there"""
        dict = {1: 42, 2: 67, 3: 99}
        key = 5
        self.assertEqual(False, Spcht.is_dictkey(dict, key))

    def test_is_dictkey3(self):
        """tests with keys that are all there"""
        dict = {1: 42, 2: 67, 3: 99}
        key = [1, 2]
        self.assertEqual(True, Spcht.is_dictkey(dict, key))

    def test_is_dictkey4(self):
        """tests with keys of which some are there"""
        dict = {1: 42, 2: 67, 3: 99}
        key = [1, 5]
        self.assertEqual(False, Spcht.is_dictkey(dict, key))

    def test_is_dictkey5(self):
        """tests with keys of which noone are there"""
        dict = {1: 42, 2: 67, 3: 99}
        key = [5, 7, 9]
        self.assertEqual(False, Spcht.is_dictkey(dict, key))

    def test_list_has_elements1(self):
        self.assertEqual(True, Spcht.list_has_elements([1, 2]))

    def test_list_has_elements2(self):
        self.assertEqual(False, Spcht.list_has_elements([]))

    def test_all_variants1(self):
        listed = [[1]]
        expected = [[1]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants2(self):
        listed = [[1], [2]]
        expected = [[1, 2]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants3(self):
        listed = [[1], [2], [3]]
        expected = [[1, 2, 3]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants4(self):
        listed = [[1, 2]]
        expected = [[1], [2]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants5(self):
        listed = [[1, 2], [3]]
        expected = [[1, 3], [2, 3]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants6(self):
        listed = [[1, 2], [3, 4]]
        expected = [[1, 3], [1, 4], [2, 3], [2, 4]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants7(self):
        listed = [[1, 2], [3], [4]]
        expected = [[1, 3, 4], [2, 3, 4]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_all_variants8(self):
        listed = [[1, 2], [3, 4], [5]]
        expected = [[1, 3, 5], [1, 4, 5], [2, 3, 5], [2, 4, 5]]
        self.assertEqual(expected, Spcht.all_variants(listed))

    def test_match_positions1(self):
        regex = r"\{\}"
        stringchain = "bla {} fasel {}"
        expected = [(4, 6), (13, 15)]
        self.assertEqual(expected, Spcht.match_positions(regex, stringchain))

    def test_match_positions2(self):
        regex = r"\[\]"
        stringchain = "bla {} fasel {}"
        expected = None
        self.assertEqual(expected, Spcht.match_positions(regex, stringchain))

    def test_fill_var1(self):
        exist = 1
        input = 5
        expected = [1, 5]
        self.assertEqual(expected, Spcht.fill_var(exist, input))


    def test_fill_var2(self):
        exist = [1, 2]
        input = 5
        expected = [1, 2, 5]
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var3(self):
        exist = {1: 2, 3: 5}
        input = 5
        expected = [{1: 2, 3: 5}, 5]
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var4(self):
        exist = [1, 2]
        input = [5, 6]
        expected = [1, 2, [5, 6]]
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var5(self):
        exist = None
        input = 5
        expected = 5
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var6(self):
        exist = []
        input = 5
        expected = [5]
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var7(self):
        exist = ""
        input = 5
        expected = 5
        self.assertEqual(expected, Spcht.fill_var(exist, input))

    def test_fill_var8(self):
        exist = None
        input = ""
        expected = ""
        self.assertEqual(expected, Spcht.fill_var(exist, input))

if __name__ == '__main__':
    unittest.main()