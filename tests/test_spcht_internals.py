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
    "perch": ["12", "9"]
}
IF_NODE = {
            "field": "frogfish",
            "source": "dict",
            "if_field": "salmon",
            "if_condition": ">",
            "if_value": 10
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


if __name__ == '__main__':
    unittest.main()

