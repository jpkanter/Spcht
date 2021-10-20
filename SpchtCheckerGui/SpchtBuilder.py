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

from collections import defaultdict
import SpchtConstants
import SpchtErrors
import uuid

RESERVED_NAMES = [":MAIN:", ":UNUSED:", ":ROOT:"]


class SimpleSpchtNode:

    def __init__(self, name: str, parent=":UNUSED:", import_dict=None):
        self.properties = dict()
        self.properties['name'] = name  # TODO: should probably make sure this is actual a possible
        self.parent = parent
        # using this as a dictionary proxy for now

    def get(self, key, default=None):
        if key in self.properties:
            return self.properties[key]
        else:
            return default

    def __repr__(self):
        return f"Parent={self.parent} - " + str(self.properties)

    def __getitem__(self, item):
        if item in self.properties:
            return self.properties[item]
        else:
            raise KeyError(item)

    def __setitem__(self, key, value):
        if key in SpchtConstants.builder_keys:
            self.properties[key] = value
        else:
            raise KeyError(f"{key} is not a valid Spcht key")

    def __delitem__(self, key):
        if key != "name":
            if key in self.properties:
                del self.properties[key]


class SpchtNodeGroup:
    def __init__(self, name: str):
        self.name = name
        self.repository = dict()


class SpchtBuilder:

    def __init__(self, import_dict = None):
        self._repository = {}
        self._root = SimpleSpchtNode(":ROOT:", parent=":ROOT:")
        self._names = UniqueNameGenerator(["Kaladin", "Yasnah", "Shallan", "Adolin", "Dalinar", "Roshone", "Teft", "Skar", "Rock", "Sylphrena", "Pattern", "Vasher", "Zahel", "Azure", "Vivianna", "Siri", "Susebron", "Kelsier", "Marsh", "Sazed", "Harmony", "Odium", "Rayse", "Tanavast"])

    @property
    def repository(self):
        return self._repository

    @repository.setter
    def repository(self, repository: dict):
        self._repository = repository

    def __getitem__(self, item):
        if item in self.repository:
            return self.repository[item]
        else:
            raise KeyError(item)

    def add(self, UniqueSpchtNode: SimpleSpchtNode):
        if UniqueSpchtNode['name'] in self._repository:
            raise KeyError("Cannot add a name that is already inside")
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode

    def remove(self, UniqueName: str):
        # removes one specific key as long as it isnt referenced anywhere
        for each in self._repository:
            for key in SpchtConstants.builder_referencing_keys:
                if key in each and each[key] == UniqueName:
                    raise SpchtErrors.OperationalError("Cannot delete this node, its referenced elsewhere:")
        self._repository.pop(UniqueName)

    def modify(self, OriginalName: str, UniqueSpchtNode: SimpleSpchtNode):
        if OriginalName not in self._repository:
            raise KeyError(f"Cannot update node {OriginalName} as it does not exist")
        if OriginalName != UniqueSpchtNode['name']:
            if UniqueSpchtNode['name'] in self._repository:
                raise SpchtErrors.OperationalError("Cannot modify node with new name as another node already exists")
            for node in self._repository:  # updates referenced names
                for key in SpchtConstants.builder_referencing_keys:
                    if key in node and node[key] == OriginalName:
                        node[key] = UniqueSpchtNode['name']
            self._repository.pop(OriginalName)
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode

    def createSpcht(self):
        # exports an actual Spcht dictionary
        pass

    def compileSpcht(self):
        # exports a compiled Spcht dictionary with all references solved
        pass

    def displaySpcht(self):
        # gives a reprensentation for SpchtCheckerGui
        curated_keys = ["name", "source", "field", "type", "mandatory", "sub_nodes", "sub_data", "predicate"]
        grouped_dict = defaultdict(list)
        for node, each in self._repository.items():
            curated_data = {key: each.get(key, "") for key in curated_keys}
            grouped_dict[each.parent].append(curated_data)
        return grouped_dict

    def _importSpcht(self, spcht: dict):
        if 'nodes' not in spcht:
            raise SpchtErrors.ParsingError("Cannot read SpchtDict, lack of 'nodes'")
        temp_spcht = self._recursiveSpchtImport(spcht['nodes'])
        return temp_spcht

    def _recursiveSpchtImport(self, spcht_nodes: list, parent=":MAIN:"):
        temp_spcht = {}
        for node in spcht_nodes:
            if 'name' not in node:
                name = self._names.giveName()
            elif 'name' in node and str(node['name']).strip() == "":
                name = self._names.giveName()
            else:
                name = node['name']
            new_node = SimpleSpchtNode(name, parent=parent)
            for key in SpchtConstants.builder_keys.keys():
                if key in node and key != "name":
                    if key in SpchtConstants.builder_list_reference:
                        new_group = self._names.giveName()
                        new_node[key] = new_group
                        temp_spcht.update(self._recursiveSpchtImport(node[key], parent=new_group))
                    elif key in SpchtConstants.builder_single_reference:
                        list_of_one = self._recursiveSpchtImport([node[key]], parent=name)
                        for each in list_of_one:
                            new_node[key] = each
                            break
                        temp_spcht.update(list_of_one)
                    else:
                        new_node[key] = node[key]
            temp_spcht[name] = new_node
        return temp_spcht

    def uniqueness_check(self):
        # checks if everything is in order for after import
        pass


class UniqueNameGenerator:
    def __init__(self, names: list):
        self._current_index = 0
        self._names = names

    def giveName(self):
        if self._current_index < len(self._names):
            self._current_index += 1
            return self._names[self._current_index-1]
        else:
            return uuid.uuid4().hex
