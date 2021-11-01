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
import logging
import re
import os
from collections import defaultdict
import random
import SpchtConstants
import SpchtErrors
import uuid
import copy

import local_tools

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
        if key in SpchtConstants.BUILDER_KEYS:
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

    def __init__(self, import_dict=None, unique_names=None, spcht_base_path=None):
        self._repository = {}
        self._root = SimpleSpchtNode(":ROOT:", parent=":ROOT:")
        self._references = {}
        if unique_names is None:
            self._names = UniqueNameGenerator(SpchtConstants.RANDOM_NAMES)
        else:
            self._names = UniqueNameGenerator(unique_names)
        if import_dict:
            self._importSpcht(import_dict, spcht_base_path)
        # self._names = UniqueNameGenerator(["Kaladin", "Yasnah", "Shallan", "Adolin", "Dalinar", "Roshone", "Teft", "Skar", "Rock", "Sylphrena", "Pattern", "Vasher", "Zahel", "Azure", "Vivianna", "Siri", "Susebron", "Kelsier", "Marsh", "Sazed", "Harmony", "Odium", "Rayse", "Tanavast"])

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
            raise KeyError(f"SpchtBuilder::Cannot access key '{item}'.")

    def add(self, UniqueSpchtNode: SimpleSpchtNode):
        if UniqueSpchtNode['name'] in self._repository:
            raise KeyError("Cannot add a name that is already inside")
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode

    def remove(self, UniqueName: str):
        # removes one specific key as long as it isnt referenced anywhere
        for each in self._repository:
            for key in SpchtConstants.BUILDER_REFERENCING_KEYS:
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
                for key in SpchtConstants.BUILDER_REFERENCING_KEYS:
                    if key in node and node[key] == OriginalName:
                        node[key] = UniqueSpchtNode['name']
            self._repository.pop(OriginalName)
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode

    def getNodesByParent(self, parent):
        """

        :param parent:
        :type parent:
        :return: a copy of the SimpleSpchtNode Object with the designated partent if its exist
        :rtype: SimpleSpchtNode
        """
        children = []
        for node in self._repository.values():
            if node.parent == parent:
                children.append(copy.copy(node))
        return children

    def createSpcht(self):
        # exports an actual Spcht dictionary
        pass

    def compileSpcht(self):
        # exports a compiled Spcht dictionary with all references solved
        # this still misses the root node
        return self.compileNode(":MAIN:")

    def compileNode(self, name: str):
        name = str(name)
        if name not in self._repository:
            return None
        pure_dict = {}
        for key, item in self._repository[name].properties.items():
            if key in SpchtConstants.BUILDER_LIST_REFERENCE:
                children_nodes = self.getNodesByParent(item)
                node_group = []
                for child_node in children_nodes:
                    node_group.append(self.compileNode(child_node['name']))
                pure_dict[key] = node_group
            elif key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                pure_dict[key] = self.compileNode(item)
            else:
                pure_dict[key] = item
            if 'predicate' not in pure_dict:
                pure_dict['predicate'] = "bla"  # find root predicate name
        return pure_dict

    def displaySpcht(self):
        # gives a reprensentation for SpchtCheckerGui
        curated_keys = ["name", "source", "field", "type", "mandatory", "sub_nodes", "sub_data", "predicate", "fallback", "comment"]
        grouped_dict = defaultdict(list)
        for node, each in self._repository.items():
            curated_data = {key: each.get(key, "") for key in curated_keys}
            grouped_dict[each.parent].append(curated_data)
        return grouped_dict

    def _importSpcht(self, spcht: dict, base_path=None):
        self._repository = {}
        self._names.reset()
        if 'nodes' not in spcht:
            raise SpchtErrors.ParsingError("Cannot read SpchtDict, lack of 'nodes'")
        self._repository = self._recursiveSpchtImport(spcht['nodes'], base_path)

    def _recursiveSpchtImport(self, spcht_nodes: list, base_path, parent=":MAIN:"):
        temp_spcht = {}
        for node in spcht_nodes:
            if 'name' not in node:
                name = self._names.giveName()
            elif 'name' in node and str(node['name']).strip() == "":
                name = self._names.giveName()
            else:
                name = node['name']
            new_node = SimpleSpchtNode(name, parent=parent)
            for key in SpchtConstants.BUILDER_KEYS.keys():
                if key in node and key != "name":
                    if key in SpchtConstants.BUILDER_LIST_REFERENCE:
                        new_group = self._names.giveName()
                        new_node[key] = new_group
                        temp_spcht.update(self._recursiveSpchtImport(node[key], base_path, parent=new_group))
                    elif key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                        list_of_one = self._recursiveSpchtImport([node[key]], base_path, parent=name)
                        for each in list_of_one:
                            new_node[key] = each
                            break
                        temp_spcht.update(list_of_one)
                    else:
                        new_node[key] = node[key]
                        rel_path = None
                        if key == 'mapping_settings' and base_path:
                            if '$ref' in node[key]:
                                rel_path = node[key]['$ref']
                        elif key == 'joined_map_ref' and base_path:
                            rel_path = node[key]
                        try:  # no base path no good
                            if rel_path:
                                keyvalue = local_tools.load_from_json(os.path.normpath(os.path.join(base_path, rel_path)))
                                if keyvalue:
                                    self._references[rel_path] = keyvalue
                        except FileNotFoundError:
                            logging.warning(f"Could not load additional data of reference: {node[key]}")
            # comments:
            comments = ""
            for key in node.keys():
                if re.search(r"^(comment)\w*$", key):
                    comments += node[key] + "\n"
            if comments.strip() != "":
                new_node['comment'] = comments[:-1]
            temp_spcht[name] = new_node
        return temp_spcht

    def compileNodeReference(self, node):
        """Uses the solved referenced inside the spcht builder to resolve the relative file paths provided by the
        given node. This works with arbitary nodes and is not limited to the Nodes inside the builder
        """
        node2 = copy.deepcopy(node)
        if 'mapping_settings' in node and '$ref' in node['mapping_settings']:
            map0 = node.get('mapping', {})
            map1 = self.resolveReference(node['mapping_settings']['$ref'])
            map1.update(map0)
            node2['mapping'] = map1
        if 'joined_map_ref' in node:
            map0 = node.get('joined_map', {})
            map1 = self.resolveReference(node['joined_map_ref'])
            map1.update(map0)
            node2['joined_map'] = map1
        for key in SpchtConstants.BUILDER_LIST_REFERENCE:
            if key in node:
                node2[key] = []
                for subnode in node[key]:
                    node2[key].append(self.compileNodeReference(subnode))
        for key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
            if key in node:
                node2[key] = self.compileNodeReference(node[key])
        return node2

    def resolveReference(self, rel_path: str):
        """
        Tries to resolve a relative file path of the Spcht file by using data loaded in the intial import
        only works if a base folder was provided when building the Spcht from the original dictionary
        :param str rel_path: relative path to the file, used as dictionary key
        """
        return copy.copy(self._references.get(rel_path, {}))

    def uniqueness_check(self):
        # checks if everything is in order for after import
        pass


class UniqueNameGenerator:
    def __init__(self, names: list, shuffle=False):
        self._current_index = 0
        self._names = names
        if shuffle:
            self.shuffle()

    def __iter__(self):
        return UniqueNameGeneratorIterator(self)

    def giveName(self):
        if self._current_index < len(self._names):
            self._current_index += 1
            return self._names[self._current_index-1]
        else:
            return uuid.uuid4().hex

    def shuffle(self):
        self.reset()
        random.shuffle(self._names)

    def reset(self):
        self._current_index = 0


class UniqueNameGeneratorIterator:
    def __init__(self, UNG: UniqueNameGenerator):
        self._UNG = UNG
        self._index = 0

    def __next__(self):
        if self._index < (len(self._UNG._names)):
            result = self._UNG._names[self._index]
            self._index += 1
            return result
        raise StopIteration



