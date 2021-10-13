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
import copy
from SpchtDescriptorFormat import SpchtThird, SpchtTriple
import rdflib

import logging
import os
logging.basicConfig(filename=os.devnull)  # hides logging that occurs when testing for exceptions


class TestSpchtThird(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpchtThird, self).__init__(*args, **kwargs)

    def test_simple_create(self):
        with self.subTest("creation"):
            self.assertIsInstance(SpchtThird(""), SpchtThird)  # this is a wild test Oo
        with self.subTest("create_str"):
            self.assertEqual('"test"', str(SpchtThird("test")))
        with self.subTest("create_repr"):
            self.assertEqual('"test"', str(SpchtThird("test")))

    def test_uri_create(self):
        self.assertEqual('<test>', str(SpchtThird("test", uri=True)))

    def test_create_language(self):
        self.assertEqual('"test"@se', str(SpchtThird("test", language="se")))

    def test_create_annoation(self):
        self.assertEqual('"test"^^xsd:time', str(SpchtThird("test", annotation="xsd:time")))

    def test_create_import(self):
        with self.subTest("import proper process annotation"):
            self.assertEqual('"test"^^xsd:time', str(SpchtThird("test", tag="^^xsd:time")))
        with self.subTest("import proper process annotation"):
            self.assertEqual('"test"@se', str(SpchtThird("test", tag="@se")))
        with self.subTest("import inproper annotation"):
            self.assertEqual('"test"', str(SpchtThird("test", tag="^xsd:time")))
        with self.subTest("import inproper process annotation"):
            self.assertEqual('"test"', str(SpchtThird("test", tag="äse")))

    def test_annotation(self):
        with self.subTest("proper annotation"):
            one_third = SpchtThird("test")
            one_third.annotation = "xsd:time"
            self.assertEqual('"test"^^xsd:time', str(one_third))
        with self.subTest("annotation collision"):
            with self.assertRaises(ValueError):
                one_third.language = "de"

    def test_language(self):
        with self.subTest("proper language"):
            one_third = SpchtThird("test")
            one_third.language = "se"
            self.assertEqual('"test"@se', str(one_third))
        with self.subTest("language collision"):
            with self.assertRaises(ValueError):
                one_third.annotation = "xsd:time"

    def test_compare(self):
        kaladin = SpchtThird("highstorm")
        shallan = SpchtThird("highstorm")
        self.assertEqual(kaladin, shallan)
        # i actually had to implement __eq__ for tests cause assert wont work otherwise

    def test_2rdf(self):
        with self.subTest("standard convert"):
            self.assertEqual(rdflib.Literal("Penguin"), SpchtThird("Penguin").convert2rdflib())
        with self.subTest("literal convert language"):
            self.assertEqual(rdflib.Literal("Penguin", lang="se"), SpchtThird("Penguin", language="se").convert2rdflib())
        with self.subTest("literla convert annotation"):
            self.assertEqual(rdflib.Literal("Penguin", datatype="xsd:string"), SpchtThird("Penguin", tag="^^xsd:string").convert2rdflib())


class TestSpchtTriple(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestSpchtTriple, self).__init__(*args, **kwargs)

    def test_empty_creation(self):
        self.assertEqual('(None, None, None)', str(SpchtTriple()))

    def test_object_creation(self):
        with self.subTest("object"):
            self.assertEqual('(None, None, "bla")', str(SpchtTriple(sobject=SpchtThird("bla"))))
        with self.subTest("subject"):
            self.assertEqual('(<bla>, None, None)', str(SpchtTriple(subject=SpchtThird("bla", uri=True))))
        with self.subTest("predicate"):
            self.assertEqual('(None, <bla>, None)', str(SpchtTriple(predicate=SpchtThird("bla", uri=True))))

    def test_uri_check(self):
        with self.subTest("subject not uri"):
            with self.assertRaises(TypeError):
                SpchtTriple(SpchtThird(""))
        with self.subTest("predicate not uri"):
            with self.assertRaises(TypeError):
                SpchtTriple(predicate=SpchtThird(""))