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

"""
tests internal functions of the spcht descriptor format
"""

import unittest
import copy
from SpchtDescriptorFormat import Spcht
import SpchtUtility

import logging
import os
logging.basicConfig(filename=os.devnull)  # hides logging that occurs when testing for exceptions


TEST_DATA = {
    "salmon": 5,
    "perch": ["12", "9"],
    "trout": "ice water danger xfire air fire hairs flair",
    "bowfin": ["air hair", "lair, air, fair", "stairs, fair and air"],
    "tench": 12,
    "sturgeon": [4, 9, 12],
    "cutthroat": "de",
    "lamprey": ["en", "de", "DE"],
    "catfish": ["air", "hair", "lair", "stairs", "fair", "tear"],
    "goldfish": ["001", "002", "003"],
    "silverfish": ["Yellow", "Blue", "Red"],
    "foulfish": ["Yellow", "Purple"],
    "bronzefish": "001",
    "copperfish": "Pink"
}

IF_NODE = {
            "field": "frogfish",
            "source": "dict",
            "if_field": "salmon",
            "if_condition": ">",
            "if_value": 10
        }

JOINED_NODE = {
            "field": "copperfish",
            "predicate": "thousand",
            "joined_field": "bronzefish",
            "joined_map": {
                "001": "nullnullone",
                "002": "twonullnull",
                "003": "nullthreenull"
            },
            "source": "dict"
        }


class TestSpchtInternal(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpchtInternal, self).__init__(*args, **kwargs)
        self.crow = Spcht("./featuretest.spcht.json")

    def test_preproccesing_single(self):
        node = {
            "match": "^(SE-251)"
        }
        with self.subTest("preprocessing_match"):
            value = "SE-251"
            self.assertEqual([value], Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_match_additional"):
            value = "SE-251moretext"
            self.assertEqual([value], Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_empty_match"):
            value = "preSE-251"
            self.assertEqual([], Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_typerror"):
            value = Spcht()
            with self.assertRaises(TypeError):
                Spcht._node_preprocessing(value, node)
        with self.subTest("preprocessing_prefix"):
            node['there_match'] = "(PT-120)"
            value = "aaaPT-120bbb"
            self.assertEqual([value], Spcht._node_preprocessing(value, node, "there_"))

    def test_preprocessing_multi(self):
        node = {
            "match": "(ente)"
        }
        with self.subTest("preprocessing_multi_match"):
            value = ["ganz", "ente", "großente", "Elefant", "studenten"]
            expected = ["ente", "großente", "studenten"]
            self.assertEqual(expected, Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_multi_no_match"):
            value = ["four", "seven", "thousand"]
            self.assertEqual([], Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_multi_multi_typeerror"):
            value = [["list"], "ente", {0: 25}, "ganz"]
            with self.assertRaises(TypeError):
                Spcht._node_preprocessing(value, node)

    def test_mapping(self):
        node = {
                12: "dutzend"
            }
        value = TEST_DATA['tench']

        with self.subTest("mapping: normal"):
            expected = ["dutzend"]
            self.assertEqual(expected, self.crow._node_mapping(value, node))
        with self.subTest("mapping: empty"):
            expected = []
            self.assertEqual(expected, self.crow._node_mapping(value, {}))

    def test_mapping_multi(self):
        node = {
                4: "quartet",
                9: "lives",
                12: "dutzend"
            }
        value = TEST_DATA['sturgeon']

        with self.subTest("mapping_multi: normal"):
            expected = ["quartet", "lives", "dutzend"]
            self.assertEqual(expected, self.crow._node_mapping(value, node))
        with self.subTest("mapping_multi: empty"):
            expected = []
            self.assertEqual(expected, self.crow._node_mapping(value, {}))

    def test_mapping_string(self):
        node = {
            "DE": "big de",
            "de": "small de",
            "De": "inbetween"
        }
        value = TEST_DATA['cutthroat']
        with self.subTest("mapping_string: normal"):
            expected = ["small de"]
            self.assertEqual(expected, self.crow._node_mapping(value, node))
        with self.subTest("mapping_string: case-insensitive"):
            expected = ['inbetween']  # case case-insensitivity overwrites keys and 'inbetween' is the last
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$casesens': False}))

    def test_mapping_regex(self):
        node = {
            "^(water)": "air",
            "(air)$": "fire"
        }
        value = TEST_DATA['catfish']
        with self.subTest("mapping_regex: normal"):
            expected = ['fire', 'fire', 'fire', 'fire']
            # mapping replaces the entire thing and not just a part, this basically just checks how many instances were replaced
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True}))
        with self.subTest("mapping_regex: inherit"):
            expected = ['fire', 'fire', 'fire', 'stairs', 'fire', 'tear']
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True, '$inherit': True}))
        with self.subTest("mapping_regex: default"):
            del node['(air)$']
            default = "this_is_defaul t"
            expected = [default]
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True, '$default': default}))

    def test_postprocessing_single_cut_replace(self):
        node = {
            "cut": "(air)\\b",
            "replace": "xXx"
        }
        value = "ice water danger xfire air fire hairs flair"
        expected = ["ice water danger xfire xXx fire hairs flxXx"]
        self.assertEqual(expected, self.crow._node_postprocessing(value, node))

    def test_postprocessing_multi_cut_replace(self):
        node = {
            "cut": "(air)\\b",
            "replace": "xXx"
        }
        value = ["air hair", "lair, air, fair", "stairs, fair and air"]
        expected = ["xXx hxXx", "lxXx, xXx, fxXx", "stairs, fxXx and xXx"]
        self.assertEqual(expected, self.crow._node_postprocessing(value, node))

    def test_postprocessing_append(self):
        node = {"append": " :IC-1211"}
        with self.subTest("Postprocessing: append -> one value"):
            value = "some text"
            expected = [value + node['append']]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: append -> one value & prefix"):
            value = "some text"
            node['elephant_append'] = copy.copy(node['append'])
            expected = [value + node['append']]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "elephant_"))
        with self.subTest("Postprocessing: append -> multi value"):
            value = ["one text", "two text", "twenty text"]
            expected = [value[0]+node['append'], value[1]+node['append'], value[2]+node['append']]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: append -> multi value & prefix"):
            value = ["one text", "two text", "twenty text"]
            node['dolphin_append'] = copy.copy(node['append'])
            expected = [value[0]+node['append'], value[1]+node['append'], value[2]+node['append']]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "dolphin_"))

    def test_postprocessing_prepend(self):
        node = {"prepend": "AS-400: "}
        with self.subTest("Postprocessing: prepend -> one value"):
            value = "some text"
            expected = [node['prepend'] + value]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: prepend -> one value & prefix"):
            value = "some different text"
            expected = [node['prepend'] + value]  # such things make you wonder why you are even testing for it
            node['macaw_prepend'] = copy.copy(node['prepend'])
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "macaw_"))
        with self.subTest("Postprocessing: prepend -> multi value"):
            value = ["one text", "two text", "twenty text"]
            expected = [node['prepend'] + value[0], node['prepend'] + value[1], node['prepend'] + value[2]]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: prepend -> multi value"):
            value = ["one text.", "two text.", "twenty text."]
            expected = [node['prepend'] + value[0], node['prepend'] + value[1], node['prepend'] + value[2]]
            node['canine_prepend'] = copy.copy(node['prepend'])
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, 'canine_'))

    def test_if(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)

        node = copy.copy(IF_NODE)

        with self.subTest("if_false"):
            self.assertFalse(self.crow._handle_if(node))
        with self.subTest("if_true"):
            node['if_value'] = 3
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_equal"):
            node['if_value'] = 5
            node['if_condition'] = "eq"
            self.assertTrue(self.crow._handle_if(node))

    def test_if_no_comparator(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(IF_NODE)
        node['if_field'] = "flounder"

        with self.subTest("if_no_normal"):
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_no_uneqal"):
            node['if_condition'] = "!="
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_no_smaller than"):
            node['if_condition'] = "<"
            self.assertFalse(self.crow._handle_if(node))

    def test_if_exi(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)

        node = copy.copy(IF_NODE)
        node['if_condition'] = "exi"

        with self.subTest("if_exi true existence"):
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_exi false existence"):
            node['if_field'] = "hibutt"
            self.assertFalse(self.crow._handle_if(node))

    def test_if_multi_comparator(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)

        node = copy.copy(IF_NODE)
        node['if_value'] = [5, "sechs", "5"]

        with self.subTest("if_multi_comp normal"):
            with self.assertRaises(TypeError):
                self.crow._handle_if(node)
        with self.subTest("if_multi_comp equal"):
            node['if_condition'] = "eq"
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_multi_comp no equal"):
            node['if_value'] = ["7", "sechs", 12]
            self.assertFalse(self.crow._handle_if(node))

    def test_if_multi_values(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)

        node = copy.copy(IF_NODE)
        node['if_field'] = "perch"

        with self.subTest("if_multi_value normal"):
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_multi_value above"):
            node['if_value'] = "13"
            self.assertFalse(self.crow._handle_if(node))
        with self.subTest("if_multi_value  below"):
            node['if_value'] = "7"
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_multi_value inside"):
            self.crow._raw_dict["salmon"] = ["9", "12"]
            node['if_value'] = "10"
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_multi_value equal"):
            node['if_value'] = "9"
            self.assertTrue(self.crow._handle_if(node))

    def test_joined_map(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(JOINED_NODE)
        node['field'] = "silverfish"
        node['joined_field'] = "goldfish"

        expected = [('nullnullone', 'Yellow'), ('twonullnull', 'Blue'), ('nullthreenull', 'Red')]
        self.assertEqual(self.crow._joined_map(node), expected)

    def test_joined_map_single(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(JOINED_NODE)
        node['field'] = "copperfish"
        node['joined_field'] = "bronzefish"

        expected = [('nullnullone', 'Pink')]
        self.assertEqual(self.crow._joined_map(node), expected)

    def test_joined_map_singlepred_to_multi_object(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(JOINED_NODE)
        node['field'] = "silverfish"
        node['joined_field'] = "bronzefish"
        expected = [('nullnullone', 'Yellow'), ('nullnullone', 'Blue'), ('nullnullone', 'Red')]
        self.assertEqual(self.crow._joined_map(node), expected)


if __name__ == '__main__':
    unittest.main()

