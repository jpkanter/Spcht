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

sources = ("dict", "marc", "tree")
# this is basically the json Schema once more
builder_keys = {
    "name": "str",
    "field": "str",
    "source": "str",
    "predicate": "str",
    "required": "boolean",
    "type": "boolean",
    "alternatives": "list",
    "mapping": "dict",
    "mapping_settings": "dict",
    "joined_map": "dict",
    "joined_field": "str",
    "joined_map_ref": "str",
    "match": "str",
    "append": "str",
    "prepend": "str",
    "cut": "str",
    "replace": "str",
    "insert_into": "str",
    "insert_add_field": "list",
    "if_field": "str",
    "if_value": "str",
    "if_condition": "str",
    "fallback": "str",
    "comment": "str",
    "sub_nodes": "str",
    "sub_data": "str",
    "tag": "str",
    "static_field": "str",
    "append_uuid_predicate_fields": "list",
    "append_uuid_object_fields": "list"
}
# all keys that reference another node
builder_referencing_keys = ["sub_nodes", "sub_data", "fallback"]
builder_single_reference = ["fallback"]
builder_list_reference = ["sub_nodes", "sub_data"]

if __name__ == "__main__":
    print("this file is not meant to be executed and only contains constant variables")
    exit(0)
