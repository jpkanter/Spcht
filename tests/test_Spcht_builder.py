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
        copper = SimpleSpchtNode("copper", "indigo",
                                 field="two", source="dict", predicate="wk:11")
        iron = SimpleSpchtNode("iron", ":MAIN:",
                                 field='one', source="dict", fallback="copper", predicate="wk:12")
        tin = SimpleSpchtNode("tin", ":MAIN",
                              field="eleven", source="tree", predicate="wkd:neun")
        pewder = SimpleSpchtNode("pewder", ":MAIN:",
                                 field="another", source="marc", predicate="wth:apl")
        blue.add(copper)
        blue.add(iron)
        blue.add(tin)
        blue.add(pewder)
        return blue

    def test_import(self):
        with open("../Spcht/foliotools/folio.spcht.json") as json_file:
            big_bird = json.load(json_file)
        test1 = SpchtBuilder(big_bird)
        test1.repository = test1._importSpcht(big_bird)
        name = test1.getNodesByParent(":MAIN:")[0]['name']
        print(json.dumps(test1.compileNode(name), indent=2))

    def test_clone(self):
        dummy = self._create_dummy()
        print(dummy)
        print(repr(dummy['iron']))
        pass

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
        pass

