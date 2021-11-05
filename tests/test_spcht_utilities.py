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
import json
import unittest

import SpchtUtility
from SpchtCore import Spcht, SpchtThird, SpchtTriple
from SpchtUtility import list_wrapper, insert_list_into_str, is_dictkey, list_has_elements, all_variants, match_positions, fill_var


class TestFunc(unittest.TestCase):

    def test_listwrapper1(self):
        self.assertEqual(list_wrapper(["OneElementList"]), ["OneElementList"])

    def test_listwrapper2(self):
        self.assertEqual(list_wrapper("OneElement"), ["OneElement"])

    def test_listwrapper3(self):
        self.assertEqual(list_wrapper(["Element1", "Element2"]), ["Element1", "Element2"])

    def test_listwrapper4(self):
        self.assertEqual(list_wrapper(None), [None])

    def test_insert_into1(self):
        """"normal test"""
        inserts = ["one", "two", "three"]
        sentence = "{} entry, {} variants and {} things"
        goal = "one entry, two variants and three things"
        trial = insert_list_into_str(inserts, sentence)
        self.assertEqual(trial, goal)

    def test_insert_into2(self):
        """test with changed placeholder and new regex length"""
        inserts = ["one", "two", "three"]
        sentence = "[--] entry, [--] variants and [--] things"
        goal = "one entry, two variants and three things"
        trial = insert_list_into_str(inserts, sentence, regex_pattern=r'\[--\]', pattern_len=4)
        self.assertEqual(trial, goal)

    def test_insert_into3(self):
        """test with only two inserts"""
        inserts = ["one", "two"]
        sentence = "{} and {}"
        goal = "one and two"
        trial = insert_list_into_str(inserts, sentence)
        self.assertEqual(trial, goal)

    def test_insert_into4(self):
        """"test with more inserts than spaces"""
        inserts = ["one", "two", "three"]
        sentence = "Space1: {}, Space2 {}."
        self.assertRaises(TypeError, insert_list_into_str(inserts, sentence))

    def test_insert_into5(self):
        """test with less inserts than slots"""
        inserts = ["one", "two"]
        sentence = "Space1: {}, Space2 {}, Space3 {}"
        print(insert_list_into_str(inserts, sentence))
        self.assertRaises(TypeError, insert_list_into_str(inserts, sentence))

    def test_is_dictkey1(self):
        """tests with one key that is actually there"""
        dictionary = {1: 42, 2: 67, 3: 99}
        key = 1
        self.assertEqual(True, is_dictkey(dictionary, key))

    def test_is_dictkey2(self):
        """tests with one key that is not there"""
        dictionary = {1: 42, 2: 67, 3: 99}
        key = 5
        self.assertEqual(False, is_dictkey(dictionary, key))

    def test_is_dictkey3(self):
        """tests with keys that are all there"""
        dictionary = {1: 42, 2: 67, 3: 99}
        key = [1, 2]
        self.assertEqual(True, is_dictkey(dictionary, key))

    def test_is_dictkey4(self):
        """tests with keys of which some are there"""
        dictionary = {1: 42, 2: 67, 3: 99}
        key = [1, 5]
        self.assertEqual(False, is_dictkey(dictionary, key))

    def test_is_dictkey5(self):
        """tests with keys of which noone are there"""
        dictionary = {1: 42, 2: 67, 3: 99}
        key = [5, 7, 9]
        self.assertEqual(False, is_dictkey(dictionary, key))

    def test_list_has_elements1(self):
        self.assertEqual(True, list_has_elements([1, 2]))

    def test_list_has_elements2(self):
        self.assertEqual(False, list_has_elements([]))

    def test_all_variants1(self):
        listed = [[1]]
        expected = [[1]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants2(self):
        listed = [[1], [2]]
        expected = [[1, 2]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants3(self):
        listed = [[1], [2], [3]]
        expected = [[1, 2, 3]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants4(self):
        listed = [[1, 2]]
        expected = [[1], [2]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants5(self):
        listed = [[1, 2], [3]]
        expected = [[1, 3], [2, 3]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants6(self):
        listed = [[1, 2], [3, 4]]
        expected = [[1, 3], [1, 4], [2, 3], [2, 4]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants7(self):
        listed = [[1, 2], [3], [4]]
        expected = [[1, 3, 4], [2, 3, 4]]
        self.assertEqual(expected, all_variants(listed))

    def test_all_variants8(self):
        listed = [[1, 2], [3, 4], [5]]
        expected = [[1, 3, 5], [1, 4, 5], [2, 3, 5], [2, 4, 5]]
        self.assertEqual(expected, all_variants(listed))

    def test_match_positions1(self):
        regex = r"\{\}"
        stringchain = "bla {} fasel {}"
        expected = [(4, 6), (13, 15)]
        self.assertEqual(expected, match_positions(regex, stringchain))

    def test_match_positions2(self):
        regex = r"\[\]"
        stringchain = "bla {} fasel {}"
        expected = []
        self.assertEqual(expected, match_positions(regex, stringchain))

    def test_fill_var1(self):
        exist = 1
        input = 5
        expected = [1, 5]
        self.assertEqual(expected, fill_var(exist, input))


    def test_fill_var2(self):
        exist = [1, 2]
        input = 5
        expected = [1, 2, 5]
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var3(self):
        exist = {1: 2, 3: 5}
        input = 5
        expected = [{1: 2, 3: 5}, 5]
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var4(self):
        exist = [1, 2]
        input = [5, 6]
        expected = [1, 2, [5, 6]]
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var5(self):
        exist = None
        input = 5
        expected = 5
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var6(self):
        exist = []
        input = 5
        expected = [5]
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var7(self):
        exist = ""
        input = 5
        expected = 5
        self.assertEqual(expected, fill_var(exist, input))

    def test_fill_var8(self):
        exist = None
        input = ""
        expected = ""
        self.assertEqual(expected, fill_var(exist, input))

    def test_extract_dictmarc(self):
        with open("thetestset.json", "r") as json_file:
            thetestset = json.load(json_file)
        fake_node = {"source": "marc", "field": "951:a"}
        expected = ["MV", "XA-DE", "XA-PL"]
        empty_spcht = Spcht()
        empty_spcht._m21_dict = SpchtUtility.marc2list(thetestset[0]['fullrecord'])
        with self.subTest("Extract dictmarc list: dictionary"):
            expected = ["MV", "XA-DE", "XA-PL"]
            computed = [x.content for x in empty_spcht.extract_dictmarc_value(fake_node)]
            self.assertEqual(expected, computed)
        with self.subTest("Extract dictmarc dictionary: list"):
            expected = ["(DE-627)1270642103", "(DE-625)rvk/96225:", "(DE-576)200642103"]
            fake_node['field'] = "936:0"
            computed = [x.content for x in empty_spcht.extract_dictmarc_value(fake_node)]
            self.assertEqual(expected, computed)

    def test_spcht_triple_serialize(self):
        one_uri = SpchtThird("https://schema.org/adress", uri=True)
        snd_uri = SpchtThird("https://schema.org/cat", uri=True)
        one_literal = SpchtThird("Miau", tag="xsd:integer")
        snd_literal = SpchtThird("english", language="en")
        triple_1 = SpchtTriple(one_uri, snd_uri, snd_literal)
        triple_2 = SpchtTriple(one_uri, snd_uri, one_literal)
        expected = """@prefix ns1: <https://schema.org/> .

ns1:adress ns1:cat "Miau",
        "english"@en .

"""
        computed = SpchtUtility.process2RDF([triple_1, triple_2])
        self.assertEqual(expected, computed)


if __name__ == '__main__':
    unittest.main()