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
import sys
import unittest
import copy
from Spcht.Core.SpchtCore import Spcht, SpchtThird, SpchtTriple
import Spcht.Core.SpchtUtility as SpchtUtility

import logging
import os
logging.basicConfig(filename=os.devnull)  # hides logging that occurs when testing for exceptions
#logging.basicConfig(level=logging.DEBUG)


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
    "copperfish": "Pink",
    "uboot": [
        {"uran": "u-235"},
        {"uran": "u-238"}
    ],
    "spaceship": [
        {
            "ufo": [
                {"earth": "round"},
                {"mars": "square"}
            ]
        },
        {
            "ufo": [
                {"earth": "imperial"},
                {"mars": "mechanicum"}
            ]
        }
    ]
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
        self.crow = Spcht("./featuretest.spcht.json", schema_path="./../SpchtSchema.json")

    def test_preproccesing_single(self):
        node = {
            "match": "^(SE-251)"
        }
        with self.subTest("preprocessing_match"):
            value = [SpchtThird("SE-251")]
            self.assertEqual(value, Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_match_additional"):
            value = [SpchtThird("SE-251moretext")]
            self.assertEqual(value, Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_empty_match"):
            value = [SpchtThird("preSE-251")]
            self.assertEqual([], Spcht._node_preprocessing(value, node))
        with self.subTest("preprocessing_typerror"):
            value = Spcht()
            with self.assertRaises(TypeError):
                Spcht._node_preprocessing(value, node)
        with self.subTest("preprocessing_prefix"):
            node['there_match'] = "(PT-120)"
            value = [SpchtThird("aaaPT-120bbb")]
            self.assertEqual(value, Spcht._node_preprocessing(value, node, "there_"))

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
        value = [SpchtThird(TEST_DATA['tench'])]

        with self.subTest("mapping: normal"):
            expected = [SpchtThird("dutzend")]
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
        self.crow._raw_dict = TEST_DATA
        value = self.crow.extract_dictmarc_value({"field": "sturgeon", "source": "dict"})

        with self.subTest("mapping_multi: normal"):
            expected = [SpchtThird("quartet"), SpchtThird("lives"), SpchtThird("dutzend")]
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
        self.crow._raw_dict = TEST_DATA
        value = self.crow.extract_dictmarc_value({"field": "cutthroat", "source": "dict"})
        with self.subTest("mapping_string: normal"):
            expected = [SpchtThird("small de")]
            self.assertEqual(expected, self.crow._node_mapping(value, node))
        with self.subTest("mapping_string: case-insensitive"):
            expected = [SpchtThird('inbetween')]  # case case-insensitivity overwrites keys and 'inbetween' is the last
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$casesens': False}))

    def test_mapping_regex(self):
        node = {
            "field": "catfish",
            "source": "dict",
            "^(water)": "air",
            "(air)$": "fire"
        }
        self.crow._raw_dict = copy.copy(TEST_DATA)
        value = self.crow.extract_dictmarc_value(node)
        with self.subTest("mapping_regex: normal"):
            expected = [SpchtThird('fire'), SpchtThird('fire'), SpchtThird('fire'), SpchtThird('fire')]
            # mapping replaces the entire thing and not just a part, this basically just checks how many instances were replaced
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True}))
        with self.subTest("mapping_regex: inherit"):
            expected = [SpchtThird('fire'), SpchtThird('fire'), SpchtThird('fire'), SpchtThird('stairs'), SpchtThird('fire'), SpchtThird('tear')]
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True, '$inherit': True}))
        with self.subTest("mapping_regex: default"):
            del node['(air)$']
            default = "this_is_defaul t"
            expected = [SpchtThird(default)]
            self.assertEqual(expected, self.crow._node_mapping(value, node, {'$regex': True, '$default': default}))

    def test_postprocessing_single_cut_replace(self):
        node = {
            "cut": "(air)\\b",
            "replace": "xXx"
        }
        value = [SpchtThird("ice water danger xfire air fire hairs flair")]
        expected = [SpchtThird("ice water danger xfire xXx fire hairs flxXx")]
        self.assertEqual(expected, self.crow._node_postprocessing(value, node))

    def test_postprocessing_multi_cut_replace(self):
        node = {
            "cut": "(air)\\b",
            "replace": "xXx"
        }
        value = [SpchtThird("air hair"), SpchtThird("lair, air, fair"), SpchtThird("stairs, fair and air")]
        expected = [SpchtThird("xXx hxXx"), SpchtThird("lxXx, xXx, fxXx"), SpchtThird("stairs, fxXx and xXx")]
        self.assertEqual(expected, self.crow._node_postprocessing(value, node))

    def test_postprocessing_append(self):
        node = {"append": " :IC-1211"}
        with self.subTest("Postprocessing: append -> one value"):
            value = [SpchtThird("some text")]
            expected = [SpchtThird("some text :IC-1211")]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: append -> one value & prefix"):
            value = [SpchtThird("some text")]
            node['elephant_append'] = copy.copy(node['append'])
            expected = [SpchtThird("some text :IC-1211")]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "elephant_"))
        with self.subTest("Postprocessing: append -> multi value"):
            value = [SpchtThird("one text"), SpchtThird("two text"), SpchtThird("twenty text")]
            expected = [SpchtThird(value[0].content + node['append']),
                        SpchtThird(value[1].content + node['append']),
                        SpchtThird(value[2].content + node['append'])]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: append -> multi value & prefix"):
            value = [SpchtThird("one text"), SpchtThird("two text"), SpchtThird("twenty text")]
            node['dolphin_append'] = copy.copy(node['append'])
            expected = [SpchtThird(value[0].content + node['append']),
                        SpchtThird(value[1].content + node['append']),
                        SpchtThird(value[2].content + node['append'])]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "dolphin_"))

    def test_postprocessing_prepend(self):
        node = {"prepend": "AS-400: "}
        with self.subTest("Postprocessing: prepend -> one value"):
            value = [SpchtThird("some text")]
            expected = [SpchtThird(node['prepend'] + value[0].content)]  # such things make you wonder why you are even testing for it
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: prepend -> one value & prefix"):
            value = [SpchtThird("some different text")]
            expected = [SpchtThird(node['prepend'] + value[0].content)]  # such things make you wonder why you are even testing for it
            node['macaw_prepend'] = copy.copy(node['prepend'])
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, "macaw_"))
        with self.subTest("Postprocessing: prepend -> multi value"):
            value = [SpchtThird("one text"), SpchtThird("two text"), SpchtThird("twenty text")]
            expected = [SpchtThird(node['prepend'] + value[0].content),
                        SpchtThird(node['prepend'] + value[1].content),
                        SpchtThird(node['prepend'] + value[2].content)]
            self.assertEqual(expected, self.crow._node_postprocessing(value, node))
        with self.subTest("Postprocessing: prepend -> multi value"):
            value = [SpchtThird("one text."), SpchtThird("two text."), SpchtThird("twenty text.")]
            expected = [SpchtThird(node['prepend'] + value[0].content),
                        SpchtThird(node['prepend'] + value[1].content),
                        SpchtThird(node['prepend'] + value[2].content)]
            node['canine_prepend'] = copy.copy(node['prepend'])
            self.assertEqual(expected, self.crow._node_postprocessing(value, node, 'canine_'))

    def test_insert_fields(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = {
            "field": "salmon",
            "source": "dict",
            "insert_into": "#{}",
            "predicate": "https://insert.test/"
        }
        with self.subTest("Insert_into - one field"):
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into - one field, many values"):
            node['field'] = "sturgeon"
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#4')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#9')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#12'))
                        ]
            self.assertEqual(expected, self.crow._recursion_node(node))

    def test_insert_fields_multi(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = {
            "field": "salmon",
            "source": "dict",
            "insert_into": "#{}~{}",
            "predicate": "https://insert.test/",
            "insert_add_fields": [{"field": "tench"}]
        }
        with self.subTest("Insert_into_ two variables, two values"):
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~12'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into_ two variables, more values"):
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#4~12')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#9~12')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#12~12'))
                        ]
            node['field'] = "sturgeon"
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into two variables, double many values"):
            node['insert_add_fields'][0]['field'] = "foulfish"
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#4~Yellow')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#4~Purple')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#9~Yellow')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#9~Purple')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#12~Yellow')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#12~Purple'))
                        ]
            self.assertEqual(expected, self.crow._recursion_node(node))

    def test_insert_fields_transformation(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = {
            "field": "salmon",
            "source": "dict",
            "insert_into": "#{}~{}",
            "predicate": "https://insert.test/",
        }
        with self.subTest("Insert_into: append"):
            node["insert_add_fields"] = [{"field": "tench", "append": "**"}]
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~12**'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into: prepend"):
            node["insert_add_fields"] = [{"field": "tench", "prepend": "**"}]
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~**12'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into: cut"):
            node["insert_add_fields"] = [{"field": "catfish", "cut": "(air)\\b"}]
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~h')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~l')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~stairs')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~f')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~tear'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into: cut&replace"):
            node["insert_add_fields"] = [{"field": "catfish", "cut": "(air)\\b", "replace": "fire"}]
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~fire')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~hfire')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~lfire')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~stairs')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~ffire')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~tear'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("Insert_into: match"):
            node["insert_add_fields"] = [{"field": "catfish", "match": "(air)\\b"}]
            expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~air')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~hair')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~lair')),
                        SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird('#5~fair'))]
            self.assertEqual(expected, self.crow._recursion_node(node))
        # TODO: different source test

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
            self.assertFalse(self.crow._handle_if(node))
        with self.subTest("if_no_uneqal"):
            node['if_condition'] = "!="
            self.assertTrue(self.crow._handle_if(node))
        with self.subTest("if_no_smaller than"):
            node['if_condition'] = "<"
            self.assertTrue(self.crow._handle_if(node))

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

        expected = [SpchtTriple(None, SpchtThird('nullnullone', uri=True), SpchtThird('Yellow')),
                    SpchtTriple(None, SpchtThird('twonullnull', uri=True), SpchtThird('Blue')),
                    SpchtTriple(None, SpchtThird('nullthreenull', uri=True), SpchtThird('Red'))
                    ]
        self.assertEqual(expected, self.crow._joined_map(node))

    def test_joined_map_single(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(JOINED_NODE)
        node['field'] = "copperfish"
        node['joined_field'] = "bronzefish"

        expected = [SpchtTriple(None, SpchtThird('nullnullone', uri=True), SpchtThird('Pink'))]
        self.assertEqual(expected, self.crow._joined_map(node))

    def test_joined_map_singlepred_to_multi_object(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = copy.copy(JOINED_NODE)
        node['field'] = "silverfish"
        node['joined_field'] = "bronzefish"
        expected = [SpchtTriple(None, SpchtThird('nullnullone', uri=True), SpchtThird('Yellow')),
                    SpchtTriple(None, SpchtThird('nullnullone', uri=True), SpchtThird('Blue')),
                    SpchtTriple(None, SpchtThird('nullnullone', uri=True), SpchtThird('Red'))
                    ]
        self.assertEqual(expected, self.crow._joined_map(node))

    def test_static_value(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        static = "static_text"
        node = {
            "field": "salmon",
            "source": "dict",
            "required": "optional",
            "predicate": "https://insert.test/",
            "static_field": static
        }
        expected = [SpchtTriple(None, SpchtThird('https://insert.test/', uri=True), SpchtThird(static))]
        with self.subTest("existing field"):
            self.assertEqual(expected, self.crow._recursion_node(node))
        with self.subTest("not-existing field"):
            node['field'] = "whargabl"
            self.assertEqual(expected, self.crow._recursion_node(node))

    def test_append_uuid(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = {
            "field": "salmon",
            "source": "dict",
            "required": "optional",
            "predicate": "nonsense",
            "static_field": "https://test.whargable/",
            "append_uuid_object_fields": ["salmon", "perch", "trout"]
        }
        expected = [SpchtTriple(None,
                                SpchtThird('nonsense', uri=True),
                                SpchtThird('https://test.whargable/fbe44eac-4162-5ee5-bf36-88ea7914eb6d'))
                    ]
        self.assertEqual(expected, self.crow._recursion_node(node))

    def test_sub_nodes(self):
        self.crow._raw_dict = copy.copy(TEST_DATA)
        node = {
            "field": "salmon",
            "prepend": "https://test.whargable/res/",
            "source": "dict",
            "required": "optional",
            "predicate": "whargable:subres",
            "type": "uri",
            "sub_nodes": [
                {
                    "field": "perch",
                    "source": "dict",
                    "required": "optional",
                    "type": "uri",
                    "predicate": "whargable:fish"
                },
                {
                    "field": "foulfish",
                    "source": "dict",
                    "required": "optional",
                    "type": "uri",
                    "predicate": "whargable:canine"
                }
            ]
        }
        expected = [SpchtTriple(SpchtThird('https://test.whargable/res/5', uri=True), SpchtThird('whargable:fish', uri=True), SpchtThird('12', uri=True)),
                    SpchtTriple(SpchtThird('https://test.whargable/res/5', uri=True), SpchtThird('whargable:fish', uri=True), SpchtThird('9', uri=True)),
                    SpchtTriple(SpchtThird('https://test.whargable/res/5', uri=True), SpchtThird('whargable:canine', uri=True), SpchtThird('Yellow', uri=True)),
                    SpchtTriple(SpchtThird('https://test.whargable/res/5', uri=True), SpchtThird('whargable:canine', uri=True), SpchtThird('Purple', uri=True)),
                    SpchtTriple(None, SpchtThird('whargable:subres', uri=True), SpchtThird('https://test.whargable/res/5', uri=True))
                    ]
        self.assertEqual(expected, self.crow._recursion_node(node))
    # TODO: tests for get fields/predicates

    def test_tree_extract(self):
        logging.basicConfig(level=logging.DEBUG)
        inputing = ["one", "two", True]
        expected = [SpchtThird(inputing[0]), SpchtThird(inputing[1]), SpchtThird(inputing[2])]
        self.crow._raw_dict = {"layer1": {"layer2": {"layer3": inputing}}}
        node = {
            "source": "tree",
            "field": "layer1 >layer2> layer3"
        }
        self.assertEqual(expected, self.crow.extract_dictmarc_value(node))

    def test_sub_data(self):
        self.crow._raw_dict = TEST_DATA
        node = {
            "field": "uboot",
            "source": "dict",
            "required": "optional",
            "predicate": "whargable:ship",
            "sub_data": [
                {
                    "field": "uran",
                    "source": "dict",
                    "predicate": "whargable:element",
                    "required": "optional"
                }
            ]
        }
        expected = [SpchtTriple(None, SpchtThird('whargable:element', uri=True), SpchtThird('u-235')),
                    SpchtTriple(None, SpchtThird('whargable:element', uri=True), SpchtThird('u-238'))]
        self.assertEqual(expected, self.crow._recursion_node(node))

    def test_nested_sub_data(self):
        self.crow._raw_dict = TEST_DATA
        node = {
            "field": "spaceship",
            "source": "dict",
            "required": "optional",
            "predicate": "whargable:ftl",
            "sub_data": [
                {
                    "field": "ufo",
                    "source": "dict",
                    "predicate": "whargable:ufo",
                    "required": "optional",
                    "sub_data": [
                        {
                            "field": "earth",
                            "source": "dict",
                            "predicate": "whargable:shape",
                            "required": "optional",
                        },
                        {
                            "field": "mars",
                            "source": "dict",
                            "predicate": "whargable:shape",
                            "required": "optional",
                        }
                    ]
                }
            ]
        }
        expected = [
                    SpchtTriple(None, SpchtThird('whargable:shape', uri=True), SpchtThird('round')),
                    SpchtTriple(None, SpchtThird('whargable:shape', uri=True), SpchtThird('square')),
                    SpchtTriple(None, SpchtThird('whargable:shape', uri=True), SpchtThird('imperial')),
                    SpchtTriple(None, SpchtThird('whargable:shape', uri=True), SpchtThird('mechanicum'))
                    ]
        self.assertEqual(expected, self.crow._recursion_node(node))


if __name__ == '__main__':
    unittest.main()

