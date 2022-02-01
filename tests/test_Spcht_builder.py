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
from solr2triplestore.SpchtCheckerGui import SpchtBuilder

# ! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ! these test are for now not functional as i use data that change at any time
# ! !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


class TestSpchtBuilder(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpchtBuilder, self).__init__(*args, **kwargs)

    def test_import(self):
        with open("../foliotools/folio.spcht.json") as json_file:
            big_bird = json.load(json_file)
        test1 = SpchtBuilder(big_bird)
        test1.repository = test1._importSpcht(big_bird)
        name = test1.getNodesByParent(":MAIN:")[0]['name']
        print(json.dumps(test1.compileNode(name), indent=2))