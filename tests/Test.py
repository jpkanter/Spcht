#!/usr/bin/env python
"""
Tests the functionality of the spcht library
"""
import json, copy

import os, sys, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
from SpchtDescriptorFormat import Spcht


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
    localTestData = "./thetestset.json"  # only true for MY Pc, testdata folder is not in git
    print("Testing starts")
    my_little_feather = Spcht("./featuretest.spcht.json")
    if my_little_feather:
        print("Couldnt Load Spcht file")
        exit(1)

    with open(localTestData, mode='r') as file:
        testdata = json.load(file)

    stat = {"list": 0, "none": 0, "string": 0, "other": 0}
    for entry in testdata:
        m21_record = Spcht.marc2list(entry.get('fullrecord'))

        # this basically does the same as .processData but a bit slimmed down
        for node in my_little_feather._DESCRI['nodes']:
            if node['source'] == "marc":
                value = Spcht.extract_dictmarc_value(m21_record, node)
                stat = gather_stats(stat, value)
            if node['source'] == "dict":
                value = Spcht.extract_dictmarc_value(entry, node)
                stat = gather_stats(stat, value)
            if Spcht.is_dictkey(node, 'fallback'):
                # i am interested in uniformity of my results, i only test for one level of callback
                tempNode = copy.deepcopy(node['fallback'])
                if tempNode['source'] == "marc":
                    value = Spcht.extract_dictmarc_value(m21_record, node)
                    stat = gather_stats(stat, value)
                if tempNode['source'] == "dict":
                    value = Spcht.extract_dictmarc_value(entry, node)
                    stat = gather_stats(stat, value)

    print(f"Result of Extract Test: {stat['list']} Lists, {stat['none']} Nones, {stat['string']} Strings, {stat['other']} Others")
    print("Should be only Lists and Nones.")

    # Insert String
    print("Testing Insert String")
    testNode = { 'source': 'dict',
                 'field': 'author',
                 'insert_add_fields': ['author2', 'language'],
                 'insert_into': 'Author: {}, Author2: {} & Langugage: {}'
                 }
    for entry in testdata:
        testVar = my_little_feather._inserter_string(entry, testNode)
        print(type(testVar), len(testVar))



    stat['processing'] = 0
    for entry in testdata:
        try:
            line = my_little_feather.processData(entry, "https://featherbeast.bird/")
        except Exception as e:
            print(e)
            stat['processing'] += 1
    print(f"Processing finished, found {stat['processing']} errors while doing so")


