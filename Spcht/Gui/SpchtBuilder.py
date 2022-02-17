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
import uuid
import copy
import random

# own imports

import Spcht.Utils.SpchtConstants as SpchtConstants
import Spcht.Core.SpchtErrors as SpchtErrors
import Spcht.Core.SpchtUtility as SpchtUtility
import Spcht.Utils.local_tools as local_tools

RESERVED_NAMES = [":ROOT:", ":UNUSED:", ":MAIN:"]

logger = logging.getLogger(__name__)


class SimpleSpchtNode:

    def __init__(self, name: str, parent=":UNUSED:", import_dict=None, **properties):
        self.properties = dict()
        self.properties['name'] = name  # TODO: should probably make sure this is actual possible
        self.parent = parent
        self.predicate_inheritance = True
        if import_dict:
            self.import_dictionary(import_dict)
        # using this as a dictionary proxy for now

        for key, prop in properties.items():
            try:
                self.properties[key] = prop
            except KeyError as e:
                logger.debug("SimpleSpchtNode>INIT:", e)  # we ignore key errors

    def __repr__(self):
        representation = f"{self.properties['name']} :: parent='{self.parent}' | "
        representation += ", ".join([f"{key}: '{value}'" for key, value in self.properties.items() if key != "name" or key != "parent"])
        return representation

    #def __repr__(self):
    #    return f"Parent={self.parent} - " + str(self.properties)

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

    def items(self):
        return self.properties.items()

    def values(self):
        return self.properties.values()

    def keys(self):
        return self.properties.keys()

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

    def __contains__(self, item):
        """
        Just a passthrough to the properties for ease of use
        :param item:
        :return: True if item is in , False if not
        :rtype: bool
        """
        return item in self.properties

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent: str):
        self._parent = parent
        self.properties['parent'] = parent

    @property
    def predicate_inheritance(self):
        return self._predicate_inheritance

    @predicate_inheritance.setter
    def predicate_inheritance(self, status: bool):
        try:
            self._predicate_inheritance = bool(status)
            self.properties['predicate_inheritance'] = self._predicate_inheritance
        except TypeError:
            logger.warning("SpchtBuilder::SimpleSpchtNode: set predicate_inheritance encountered non-bool-able value")

    def import_dictionary(self, data: dict):
        # this is like the worst import procedure i can imagine, it checks nothing
        for key in data:
            try:
                self[key] = data[key]
            except KeyError:
                if key == "parent" and isinstance(data['parent'], str):
                    self.parent = data['parent']
                if key == "predicate_inheritance" and isinstance(data['predicate_inheritance'], bool):
                    self.predicate_inheritance = data['predicate_inheritance']


class SpchtBuilder:

    def __init__(self, import_dict=None, unique_names=None, spcht_base_path=None):
        self._repository = {}
        self.root = SimpleSpchtNode(":ROOT:", parent=":ROOT:", source="", field="")
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

    def __repr__(self):
        representation = f"Len: {len(self._repository)}, {self.cwd=} || "
        representation += repr(self.root) + " || "
        representation += " | ".join([repr(x) for x in self._repository.values()])
        return representation

    def structure_hash(self, raw=False):
        """
        basically does the same as __repr__ but omits the mentioning of names that are not all that relevant, used in
        unit tests to compare nodes on differences..which has the side effect that it only needs to be machine readable
        which then lead to my decision to only give a hash in the end...which makes it terrible to actually see where
        the differences are..therefore it has an alt mode where it just shows where the problem is
        :param bool raw: if True gives the actual string and not an hash
        :return: a long string describing a node
        :rtype: str
        """
        pass

    def node_hash(self, node: str, raw=False):
        """
        Omits all mentions of names & parents from a node structure so they can be compared without getting the
        fluff in the way, basically just utilizes "compile_node
        :param str node:
        :param bool raw:
        :return:
        :rtype:
        """
        if node not in self._repository:
            return None
        return self.compileNode(node)

    def __getitem__(self, item):
        if item in self._repository:
            return self._repository[item]
        else:
            raise KeyError(f"SpchtBuilder::Cannot access key '{item}'.")

    def __contains__(self, item) -> bool:  # mirror mirror
        return item in self._repository

    def __iter__(self):
        return self._repository.__iter__()

    def get(self, key, default=None):
        if key in self.repository:
            return self.repository[key]
        else:
            return default

    def values(self):
        return self._repository.values()

    def items(self):
        return self._repository.items()

    def keys(self):
        return self._repository.keys()

    def add(self, input_node: SimpleSpchtNode):
        """
        Adds a SimpleSpchtNode to the Builder
        :param SimpleSpchtNode input_node:
        :return: the name of the added node (might be different than the inputed one)
        :rtype: str
        """
        uniq_sp_node = copy.deepcopy(input_node)  # in case you want to preserve the original node for some reason
        if not self._check_ancestry(input_node):
            return None
        uniq_sp_node['name'] = self.createNewName(uniq_sp_node['name'])
        """
        for key in SpchtConstants.BUILDER_LIST_REFERENCE:
            if key in uniq_sp_node:
                uniq_sp_node[key] = self.createNewName(uniq_sp_node[key], mode="add")
        for key in SpchtConstants.BUILDER_SINGLE_REFERENCE:  # for now just throw away nodes, maybe implement duplicate
            if key in uniq_sp_node:                       # for recursion
                uniq_sp_node.pop(key, None)
        # ?  the following lines were present before i added mendFamily()
        if uniq_sp_node['parent'] not in self:  # aka its a direct ancestor
            uniq_sp_node.parent = ":UNUSED:"
        if UniqueSpchtNode['name'] in self._repository:
            raise KeyError("Cannot add a name that is already inside")
        """
        self._repository[uniq_sp_node['name']] = uniq_sp_node
        return uniq_sp_node['name']

    def remove(self, UniqueName: str):
        # removes one specific key as long as it isnt referenced anywhere
        for field in SpchtConstants.BUILDER_SINGLE_REFERENCE:
            if field in self[UniqueName]: # actually this is only fallback, will set anyone who is fallback of this to Main
                self[self[UniqueName][field]].parent = ":MAIN:"
        chainbreakers = []
        for field in SpchtConstants.BUILDER_LIST_REFERENCE:
            if field in self[UniqueName]:
                chainbreakers.append(self[UniqueName][field])
        for name in self:
            # ? to assign multiple fields to one node a field name is created that is just ever expressed as the value
            # ? of sub_data and sub_nodes, therefore child element have to hear from this
            for unreal_field in chainbreakers:
                if self[name].parent == unreal_field:
                    self[name].parent = ":UNUSED:"

        self._repository.pop(UniqueName)

    def clone(self, node_name: str, parent_overwrite=None) -> str:
        """
        Clones a given node in the SpchtBuilder, if there are any children or even sub-data/sub-nodes those will be
        copied aswell and linked relativly to this node. If this node is fallback of something :UNUSED: will be the new
        parent, otherwise
        :param str node_name: Name of a node inside the SpchtBuilder
        :param str parent_overwrite:  This can be used recursivly, if parent overwrite is active, parent wont be replaced
        :return: the name of the new node
        :rtype: str
        """
        if node_name not in self:
            raise KeyError(f"Cannot clone node {node_name} as it does not exist")

        new_node = copy.deepcopy(self[node_name])
        new_name = self.createNewName(new_node['name'], mode="number")
        new_node['name'] = new_name
        if new_node.parent in self:  # aka. its a fallback of something
            new_node.parent = ":UNUSED:"
        if parent_overwrite:
            new_node.parent = parent_overwrite
        # if parent :MAIN: it stays :MAIN:, same for :UNUSED:, if part of sub_node/sub_data stays aswell
        for ref in SpchtConstants.BUILDER_SINGLE_REFERENCE:
            if ref in new_node:
                new_node[ref] = self.clone(self[node_name][ref], parent_overwrite=new_name)
        for ref in SpchtConstants.BUILDER_LIST_REFERENCE:
            if ref in new_node:
                new_node[ref] = self.createNewName(new_node[ref], mode="number")
                old_keys = [x for x in self.keys() if self[x].parent == self[node_name][ref]]
                for node in old_keys:
                    self.clone(node, parent_overwrite=new_node[ref])
        self._repository[new_name] = new_node
        return new_name

    def modify(self, OriginalName: str, UniqueSpchtNode: SimpleSpchtNode):
        """
        Modifies a node in the repository with a new Node. The actual new name if changed might be different from
        what was given due the uniqueness rule
        :param str OriginalName: name of the node that is about to be changed
        :param SimpleSpchtNode UniqueSpchtNode: a complete node
        :return: The Name of the new node
        :rtype: str
        """
        if OriginalName not in self:
            raise KeyError(f"Cannot update node {OriginalName} as it does not exist")
        # ! reinstate fallback relationships
        if OriginalName != UniqueSpchtNode['name']:
            # ? this is actually a rather hard decision, do i want to discard the name automatically or give choice to the user?
            # if UniqueSpchtNode['name'] in self._repository:
            #    raise SpchtErrors.OperationalError("Cannot modify node with new name as another node already exists")
            UniqueSpchtNode['name'] = self.createNewName(UniqueSpchtNode['name'])

        # ! you can actually set a node to be its own parent, it wont be exported that ways as no recursion will find it
        # ! if you manually set a node a parent that already has a fallback that relationship will be usurped
        old_fallback = self[OriginalName].get('fallback', None)
        new_fallback = UniqueSpchtNode.get('fallback', None)
        if old_fallback or new_fallback:
            if old_fallback in self and old_fallback != new_fallback:
                self[old_fallback].parent = ":UNUSED:"
            if new_fallback in self:
                self[new_fallback].parent = UniqueSpchtNode['name']
                for name, node in self.items():
                    if 'fallback' in node and node['fallback'] == new_fallback:
                        node.pop('fallback', "")  # in case old == new this is of no consequence and gets overwritten in the end
        # * consistency check - i had a random bug that my interface set the parent to nothing / :MAIN: and i got aware
        # * the fallbacking node does not know about this, therefore we have to account for that
        if (self[OriginalName].parent != UniqueSpchtNode.parent and            # ? so this is over specific, actually it
                self[OriginalName].parent in self and                          # ? would be enough to just check if
                'fallback' in self[self[OriginalName].parent] and              # ? parent is in self for fallback
                self[self[OriginalName].parent]['fallback'] == OriginalName):  # bracket style ifs in python are quite rare..seems weird, would work without
            self[self[OriginalName].parent].pop('fallback', None)

        # * updating of references - quite similar to fallback but not based on name
        for prop in SpchtConstants.BUILDER_LIST_REFERENCE:
            old_node = self[OriginalName].get(prop, None)
            new_node = UniqueSpchtNode.get(prop, None)
            if old_node:
                for key, node in self.items():
                    if not new_node and node.parent == old_node:  # basically deleting the old node
                        node.parent = ":UNUSED:"
                    if new_node and node.parent == old_node:  # reassigning to the renamed
                        node.parent = new_node

        if OriginalName != UniqueSpchtNode['name']:  # * second time we do this because the fallback fix from above needed the name earlier
            for name, node in self.items():  # updates referenced names
                for key in SpchtConstants.BUILDER_REFERENCING_KEYS:
                    if key in node and node[key] == OriginalName:
                        node[key] = UniqueSpchtNode['name']
            self._repository.pop(OriginalName)  # i have not implemented pop for this one occasion
        self._repository[UniqueSpchtNode['name']] = UniqueSpchtNode  # also not set item because .modify is the way
        # * replace predicate
        if UniqueSpchtNode.predicate_inheritance:  # tl;dr: if you are a fallback your predicate gets overwritten if not stated otherwise
            if self[UniqueSpchtNode['name']].parent in self and self[UniqueSpchtNode['name']].parent not in RESERVED_NAMES:
                if 'fallback' in self[self[UniqueSpchtNode['name']].parent] and self[self[UniqueSpchtNode['name']].parent]['fallback'] == UniqueSpchtNode['name']:
                    self[UniqueSpchtNode['name']]['predicate'] = self[self[UniqueSpchtNode['name']].parent]['predicate']
        return UniqueSpchtNode['name']

    def getNodesByParent(self, parent):
        """

        :param parent:
        :type parent:
        :return: a copy of the SimpleSpchtNode Object with the designated partent if its exist
        :rtype: SimpleSpchtNode
        """
        children = []
        for node in self.values():
            if node.parent == parent:
                children.append(copy.copy(node))
        return children

    def exportDict(self):
        a = dict()
        a['meta'] = {'created': str(datetime.date.today().isoformat())}
        b = dict()
        b[':ROOT:'] = self.root.properties
        b[':ROOT:']['parent'] = self.root.parent
        for key in self:
            b[key] = self[key].properties
            b[key]['parent'] = self[key].parent
            b[key]['predicate_inheritance'] = self[key].predicate_inheritance
        a['nodes'] = b
        a['references'] = self._references  # all referenced data that could be loaded
        return a

    def importDict(self, spchtbuilder_point_json: dict):
        """
        This is basically the "load from file" option when having an exported SpchtBuilder file, not to be confused
        with a readily "compiled" Spcht file that can be just executed by Spcht, the Builder can, in theory be im &
        exported back and forth to SpchtBuilder and normal Spcht but this format preserves some settings that the other
        does not. In Theory this should make no difference, and yet the option exists.
        :param dict spchtbuilder_point_json: the entire raw content of a SpchtBuilder file after interpret by json
        :return: True if everything went okay, False if something failed
        :rtype: bool
        """
        # TODO: make this throw exceptions to better gauge the reason for rejection
        if not SpchtUtility.is_dictkey(spchtbuilder_point_json, "nodes", "references"):
            logging.error(f"SpchtBuilder>importDict: data does not contain 'node' and/or 'references'.")
            return False
        # sanity check for references
        if not isinstance(spchtbuilder_point_json['references'], dict) or\
                not isinstance(spchtbuilder_point_json['nodes'], dict):
            logging.error(f"SpchtBuilder>importDict: 'node' and/or 'references are of wrong type")
            return False
        # check for duplicates
        uniques = set()
        for name in spchtbuilder_point_json['nodes']:
            if name in uniques:
                logging.error(f"SpchtBuilder>importDict: not all node names are unique, manual fix needed")
                return False
            uniques.add(name)
            for groups in SpchtConstants.BUILDER_LIST_REFERENCE:  # sub_nodes & sub_data
                if groups in spchtbuilder_point_json['nodes'][name]:
                    uniques.add(spchtbuilder_point_json['nodes'][name][groups])
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
                    logging.error(f"SpchtBuilder>importDict: at least one references contains the wrong data type")
                    return False
                self._references[ref][key] = value
        self._enrichPredicates()
        self.mendFamily()
        return True

    def createSpcht(self):
        # exports an actual Spcht dictionary
        root_node = {"id_source": self.root['source'],
                     "id_field": self.root['field'],
                     "nodes": self.compileSpcht(purity=True)}
        if 'append' in self.root and self.root['append'].strio() != "":
            root_node['id_subject_prefix'] = self.root['append']
        if 'fallback' in self.root:
            fallback = self.compileNodeByParent(":ROOT:", purity=True)
            root_node.update({'id_fallback': fallback[0]})
        return root_node

    def compileSpcht(self, purity=False):
        # exports a compiled Spcht dictionary with all references solved
        # this still misses the root node
        return self.compileNodeByParent(":MAIN:", purity=purity)

    def compileNodeByParent(self, parent: str, mode="conservative", always_inherit=False, purity=False) -> list:
        """
        Compiles a node by common parent, has two modes:

        * conservative (default) - will discard all nodes that do not possess the minimum Spcht requirements
        * reckless - will add any node, regardless if the resulting spcht might not be useable
        :param str parent:
        :type parent:
        :param str mode: either 'conservative' or 'reckless' for node adding behaviour
        :param always_inherit: if True this will ignore faulty inheritance settings
        :param bool purity: for export only, throws all non-format keys away
        :return: a list of nodes
        :rtype: list
        """
        parent = str(parent)
        node_list = []
        for key, top_node in self.items():
            if top_node.parent == parent:
                one_node = self.compileNode(key, always_inherit, purity=purity)
                if mode == "reckless":
                    node_list.append(one_node)
                else:
                    # * this has the potential to wreck entire chains if the top node is incorrect
                    if not SpchtUtility.is_dictkey(one_node, "field", "source"):
                        continue
                    if 'predicate' not in self[key] or self[key]['predicate'].strip() == "":
                        # if for some reasons there is no predicate AND the default true inheritance setting is False
                        # this node is obviously faulty and has to be ignored, this can only happen if someone
                        # would recklessly modify the Nodes in the repository without using .modify...i think
                        if 'predicate_inheritance' in one_node and not one_node['predicate_inheritance']:
                            continue
                    if str(one_node['field']).strip() == "":
                        continue
                    node_list.append(one_node)
        return node_list

    def compileNode(self, name: str, always_inherit=False, purity=False, anon=False):
        name = str(name)
        if name not in self:
            return None
        pure_dict = {}
        for key, item in self[name].items():
            if key in SpchtConstants.BUILDER_LIST_REFERENCE:  # sub_nodes & sub_data
                node_group = []
                for child_node in self.getNodesByParent(item):
                    node_group.append(self.compileNode(child_node['name'], always_inherit=always_inherit, purity=purity, anon=anon))
                pure_dict[key] = node_group
            elif key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                pure_dict[key] = self.compileNode(item, always_inherit=always_inherit, purity=purity, anon=anon)
            elif key in SpchtConstants.BUILDER_NON_SPCHT:
                continue
            else:
                pure_dict[key] = item
        parent_predicate = self.inheritPredicate(name)
        if parent_predicate:
            if pure_dict.get('predicate_inheritance', False):  # can only inherit if being fallback
                pure_dict.pop('predicate')
            if pure_dict.get('predicate', "").strip == "" and always_inherit:
                pure_dict['predicate'] = parent_predicate
        if purity:
            pure_dict.pop('parent', None)
            pure_dict.pop('predicate_inheritance', None)
            for high_key, default_val in {'predicate': '', 'source': 'dict', 'field': '', 'required': 'optional'}.items():
                if high_key not in pure_dict:
                    pure_dict[high_key] = default_val
        else:
            pure_dict['parent'] = self[name].parent
        if anon:  # removes individual properties of a node (for unit testing mostly)
            pure_dict.pop('name', None)
        return pure_dict

    def inheritPredicate(self, sub_node_name: str):
        """
        Fallbacks are not required to have the predicate redefined as those get inherited from the parent,

        This will fail horribly when used on something that actually has no parent in its chain
        :param sub_node_name: unique name of that sub_node
        :type sub_node_name: str
        :return: a predicate
        :rtype: str
        """
        try:
            if 'predicate' not in self[sub_node_name] or self[sub_node_name]['predicate'].strip() == "":
                if self[sub_node_name].parent not in self or self[sub_node_name].parent in RESERVED_NAMES:
                    return ""
                elif 'fallback' in self[self[sub_node_name].parent] and self[self[sub_node_name].parent]['fallback'] == sub_node_name:
                    return self.inheritPredicate(self[sub_node_name].parent)
                else:
                    return ""
            else:
                return self[sub_node_name]['predicate']
        except KeyError as e:
            logging.warning(f"Could not inherit predicate for {sub_node_name} - {e}")
            return ""

    def displaySpcht(self):
        # gives a reprensentation for SpchtCheckerGui
        curated_keys = ["name", "source", "field", "type", "mandatory", "sub_nodes", "sub_data", "predicate", "fallback", "comment"]
        grouped_dict = defaultdict(list)
        for node, each in self.items():
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
        """
        This imports an actual Spcht file, not a SpchtBuilder but a ready and interpreteable Spcht file that can be
        used to process data. For this to work some additional data has to be created on the fly.

        There are historical reasons that a Spcht file works differently than a builder. While processing the original
        Spcht logic just crawls down the Spcht structure and uses data as it comes. For this a nested tree structure
        is of advantage. For editing purpose a nested structure is less than practical. SpchtBuilder is therefore
        inherently flat so it can be displayed in an GUI program without going in depths. For this to work the properties
        of the tree have to be coded in some way. This is achieved by using unique names for each node and subnode, for
        Spcht itself names are an optional parameter, created as afterthough to get some order going, for SpchtBuilder
        names are paramount and are the link between nodes. As Spcht was originally designed to be written by hand one
        cannot assume every single file contains names, the import process creates new names as it sees fit and also
        puts the referenced data in the files.
        :param dict spcht: a read file, interpreted by json.decode
        :param str or None base_path: defines the working directory of the Spcht, needed for references
        :raises SpchtErrors.ParsingError: in cases of reading error
        :return: True if everything was alright
        :rtype: bool
        """
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
        self._enrichPredicates()
        return True

    def _recursiveSpchtImport(self, spcht_nodes: list, base_path: str, parent=":MAIN:") -> dict:
        """
        Imports a dictionary object as a spcht structure, for a moment this will create an partially
        defined spcht with loose nodes which has to be repaired / mended with "mendFamily"

        This will add almost empty nodes to the self structure so that name-duplicate checking can succeed,
        but the procedure is meant to overwrite everything afterwards

        :param list spcht_nodes: list of dictionary nodes
        :param str base_path: file base for references
        :param str parent: name of parent
        :return: SpchtBuilder Repository
        :rtype: dict
        """
        temp_spcht = {}
        for node in spcht_nodes:
            if 'name' not in node:
                name = self._names.giveName()
            elif 'name' in node and str(node['name']).strip() == "":
                name = self._names.giveName()
            else:
                name = node['name']
            name = self.createNewName(name, "number")
            new_node = SimpleSpchtNode(name, parent=parent)
            self._repository[name] = new_node
            for key in SpchtConstants.BUILDER_KEYS.keys():
                if key in node and key != "name":
                    if key in SpchtConstants.BUILDER_LIST_REFERENCE:  # sub_nodes & sub_data
                        new_group = self._names.giveName()
                        new_group = self.createNewName(new_group, "replace")
                        new_node[key] = new_group
                        temp_spcht.update(self._recursiveSpchtImport(node[key], base_path, parent=new_group))
                    elif key in SpchtConstants.BUILDER_SINGLE_REFERENCE:  # fallback
                        list_of_one = self._recursiveSpchtImport([node[key]], base_path, parent=name)
                        # ? lemme explained this abomination that follows, as of Python 3.7 dictionaries are ordered
                        # ? when having nested fallbacks you get something similar to an avalanche when walking back
                        # ? from the recursion, as the element that got the previous fallback as child is always the
                        # ? last to be added its also the last in the dictionary, its not super trivial to call the
                        # ? last element of a dictionary but this seems to be the easiests way, it should never be
                        # ? long, therefore i did not even check how the performance is
                        new_node[key] = list_of_one[list(list_of_one.keys())[-1]]['name']
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
                new_node['comment'] = comments[:-1]  # overwrites the temporary added with the enriched one
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

    def parkNode(self, node_name: str) -> bool:
        """
        Parks a node in the :UNUSED: category so that it does not get exported to a spcht file but is still available
        If the node is already parked it gets reassigned to :MAIN:
        :param str node_name: unique name of an existing node
        :return: Returns true if the parking actually suceeded
        :rtype: bool
        """
        if node_name not in self:
            raise KeyError(f"SpchtBuilder::Cannot access element '{node_name}'.")
        print(self._repository[node_name].parent)
        if self[node_name].parent == ":MAIN:":
            self[node_name].parent = ":UNUSED:"
        elif self[node_name].parent == ":UNUSED:":
            print("unused")
            self[node_name].parent = ":MAIN:"
        else:
            return False
        return True

    def getSolidParents(self):
        return [key for key in self]  # is this not the same as self.keys()?

    def getChildlessParents(self):
        """
        Finds all parent objects that are actual nodes and do not already possess a fallback
        :return: list of all nodes without fallback
        :rtype: list
        """
        return [x for x in self if 'fallback' not in self[x]]

    def getSubnodeParents(self):
        names = []
        for node in self.values():
            if 'sub_nodes' in node.properties:
                names.append(node.properties['sub_nodes'])
        return names

    def getSubdataParents(self):
        names = []
        for node in self.values():
            if 'sub_data' in node.properties:
                names.append(node.properties['sub_data'])
        return names

    def getAllSubParents(self):
        names = set()
        for node in self.values():
            for key in SpchtConstants.BUILDER_LIST_REFERENCE:
                if key in node.properties:
                    names.add(node.properties[key])
        return list(names)

    def getAllParents(self):
        names = []
        for key, node in self.items():
            if 'sub_data' in node.properties:
                names.append(node.properties['sub_data'])
            if 'sub_nodes' in node.properties:
                names.append(node.properties['sub_nodes'])
            names.append(key)
        return names

    def _enrichPredicates(self):
        """
        This solves a meta problem. In the original version, handwritten fallbacks wont have their own predicate
        as the schema doesnt demand them and it would be illogical to have a different predicate for a fallback node,
        but as a fallback node is not lesser than any other one node it can have its own predicate. The Spcht script
        just inherits the predicate from its direct ancestor, the Gui program does the same but this means, if you
        somewhen down the line change the predicate and still have fallbacks, those wont change with them, this is now
        the default, as long as the link exists a change in the predicate of a node that has fallbacks will also change
        the predicate of all fallback nodes, EXCEPT there is an extra flag set to not do so. This flag has to be
        initialized somewhere, and this is the moment, used right after importing data
        :return: nothing
        :rtype: nothing
        """
        for name, node in self.items():
            if node.parent not in self or node.parent in RESERVED_NAMES:
                continue
            if 'predicate' not in node or node['predicate'].strip() == "":
                self[name]['predicate'] = ""
                if 'fallback' in self[node.parent] and self[node.parent]['fallback'] == name:
                    self[name]['predicate'] = self.inheritPredicate(name)
                    self[name].predicate_inheritance = True
            else:
                if 'fallback' in self[node.parent] and self[node.parent]['fallback'] == name:
                    if node['predicate'] != self[node.parent]['predicate']:
                        self[name].predicate_inheritance = False

    def _check_ancestry(self, node: SimpleSpchtNode):
        """
        A simple Spcht Node just is, there are no checks and balances to make sure that an individual one has a real
        parent or an realistic sibling relationship. We can only check this in the context of an already established
        builder (which puts up some restriction in the order we can actually add content to the builder as we need
        to walk down the tree path starting from :MAIN:

        Note: this contains a superflous amount of `return False` for clarity

        :param SimpleSpchtNode node:
        :return: True if the proposed relationship is possible, False if not
        :rtype: bool
        """
        if node.parent == ":UNUSED:" or node.parent == ":MAIN:":  # the default case if something is just on the base
            for node in self.values():
                if 'fallback' in node:
                    if node['fallback'] == node['name']:
                        return False  # discrepancy as node cannot be different if other node claims this one
            return True
        elif node.parent in self:  # direct ancestor aka. Fallback
            if 'fallback' not in self[node.parent]:
                return False
            else:  # else for clarity reasons
                if node['name'] not in self:  # the name is still free and can just be added
                    if self[node.parent]['fallback'] != node['name']:
                        return False
                    else:
                        return True
                else:  # the name already exists, this new node will get a different one
                    return False
        else:  # no reason to not add
            return True
            # sub_list = self.getAllSubParents()
            # if node.parent in sub_list:  # * this is illogical, the element containing the parent might not be added yet
            #     return True
            # return False

    def mendFamily(self):
        """
        Utility procedure that tries to repair some links that might not be established by wrongly inputed data

        * A node is fallback of another node but its parent is :MAIN: or :UNUSED:, in that case the relationship
          can easily be overwritten
        * A node has a fallback that just doesnt exist in the repository, this connection cannot be used in this
          case and the dead link will be removed

        The second occassion is the reason why this should only be used after a full import of all data has taken place

        :return: return a list of repaired nodes
        :rtype: list
        """
        sub_list = self.getAllSubParents()
        repair = []
        for name, node in self.items():
            for key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                if key in node:
                    if node[key] not in self:
                        self[name].pop(key)
                    else:
                        if self[node[key]].parent != name:
                            if self[node[key]].parent == ":MAIN:" or self[node[key]].parent == ":UNUSED:":
                                self[node[key]].parent = name
                                repair.append(self[node[key]])
                            else:  # another node claims inheritance?
                                if self[node[key]].parent in self:
                                    for key2 in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                                        if key2 in self[self[node[key]].parent]:
                                            if self[self[node[key]].parent][key2] == self[node[key]]:
                                                raise SpchtErrors.DataError("Family structure of builder is broken")
                                    # ? if we get here without exception there seems to not be any match and we can repair
                                    self[node[key]].parent = name
                                    repair.append(node[key])
                                else:  # the supposed node does not exist in the repository, so we can overwrite
                                    self[node[key]].parent = name
                                    repair.append(node[key])
            if node.parent != ":UNUSED:" and node.parent != ":MAIN:":
                if node.parent in sub_list:  # list reference can contain any number of elements, should always be fine
                    continue
                elif node.parent in self:
                    for key in SpchtConstants.BUILDER_SINGLE_REFERENCE:
                        if self[node.parent][key] == name:
                            break
                    else:  # python tricks, if for runs through without stops else triggers
                        # ? if we get here the parent relationship is empty
                        self[name].parent = ":UNUSED:"
                        repair.append(name)
                else:  # the supposed parent doesnt exist anyway
                    self[name].parent = ":UNUSED:"
                    repair.append(name)
        return repair

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
        if name in RESERVED_NAMES:  # using a reserved name gets you a new one right from the repository
            name = self._names.giveName()
            return self.createNewName(name, mode, alt_repository)
        all_clear = False  # i fear this is the easiest way, but i am not happy with it
        if alt_repository:
            for key in alt_repository:
                if key == name:
                    break
                if hasattr(alt_repository[key], "parent"):  # theoretically this has not to be a dict of SimpleSpchtNodes
                    if alt_repository[key].parent == name:
                        break
            else:
                all_clear = True  # when loops goes through without break
            if name not in alt_repository:
                return name
        else:  # checks for direct names and duplicated parent names
            for key in self:
                if key == name:
                    break
                if self[key].parent == name:
                    break
            else:
                all_clear = True
        if all_clear:
            return name
        # ! in case a duplicate was found
        if mode == "number":
            found = re.search(r"[0-9]+$", name)
            if found:
                pos0 = found.regs[0][0]
                num = str(int(found.group(0))+1)
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



