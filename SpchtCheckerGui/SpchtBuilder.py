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
import datetime
import logging
import re
import os
from collections import defaultdict
import random
import SpchtConstants
import SpchtErrors
import uuid
import copy

import SpchtUtility
import local_tools

RESERVED_NAMES = [":MAIN:", ":UNUSED:", ":ROOT:"]


class SimpleSpchtNode:

    def __init__(self, name: str, parent=":UNUSED:", import_dict=None):
        self.properties = dict()
        self.properties['name'] = name  # TODO: should probably make sure this is actual possible
        self.parent = parent
        if import_dict:
            self.import_dictionary(import_dict)
        # using this as a dictionary proxy for now

    def get(self, key, default=None):
        if key in self.properties:
            return self.properties[key]
        else:
            return default

    def pop(self, key, default=None):
        """
        Simple forwarding of dictionaries .pop function
        :param str or int key: key of an dictionary
        :param any default: value that will be returned if nothing happened
        :return: the popped value
        :rtype: Any
        """
        if key not in self.properties:
            raise KeyError(key)
        return self.properties.pop(key, default)

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

    def __iter__(self):
        """
        Mirrors the iterable functionality of properties to external use
        :return:
        :rtype:
        """
        return self.properties.__iter__()

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent: str):
        self._parent = parent
        self.properties['parent'] = parent

    def import_dictionary(self, data: dict):
        # this is like the worst import procedure i can imagine, it checks nothing
        for key in data:
            try:
                self[key] = data[key]
            except KeyError:
                if key == "parent" and isinstance(data['parent'], str):
                    self.parent = data['parent']


class SpchtNodeGroup:
    def __init__(self, name: str):
        self.name = name
        self.repository = dict()


class SpchtBuilder:

    def __init__(self, import_dict=None, unique_names=None, spcht_base_path=None):
        self._repository = {}
        self.root = SimpleSpchtNode(":ROOT:", parent=":ROOT:")
        self.cwd = spcht_base_path
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

    def get(self, key, default=None):
        if key in self.repository:
            return self.repository[key]
        else:
            return default

    def add(self, UniqueSpchtNode: SimpleSpchtNode):
        UniqueSpchtNode['name'] = self.createNewName(UniqueSpchtNode['name'])
        # if UniqueSpchtNode['name'] in self._repository:
        #     raise KeyError("Cannot add a name that is already inside")
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode

    def remove(self, UniqueName: str):
        # removes one specific key as long as it isnt referenced anywhere
        for field in SpchtConstants.BUILDER_SINGLE_REFERENCE:
            if field in self[UniqueName]: # actually this is only fallback, will set anyone who is fallback of this to Main
                self[self[UniqueName][field]].parent = ":MAIN:"
        chainbreakers = []
        for field in SpchtConstants.BUILDER_LIST_REFERENCE:
            if field in self[UniqueName]:
                chainbreakers.append(self[UniqueName][field])
        for name in self._repository:
            # ? to assign multiple fields to one node a field name is created that is just ever expressed as the value
            # ? of sub_data and sub_nodes, therefore child element have to hear from this
            for unreal_field in chainbreakers:
                if self[name].parent == unreal_field:
                    self[name].parent = ":UNUSED:"

        self._repository.pop(UniqueName)

    def modify(self, OriginalName: str, UniqueSpchtNode: SimpleSpchtNode):
        if OriginalName not in self._repository:
            raise KeyError(f"Cannot update node {OriginalName} as it does not exist")
        # ! reinstate fallback relationships
        if OriginalName != UniqueSpchtNode['name']:
            UniqueSpchtNode['name'] = self.createNewName(UniqueSpchtNode['name'])

        # ! you can actually set a node to be its own parent, it wont be exported that ways as no recursion will find it
        # ! if you manually set a node a parent that already has a fallback that relationship will be usurped
        old_fallback = self._repository[OriginalName].get('fallback', None)
        new_fallback = UniqueSpchtNode.get('fallback', None)
        if old_fallback or new_fallback:  # we only have to iterate once through the thing
            for name in self._repository:
                if 'fallback' in self._repository[name]:
                    if old_fallback != new_fallback:
                        if self._repository[name]['fallback'] == new_fallback:  # the other nodes loses its fallback
                            self._repository[name].pop('fallback', None)
                        if name == old_fallback:
                            self._repository[name].parent = ":MAIN:"  # default back into the orphanage called :MAIN:
                if name == new_fallback:  # the target of the old fallback gets a new parent
                    self._repository[name].parent = UniqueSpchtNode['name']  # also accidentally updates the fallback in case the node is now named differently

        if OriginalName != UniqueSpchtNode['name']:  # * second time we do this because the fallback fix from above needed the name earlier
            # ? this is actually a rather hard decision, do i want to discard the name automatically or give choice to the user?
            # if UniqueSpchtNode['name'] in self._repository:
            #    raise SpchtErrors.OperationalError("Cannot modify node with new name as another node already exists")
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

    def exportDict(self):
        a = dict()
        a['meta'] = {'created': str(datetime.date.today().isoformat())}
        b = dict()
        b[':ROOT:'] = self.root.properties
        b[':ROOT:']['parent'] = self.root.parent
        for key in self._repository:
            b[key] = self._repository[key].properties
            b[key]['parent'] = self._repository[key].parent
        a['nodes'] = b
        a['references'] = self._references  # all referenced data that could be loaded
        return a

    def importDict(self, spchtbuilder_point_json: dict):
        # TODO: make this throw exceptions to better gauge the reason for rejection
        if not SpchtUtility.is_dictkey(spchtbuilder_point_json, "nodes", "references"):
            return False
        # sanity check for references
        if not isinstance(spchtbuilder_point_json['references'], dict) or not isinstance(spchtbuilder_point_json['nodes'], dict):
            return False
        # check for duplicates
        uniques = set()
        for name in spchtbuilder_point_json['nodes']:
            if name in uniques:
                return False
            uniques.add(name)
            if 'sub_nodes' in spchtbuilder_point_json['nodes'][name]:
                uniques.add(spchtbuilder_point_json['nodes'][name]['sub_nodes'])
            if 'sub_data' in spchtbuilder_point_json['nodes'][name]:
                uniques.add(spchtbuilder_point_json['nodes'][name]['sub_data'])
        # getting a fresh node
        throwaway_builder = SpchtBuilder()
        self.root = copy.deepcopy(throwaway_builder.root)
        self._repository = {}
        self._references = {}
        for name in spchtbuilder_point_json['nodes']:
            if name == ":ROOT:":
                self.root = spchtbuilder_point_json['nodes'][':ROOT:']
            else:
                self._repository[name] = SimpleSpchtNode(name, import_dict=spchtbuilder_point_json['nodes'][name])

        for ref in spchtbuilder_point_json['references']:
            self._references[ref] = {}
            for key, value in spchtbuilder_point_json['references'][ref].items():
                if isinstance(value, (dict, list)):
                    return False
                self._references[ref][key] = value
        return True

    def createSpcht(self):
        # exports an actual Spcht dictionary
        root_node = {"id_source": self.root['source'],
                     "id_field": self.root['field'],
                     "nodes": self.compileSpcht()}
        if 'fallback' in self.root:
            fallback = self.compileNodeByParent(":ROOT:")
            root_node.update({'id_fallback': fallback[0]})
        return root_node

    def compileSpcht(self):
        # exports a compiled Spcht dictionary with all references solved
        # this still misses the root node
        return self.compileNodeByParent(":MAIN:")

    def compileNodeByParent(self, parent: str, mode="conservative"):
        """
        Compiles a node by common parent, has two modes:

        * conservative (default) - will discard all nodes that do not possess the minimum Spcht requirements
        * reckless - will add any node, regardless if the resulting spcht might not be useable
        :param parent:
        :type parent:
        :param mode:
        :type mode:
        :return:
        :rtype:
        """
        parent = str(parent)
        node_list = []
        for key, top_node in self._repository.items():
            if top_node.parent == parent:
                one_node = self.compileNode(key)
                if mode == "reckless":
                    node_list.append(one_node)
                else:
                    # * this has the potential to wreck entire chains if the top node is incorrect
                    if not SpchtUtility.is_dictkey(one_node, "field", "source", "predicate", "required"):
                        continue
                    if str(one_node['field']).strip() == "" or str(one_node['predicate']).strip() == "":
                        continue
                    node_list.append(one_node)
        return node_list

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
            elif key == 'parent':  # parent added to object for some convenience but its not technically in the schema
                continue
            else:
                pure_dict[key] = item
            if 'predicate' not in pure_dict:
                predicate = self.inheritPredicate(name)  # find root predicate name
                if predicate:
                    pure_dict['predicate'] = predicate
        return pure_dict

    def inheritPredicate(self, sub_node_name: str):
        """
        Sub-Nodes are not required to have the predicate redefined as those get inherited from the parent,
        fallbacks for example wont have a predicate but can inherit one from their ancestors

        This will fail horribly when used on something that actually has no parent in its chain
        :param sub_node_name: unique name of that sub_node
        :type sub_node_name: str
        :return: a predicate
        :rtype: str
        """
        try:
            if 'predicate' not in self._repository[sub_node_name].properties:
                if self._repository[sub_node_name].parent == ":MAIN" or self._repository[sub_node_name].parent == ":ROOT:":
                    return ""
                return self.inheritPredicate(self._repository[sub_node_name].parent)
            else:
                return self._repository[sub_node_name]['predicate']
        except KeyError as e:
            print(self._repository.get(sub_node_name))
            logging.warning(f"Could not inherit predicate for {sub_node_name} - {e}")
            return ""

    def displaySpcht(self):
        # gives a reprensentation for SpchtCheckerGui
        curated_keys = ["name", "source", "field", "type", "mandatory", "sub_nodes", "sub_data", "predicate", "fallback", "comment"]
        grouped_dict = defaultdict(list)
        for node, each in self._repository.items():
            curated_data = {key: each.get(key, "") for key in curated_keys}
            # tech usage:
            techs = []
            for tech in SpchtConstants.BUILDER_SPCHT_TECH:
                if tech in each:
                    techs.append(tech)
            curated_data['tech'] = ", ".join(techs)
            grouped_dict[each.parent].append(curated_data)
        return grouped_dict

    @staticmethod
    def displaySpchtHeaders() -> list:
        """
        Just echos the possible header names from above so SpchtBuilder can serve as a "source of truth"
        :return: a list of strings
        :rtype: list
        """
        return ["name", "source", "field", "type", "mandatory", "sub_nodes", "sub_data", "predicate", "fallback", "tech", "comment"]

    def _importSpcht(self, spcht: dict, base_path=None):
        self._repository = {}
        self._names.reset()
        if 'nodes' not in spcht:
            raise SpchtErrors.ParsingError("Cannot read SpchtDict, lack of 'nodes'")
        self._repository = self._recursiveSpchtImport(spcht['nodes'], base_path)
        # ! import :ROOT:
        self.root['field'] = spcht['id_field']
        self.root['source'] = spcht['id_source']
        # this special case of root fallbacks makes for a good headache
        if 'id_fallback' in spcht:
            root_fallbacks = self._recursiveSpchtImport([spcht['id_fallback']], base_path, parent=":ROOT:")
            # ? iterating through all fallbacks which will be the one directly tied to root and those below it, each
            # ? node can only have on fallback so we can safely skip after the first one, yet those fallbacks
            # ? live normally in the repository
            for key in root_fallbacks:
                if root_fallbacks[key]['parent'] == ":ROOT:":
                    self.root['fallback'] = key
                    break
            self._repository.update(root_fallbacks)

    def _recursiveSpchtImport(self, spcht_nodes: list, base_path, parent=":MAIN:") -> dict:
        temp_spcht = {}
        for node in spcht_nodes:
            if 'name' not in node:
                name = self._names.giveName()
            elif 'name' in node and str(node['name']).strip() == "":
                name = self._names.giveName()
            else:
                name = node['name']
            name = self.createNewName(name, "number", alt_repository=temp_spcht)
            node['name'] = name
            new_node = SimpleSpchtNode(name, parent=parent)
            for key in SpchtConstants.BUILDER_KEYS.keys():
                if key in node and key != "name":
                    if key in SpchtConstants.BUILDER_LIST_REFERENCE:  # sub_nodes & sub_data
                        new_group = self._names.giveName()
                        new_group = self.createNewName(new_group, "replace")
                        new_node[key] = new_group
                        temp_spcht.update(self._recursiveSpchtImport(node[key], base_path, parent=new_group))
                    elif key in SpchtConstants.BUILDER_SINGLE_REFERENCE:  # fallback
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

    def getSolidParents(self):
        return [key for key in self._repository]

    def getChildlessParents(self):
        """
        Finds all parent objects that are actual nodes and do not already possess a fallback
        :return: list of all nodes without fallback
        :rtype: list
        """
        return [x for x in self._repository if 'fallback' not in self._repository[x]]

    def getSubdataParents(self):
        names = []
        for node in self._repository.values():
            if 'sub_nodes' in node.properties:
                names.append(node.properties['sub_nodes'])
        return names

    def getSubnodeParents(self):
        names = []
        for node in self._repository.values():
            if 'sub_data' in node.properties:
                names.append(node.properties['sub_data'])
        return names

    def getAllParents(self):
        names = []
        for key, node in self._repository.items():
            if 'sub_data' in node.properties:
                names.append(node.properties['sub_data'])
            if 'sub_nodes' in node.properties:
                names.append(node.properties['sub_nodes'])
            names.append(key)
        return names

    def createNewName(self, name: str, mode="add", alt_repository=None) -> str:
        """
        Creates a new name by the given name, if the provided name is already unique it just gets echoed, otherwise
        different methods can be utilised to generate a new one.

        Finding modes:

        * add - adds a random string from the name repository to the original name, might be an UUID DEFAULT
        * number - just counts up a number at the end
        * replace - replaces the name with one of the name repository, might be an UUID
        :param str name: any UTF-8 valid name
        :param str mode: 'add', 'number' or 'replace
        :param didct alt_repository: alternative names repository in case of bulk processing
        :return: a new, unique name
        :rtype: str
        """
        all_clear = True # i fear this is the easiest way, but i am not happy with it
        if alt_repository:
            for key in alt_repository:
                if key == name:
                    all_clear = False
                    break
                if hasattr(alt_repository[key], "parent"):  # theoretically this has not to be a dict of SimpleSpchtNodes
                    if alt_repository[key].parent == name:
                        all_clear = False
                        break
            if name not in alt_repository:
                return name
        else:  # checks for direct names and duplicated parent names
            for key in self._repository:
                if key == name:
                    all_clear = False
                    break
                if self._repository[key].parent == name:
                    all_clear = False
                    break
        if all_clear:
            return name
        # ! in case a duplicate was found
        if mode == "number":
            found = re.search(r"[0-9]+$", name)
            if found:
                pos0 = found.regs[0][0]
                num = int(found.group(0))+1
                name = name[:pos0] + num
            else:
                name = f"{name}1"
        elif mode == "replace":
            name = self._names.giveName()
        else:
            name = f"{name}{self._names.giveName()}"  # one day i have to benchmark whether this is faster than str + str
        return self.createNewName(name, mode)


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



