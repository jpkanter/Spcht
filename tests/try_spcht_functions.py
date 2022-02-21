#!/usr/bin/env python
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

"""
Tests the functionality of the spcht library

Update: 08.02.2022

It rather did not test but it counts how often the processing of a certain testset fails that should not fail
at all, one cannot say that this is real unittesting, its more or less a demo i fear.
"""
import copy
import json
import logging

from Spcht.Core.SpchtCore import Spcht
import Spcht.Core.SpchtUtility as SpchtUtility

logging.basicConfig(filename='debug.log', format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)


def gather_stats(existing_stats, variable_value) -> dict:
    if isinstance(variable_value, str):
        existing_stats['string'] += 1
    elif isinstance(variable_value, list):
        existing_stats['list'] += 1
    elif variable_value is None:
        existing_stats['none'] += 1
    else:
        existing_stats['other'] += 1
    return existing_stats


if __name__ == "__main__":
    localTestData = "thetestset.json"
    print("Testing starts")
    crow = Spcht("featuretest.spcht.json", schema_path="./../Spcht/SpchtSchema.json", debug=False)
    if not crow:
        print("Couldnt Load Spcht file")
        exit(1)

    with open(localTestData, mode='r') as file:
        testdata = json.load(file)

    stat = {"list": 0, "none": 0, "string": 0, "other": 0}
    for entry in testdata:
        crow._raw_dict = entry
        crow._m21_dict = SpchtUtility.marc2list(crow._raw_dict.get('fullrecord'))

        # this basically does the same as .processData but a bit slimmed down
        for node in crow._DESCRI['nodes']:
            if node['source'] == "marc":
                value = crow.extract_dictmarc_value(node)
                stat = gather_stats(stat, value)
            if node['source'] == "dict":
                value = crow.extract_dictmarc_value(node)
                stat = gather_stats(stat, value)
            if 'fallback' in node:
                # i am interested in uniformity of my results, i only test for one level of callback
                tempNode = copy.deepcopy(node['fallback'])
                if tempNode['source'] == "marc":
                    value = crow.extract_dictmarc_value(node)
                    stat = gather_stats(stat, value)
                if tempNode['source'] == "dict":
                    value = crow.extract_dictmarc_value(node)
                    stat = gather_stats(stat, value)

    print(f"Result of Extract Test: {stat['list']} Lists, {stat['none']} Nones, {stat['string']} Strings, {stat['other']} Others")
    print("Should be only Lists and Nones.")

    # Insert String
    print("Testing Insert String")
    testNode = { 'source': 'dict',
                 'field': 'author',
                 'insert_add_fields': [
                     {'field': 'author2'},
                     {'field': 'language'}
                 ],
                 'insert_into': 'Author: {}, Author2: {} & Langugage: {}'
                 }
    for entry in testdata:
        crow._raw_dict = entry
        crow._m21_dict = SpchtUtility.marc2list(crow._raw_dict.get('fullrecord'))
        testVar = crow._inserter_string(crow.extract_dictmarc_value(testNode), testNode)
        if testVar:
            print(type(testVar), len(testVar), " \n  ", "\n   ".join([x.content for x in testVar]))

    stat['processing'] = 0
    for entry in testdata:
        try:
            line = crow.process_data(entry, "https://featherbeast.bird/")
        except Exception as e:
            print(e)
            stat['processing'] += 1
    print(f"Processing finished, found {stat['processing']} errors while doing so")


