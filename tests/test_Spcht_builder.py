#!/usr/bin/env python#!/usr/bin/env python
# coding: utf-8

# Copyright 2022 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of the Spcht.
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
# along with Spcht.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

import unittest
import json
from Spcht.Gui.SpchtBuilder import SpchtBuilder, SimpleSpchtNode

# ! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ! these test are for now not functional as i use data that change at any time
# ! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


class TestSpchtBuilder(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpchtBuilder, self).__init__(*args, **kwargs)

    @staticmethod
    def _create_dummy():
        """This puts a lot of trust in the established init functions"""
        blue = SpchtBuilder()
        copper = SimpleSpchtNode("copper", "iron",
                                 field="two", source="dict", predicate="wk:11", fallback="zinc")
        iron = SimpleSpchtNode("iron", ":MAIN:",
                                 field='one', source="dict", fallback="copper", predicate="wk:12")
        tin = SimpleSpchtNode("tin", ":MAIN:",
                              field="eleven", source="tree", predicate="wkd:neun")
        pewder = SimpleSpchtNode("pewder", ":MAIN:",
                                 field="another", source="marc", predicate="wth:apl")
        zinc = SimpleSpchtNode("zinc", "copper", field="many", source="dict", predicate="mt:32")
        blue.add(iron)
        blue.add(copper)
        blue.add(tin)
        blue.add(pewder)
        blue.add(zinc)
        return blue

    def test_import(self):
        """
        Tests if the import of featuretest has the structure that is to be expected

        :return:
        :rtype:
        """
        with self.subTest("general import"):
            with open("featuretest.spcht.json") as json_file:
                big_bird = json.load(json_file)
            test1 = SpchtBuilder(big_bird, spcht_base_path="./")
        with self.subTest("1st level import"):
            self.assertEqual("wk:12", test1['fallback_with_names']['predicate'])
        with self.subTest("2nd named level import"):
            self.assertEqual("author_mv", test1['fallback_with_name_2nd_level']['field'])
        with self.subTest("3rd named level import"):
            self.assertEqual("somrhing_mv", test1['fallback_with_name_3rd_level']['field'])

        with self.subTest("1st level unnamed import"):
            fallback = test1['fallback_without_names']['fallback']
            parent = test1[fallback].parent
            self.assertEqual('fallback_without_names', parent)
            self.assertEqual("director_mv", test1[fallback]['field'])
        with self.subTest("2nd level unnamed import"):
            fallback1 = test1['fallback_without_names']['fallback']
            fallback2 = test1[fallback1]['fallback']
            parent = test1[fallback2].parent
            self.assertEqual(test1[fallback1]['name'], parent)
            self.assertEqual("anything_mv", test1[fallback2]['field'])

    def test_clone(self):
        dummy = self._create_dummy()
        with self.subTest("Simple Node Clone"):
            new_name = dummy.clone("tin")
            one = dummy.compileNode("tin", purity=True, anon=True)
            two = dummy.compileNode(new_name, purity=True, anon=True)
            self.assertEqual(one, two)
        with self.subTest("Nested Node Clone"):
            new_name = dummy.clone("iron")
            one = dummy.compileNode("iron", purity=True, anon=True)
            two = dummy.compileNode(new_name, purity=True, anon=True)
            self.assertEqual(one, two)

    def test_modify(self):
        pass

    def test_add(self):
        pass

    def test_del(self):
        pass

    def test_compile(self):
        pass

    def test_create(self):
        pass

    def test_name_conflicts(self):
        dummy = self._create_dummy()
        hilbert = SimpleSpchtNode("iron", ":MAIN:", field="book", predicate="wk:00", source="dict")
        new_name = dummy.add(hilbert)
        print(dummy.compileNode(new_name, False, True, True))
        self.assertIsNotNone(new_name)
        self.assertNotEqual("iron", new_name)

