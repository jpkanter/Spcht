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

import json
import re


def grab(a_list, dict_attr, dict_value):
    for each in a_list:
        if dict_attr in each and each[dict_attr] == dict_value:
            return each
    return None


if __name__ == "__main__":
    try:
        raw_info = None
        with open("folio_dump.json", "r") as folio_dump:
            raw_info = json.load(folio_dump)
        if raw_info:
            extracted_dicts = []
            for each in raw_info['locations']:
                if re.search(r"entrance$", each['code']):
                    inst = grab(raw_info['locinsts'], "id", each['institutionId'])
                    lib = grab(raw_info['loclibs'], "id", each['libraryId'])
                    one_node = {
                        "inst_code": inst['code'],
                        "inst_name": inst['name'],
                        "lib_code": lib['code'],
                        "lib_name": lib['name'],
                        "loc_name": each['name'],
                        "loc_code": each['code'],
                        "loc_displayName": each['discoveryDisplayName']
                    }
                    one_node.update(each['details'])
                    extracted_dicts.append(one_node)
            with open("folio_extract.json", "w") as folio_extract:
                json.dump(extracted_dicts, folio_extract, indent=2)
        else:
            print("Loading failed, cannot create what is needed")

    except Exception as e:
        print(f"THIS throws Exception {e.__class__.__name__}: '{e}'")
        exit(1)  # what sense is it to catch exceptions to then just print them?

