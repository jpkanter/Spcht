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
import copy
from SpchtCore.SpchtCore import SpchtNode
import SpchtCore.SpchtUtility as SpchtUtility

import logging
import os
logging.basicConfig(filename=os.devnull)  # hides logging that occurs when testing for exceptions
#logging.basicConfig(level=logging.DEBUG)


class TestSpchtNode(unittest.TestCase):

    def test_basic_null_node(self):
        hans = SpchtNode()
        with self.subTest("Empty Node repr:"):
            expected = "SpchtNode {'source': \"dict\", 'type': \"literal\", 'required': \"optional\"}"
            self.assertEqual(expected, str(hans))
        with self.subTest("Empty node length"):
            self.assertEqual(3, len(hans))

    def test_basic_get(self):
        rolf = SpchtNode()
        with self.subTest("Get existing value:"):
            expected = "dict"
            self.assertEqual(expected, rolf['source'])
        with self.subTest("Get non-existing value:"):
            self.assertEqual(None, rolf['if_field'])
        with self.subTest("Get non-existing, non-accessable Key:"):
            with self.assertRaises(KeyError):
                rolf['world-equation']

    def test_import(self):
        michael = SpchtNode()
        try:
            with open("featuretest.spcht.json", "r") as import_file:
                jsoned = json.load(import_file)
                node = 12
                that_node = jsoned['nodes'][node]
                michael.import_dict(that_node)
                expected = "SpchtNode {}"
                self.assertEqual(expected,  str(michael))
        except Exception as e:
            self.assertEqual(e, None)


if __name__ == '__main__':
    unittest.main()
