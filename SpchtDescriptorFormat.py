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

import copy
import json
import os
import re
import sys
from pathlib import Path

import SpchtUtility
from SpchtUtility import if_possible_make_this_numerical, insert_list_into_str, extract_dictmarc_value

import SpchtErrors
try:
    from termcolor import colored  # only needed for debug print
except ModuleNotFoundError:
    def colored(text, *args):
        return text  # throws args away returns non colored text

import logging
logger = logging.getLogger(__name__)


class Spcht:
    def __init__(self, filename=None, check_format=False, debug=False):
        self._DESCRI = None  # the finally loaded descriptor file with all references solved
        self._SAVEAS = {}
        # * i do all this to make it more customizable, maybe it will never be needed, but i like having options
        self.std_out = sys.stdout
        self.std_err = sys.stderr
        self.debug_out = sys.stdout
        self._debug = debug
        self.default_fields = ['fullrecord']
        self.descriptor_file = None
        if filename is not None:
            if not self.load_descriptor_file(filename):
                raise FileNotFoundError("Something with the specified Spcht file was wrong")

        # does absolutely nothing in itself

    def __repr__(self):
        if len(self._DESCRI) > 0:
            some_text = ""
            for item in self._DESCRI['nodes']:
                some_text += "{}[{},{}] - ".format(item['field'], item['source'], item['required'])
            return some_text[:-3]
        else:
            return "Empty Spcht"

    def __str__(self):
        if self.descriptor_file is not None:
            return f"SPCHT{{{self.descriptor_file}}}"
        else:
            return "SPCHT{_empty_}"

    def __bool__(self):
        if self._DESCRI is not None:
            return True
        else:
            return False

    def __iter__(self):
        return SpchtIterator(self)

    def processData(self, raw_dict, graph, marc21="fullrecord", marc21_source="dict"):
        """
            takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
            per default it assumes there is a marc entry in the solrdump but it can be provided directly
            it also takes technically any dictionary with entries as input

            :param dict raw_dict: a flat dictionary containing a key sorted list of values to be processes
            :param str graph: beginning of the assigned graph all entries become triples of
            :param str marc21: the raw_dict dictionary key that contains additional marc21 data
            :param str marc21_source: source for marc21 data
            :return: a list of tuples with 4 entries (subject, predicat, object, bit) - bit = 1 -> object is another triple. Returns True if absolutly nothing was matched but the process was a success otherwise. False if something didnt worked
            :rtype: list or bool
        """
        # spcht descriptor format - sdf
        # ! this is temporarily here, i am not sure how i want to handle the descriptor dictionary for now
        # ! there might be a use case to have a different mapping file for every single call instead of a global one

        # most elemental check
        if not self:
            return False
        # Preparation of Data to make it more handy in the further processing
        marc21_record = None  # setting a default here
        if marc21_source.lower() == "dict":
            try:
                marc21_record = SpchtUtility.marc2list(raw_dict.get(marc21))
            except AttributeError as e:
                self.debug_print("AttributeError:", colored(e, "red"))
                logger.error(f"Marc21 could not be loaded due an AttributeError: {e}")
                marc21_record = None
            except ValueError as e:  # something is up
                self.debug_print("ValueException:", colored(e, "red"))
                marc21_record = None
            except TypeError as e:
                self.debug_print(f"TypeException: (in {raw_dict.get('kxp_id_str', '')}", colored(e, "red"))
                marc21_record = None
        elif marc21_source.lower() == "none":
            pass  # this is more a nod to anyone reading this than actually doing anything
        else:
            raise SpchtErrors.UndefinedError("The choosen Source option doesnt exists")
            # ? what if there are just no marc data and we know that in advance?
        # generate core graph, i presume we already checked the spcht for being correct
        # ? instead of making one hard coded go i could insert a special round of the general loop right?
        sub_dict = {
            "name": "$Identifier$",  # this does nothing functional but gives the debug text a non-empty string
            "source": self._DESCRI['id_source'],
            "graph": "none",  # recursion node presumes a graph but we dont have that for the root, this is a dummy
            "field": self._DESCRI['id_field'],
            "subfield": self._DESCRI.get('id_subfield', None),
            # i am aware that .get returns none anyway, this is about you
            "alternatives": self._DESCRI.get('id_alternatives', None),
            "fallback": self._DESCRI.get('id_fallback', None)
        }
        # ? what happens if there is more than one resource?
        ressource = self._recursion_node(sub_dict, raw_dict, marc21_record)
        if isinstance(ressource, list) and len(ressource) == 1:
            ressource = ressource[0][1]
            self.debug_print("Ressource", colored(ressource, "green", attrs=["bold"]))
        else:
            self.debug_print("ERROR", colored(ressource, "green"))
            raise TypeError("More than one ID found, SPCHT File unclear?")
        if ressource is None:
            raise ValueError("Ressource ID could not be found, aborting this entry")

        triple_list = []
        for node in self._DESCRI['nodes']:
            facet = self._recursion_node(node, raw_dict, marc21_record)
            # ! Data Output Modelling Try 2
            if node.get('type', "literal") == "triple":
                node_status = 1
            else:
                node_status = 0
            # * mandatory checks
            # there are two ways i could have done this, either this or having the checks split up in every case
            if facet is None:
                if node['required'] == "mandatory":
                    raise SpchtErrors.MandatoryError(f"Field {node['field']} is a mandatory field but not present")
                else:
                    continue  # nothing happens
            else:
                if isinstance(facet, tuple):
                    if facet[1] is None:  # all those string checks
                        if node['required'] == "mandatory":
                            self.debug_print(colored(f"{node.get('name')} is an empty, mandatory string"), "red")
                            raise SpchtErrors.MandatoryError(f"Field {node['field']} is a mandatory field but not present")
                        else:
                            continue  # we did everything but found nothing, this happens
                elif isinstance(facet, list):
                    at_least_something = False  # i could have juxtaposition this to save a "not"
                    for each in facet:
                        if each[1] is not None:
                            at_least_something = True
                            break
                    if not at_least_something:
                        if node['required'] == "mandatory":
                            self.debug_print(colored(f"{node.get('name')} is an empty, mandatory list"), "red")
                            raise SpchtErrors.MandatoryError(f"Field {node['field']} is a mandatory field but not present")
                            # there are checks before this, so this should, theoretically, not happen
                        else:
                            continue
                else:  # whatever it is, its weird if this ever happens
                    if node['required'] == "mandatory":
                        return False
                    else:
                        print(facet, colored("I cannot handle that for the moment", "magenta"), file=self.std_err)
                        raise SpchtErrors.Unexpected("Unexpected return from recursive processor, this shouldnt happen")

            # * data output - singular form
            if isinstance(facet, tuple):
                triple_list.append(((graph + ressource), facet[0], facet[1], node_status))
                # tuple form of 4
                # [0] the identifier
                # [1] the object name
                # [2] the value or graph
                # [3] meta info whether its a graph or a literal
            # * data output - list form
            elif isinstance(facet, list):  # list of tuples form
                for each in facet:  # this is a new thing, me naming the variable "each", i dont know why
                    if each[1] is not None:
                        triple_list.append(((graph + ressource), each[0], each[1], node_status))
                    # here was a check for empty elements, but we already know that not all are empty
                    # this should NEVER return an empty list cause the mandatory check above checks for that
        return triple_list  # * can be empty []
    # TODO: Error logs for known error entries and total failures as statistic

    def debug_print(self, *args, **kwargs):
        """
            prints only text if debug flag is set, prints to *self._debug_out*

            :param any args: pipes all args to a print function
            :param any kwargs: pipes all kwargs **except** file to a print function
        """
        # i wonder if it would have been easier to just set the out put for
        # normal prints to None and be done with it. Is this better or worse? Probably no sense questioning this
        if self._debug is True:
            if 'file' in kwargs:
                del kwargs['file']  # while handing through all the kwargs we have to make one exception, this seems to work
            print(*args, file=self.debug_out, **kwargs)

    def debugmode(self, status):
        """
            Tooles the debug mode for the instance of SPCHT

            :param bool status: Debugmode is activated if true
            :return: nothing
        """
        # a setter, i really dont like those
        if not isinstance(status, bool) or status is False:
            self._debug = False
        else:
            self._debug = True

    def export_full_descriptor(self, filename, indent=3):
        """
            Exports the ready loaded descriptor as a local json file, this includes all referenced maps, its
            basically a "compiled" version

            :param str filename: Full or relative path to the designated file, will overwrite
            :param int indent: indentation of the json
            :return: True if everything was successful
            :rtype: bool
        """
        if not self:
            return False
        try:
            with open(filename, "w") as outfile:
                json.dump(self._DESCRI, outfile, indent=indent)
        except Exception as e:
            print("File Error", e, file=self.std_err)

    def load_json(self, filename):
        """
            Encapsulates the loading of a json file into a simple command to save  lines
            It also catches most exceptions that might happen
            :param: filename: full path to the file or relative from current position
            :type filename: string
            :return: Returns the loaded object (list or dictionary) or ''False'' if something happend
            :rtype: dict
        """
        try:
            with open(filename, mode='r') as file:
                return json.load(file)
        except FileNotFoundError:
            print("nofile -", filename, file=self.std_err)
            return False
        except ValueError as error:
            print(colored("Error while parsing JSON:\n\r", "red"), error, file=self.std_err)
            return False
        except KeyError:
            print("KeyError", file=self.std_err)
            return False
        except Exception as e:
            print("Unexpected Exception:", e.args, file=self.std_err)
            return False

    def getSaveAs(self, key=None):
        """
            SaveAs key in SPCHT saves the value of the node without prepend or append but with cut and match into a
            list, this list is retrieved with this function. All data is saved inside the SPCHT object. It might get big.

            :param str key: the dictionary key you want to retrieve, if key not present function returns None
            :return: a dictionary of lists with the saved values, or when specified a key, a list of saved values
            :rtype: dict or list or None
        """
        if key is None:
            return self._SAVEAS
        if key in self._SAVEAS:
            return self._SAVEAS[key]
        else:
            return None

    def cleanSaveaAs(self):
        # i originally had this in the "getSaveAs" function, but maybe you have for some reasons the need to do this
        # manually or not at all. i dont know how expensive set to list is. We will find out, eventually
        for key in self._SAVEAS:
            self._SAVEAS[key] = list(set(self._SAVEAS[key]))

    def load_descriptor_file(self, filename):
        """
            Loads the SPCHT Descriptor Format, a file formated as json in a specific structure outlined by the docs.
            Notice that relative paths inside the file are relativ to the excuting script not the SPCHT format file itself
            This might change at later point

            :param str filename: a local file containing the main descriptor file
            :return: Returns the descriptors as dictionary, False if something is wrong, None when pre-checks fail
            :rtype: bool
        """
        # returns None if something is amiss, returns the descriptors as dictionary
        # ? turns out i had to add some complexity starting with the "include" mapping
        descriptor = self.load_json(filename)
        spcht_path = Path(filename)
        self.debug_print("Local Dir:", colored(os.getcwd(), "blue"))
        self.debug_print("Spcht Dir:", colored(spcht_path.parent, "cyan"))
        if isinstance(descriptor, bool):  # load json goes wrong if something is wrong with the json
            return False
        if not SpchtUtility.check_format(descriptor, base_path=spcht_path.parent):
            return False
        # * goes through every mapping node and adds the reference files, which makes me basically rebuild the thing
        # ? python iterations are not with pointers, so this will expose me as programming apprentice but this will work
        new_node = []
        for item in descriptor['nodes']:
            try:
                a_node = self._load_ref_node(item, str(spcht_path.parent))
            except Exception as e:
                self.debug_print("spcht_ref", colored(e, "red"))
                # raise ValueError(f"ValueError while working through Reference Nodes: '{e}'")
                return False
            new_node.append(a_node)
        descriptor['nodes'] = new_node  # replaces the old node with the new, enriched ones
        self._DESCRI = descriptor
        self.descriptor_file = filename
        return True

    def _load_ref_node(self, node_dict: dict, base_path: str) -> dict:
        """
        Loads referenced data (read: external files) in a subnode
        :param dict node_dict: a node dictionary
        :param str base_path: file path prefix in case the descriptor is not in the executable folder
        :return: Returns the changed node dictionary, the loaded data added
        :rtype: dict
        :raises TypeError: if the loaded file is the wrong format
        :raises FileNotFounderror: if the given file could not be found
        """
        # We are again in beautiful world of recursion. Each node can contain a mapping and each mapping can contain
        # a reference to a mapping json. i am actually quite worried that this will lead to performance issues
        # TODO: Research limits for dictionaries and performance bottlenecks
        # so, this returns False and the actual loading operation returns None, this is cause i think, at this moment,
        # that i can check for isinstance easier than for None, i might be wrong and i have not looked into the
        # cost of that operation if that is ever a concern
        if 'fallback' in node_dict:
            try:
                node_dict['fallback'] = self._load_ref_node(node_dict['fallback'], base_path)  # ! there it is again, the cursed recursion thing
            except Exception as e:
                raise e  # basically lowers the exception by one level
        if 'mapping_settings' in node_dict and node_dict['mapping_settings'].get('$ref') is not None:
            file_path = node_dict['mapping_settings']['$ref']  # ? does it always has to be a relative path?
            self.debug_print("Reference:", colored(file_path, "green"))
            try:
                map_dict = self.load_json(os.path.normpath(os.path.join(base_path, file_path)))
            except FileNotFoundError:
                self.debug_print("Reference File not found")
                raise FileNotFoundError(f"Reference File not found: '{file_path}'")
            # iterate through the dict, if manual entries have the same key ignore
            if not isinstance(map_dict, dict):  # we expect a simple, flat dictionary, nothing else
                raise TypeError("Structure of loaded Mapping Settings is incorrect")
            # ! this here is the actual logic that does the thing:
            # there might no mapping key at all
            node_dict['mapping'] = node_dict.get('mapping', {})
            for key, value in map_dict.items():
                if not isinstance(value, str):  # only flat dictionaries, no nodes
                    self.debug_print("spcht_map")
                    raise TypeError("Value of mapping_settings is not a string")
                if key not in node_dict['mapping']:  # existing keys have priority
                    node_dict['mapping'][key] = value
            del map_dict
            # clean up mapping_settings node
            del (node_dict['mapping_settings']['$ref'])
            if len(node_dict['mapping_settings']) <= 0:
                del (node_dict['mapping_settings'])  # if there are no other entries the entire mapping settings goes

        if 'graph_map_ref' in node_dict:  # mostly boiler plate from above, probably not my brightest day
            file_path = node_dict['graph_map_ref']
            map_dict = self.load_json(os.path.normpath(os.path.join(base_path, file_path)))
            if not isinstance(map_dict, dict):
                raise TypeError("Structure of loaded graph_map_reference is not a dictionary")
            node_dict['graph_map'] = node_dict.get('graph_map', {})
            for key, value in map_dict.items():
                if not isinstance(value, str):
                    self.debug_print("spcht_map")
                    raise TypeError("Value of graph_map is not a string")
                node_dict['graph_map'][key] = node_dict['graph_map'].get(key, value)
            del map_dict
            del node_dict['graph_map_ref']

        return node_dict  # whether nothing has had changed or not, this holds true

    def _recursion_node(self, sub_dict: dict, raw_dict: dict, marc21_dict=None):
        """
        Main function of the data processing, this decides how to handle a specific node, gets also called recursivly
        if a node contains a fallback
        :param dict sub_dict: the sub node that describes the behaviour
        :param dict raw_dict: the raw data, usually a flat dictionary (key: str|int|float)
        :param dict marc21_dict: pre-transformed marc21 data in marc21-dictionary format as provided by SpchtUtility.marc2list
        :return:
        :rtype:
        """
        # i do not like the general use of recursion, but for traversing trees this seems the best solution
        # there is actually not so much overhead in python, its more one of those stupid feelings, i googled some
        # random reddit thread: https://old.reddit.com/r/Python/comments/4hkds8/do_you_recommend_using_recursion_in_python_why_or/
        # @param sub_dict = the part of the descriptor dictionary that is in ['fallback']
        # @param raw_dict = the big raw dictionary that we are working with
        # @param marc21_dict = an alternative marc21 dictionary, already cooked and ready
        # the header/id field is special in some sense, therefore there is a separated function for it
        # ! this can return anything, string, list, dictionary, it just takes the content and relays, careful
        # UPDATE 03.08.2020 : i made it so that this returns a tuple of the named graph and the actual value
        # this is so cause i rised the need for manipulating the used named graph for that specific object via
        # mappings, it seemed most forward to change all the output in one central place, and that is here
        if sub_dict.get('name', "") == "$Identifier$":
            self.debug_print(colored("ID Source:", "red"), end=" ")
        else:
            self.debug_print(colored(sub_dict.get('name', ""), "cyan"), end=" ")

        if sub_dict['source'] == "marc":
            if marc21_dict is None:
                self.debug_print(colored("No Marc", "yellow"), end="|")
                pass
            if "if_condition" in sub_dict:  # condition cancels out the entire node, triggers callback
                if not self._handle_if(marc21_dict, sub_dict, 'flexible'):
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)  # ! i created call_fallback just for this

            m21_value = extract_dictmarc_value(marc21_dict, sub_dict)
            if m21_value is None:
                self.debug_print(colored(f"Marc around but not field {sub_dict['field']}", "yellow"), end=" > ")
                return self._call_fallback(sub_dict, raw_dict, marc21_dict)

            self.debug_print(colored("Marc21", "yellow"), end="-> ")  # the first step
            # ? Whats the most important step a man can take? --- Always the next one

            if m21_value is False:  # r"^[0-9]{1,3}:\w*$"
                self.debug_print(colored(f"✗ field found but subfield not present in marc21 dict", "magenta"), end=" > ")
                return self._call_fallback(sub_dict, raw_dict, marc21_dict)

            """Explanation:
            I am rereading this and its quite confusing on the first glance, so here some prose. This assumes three modes,
            either returned value gets replaced by the graph_field function that works like a translation, or it inserts
            something, if it doesnt do  that it does the normal stuff where it adds some parts, divides some and does 
            all the other pre&post processing things. Those 3 modi are exclusive. If any value gets filtered by the 
            if function above we never get here, as of now only one valid value in a list of value is enough to get here
            02.02.2021"""
            if 'graph_field' in sub_dict:  # original boilerplate from dict
                graph_value = self._graph_map(marc21_dict, sub_dict)
                if graph_value is not None:  # ? why i am even checking for that? Fallbacks, that's why, if this fails we end on the bottom of this function
                    self.debug_print(colored("✓ graph_field", "green"))
                    return graph_value
                self.debug_print(colored(f"✗ graph mapping could not be fullfilled", "magenta"), end=" > ")
            elif 'insert_into' in sub_dict:
                inserted_ones = self._inserter_string(marc21_dict, sub_dict)
                if inserted_ones is not None:
                    self.debug_print(colored("✓ insert_into", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], inserted_ones)
                    # ! this handling of the marc format is probably too simply
            else:
                temp_value = Spcht._node_preprocessing(m21_value, sub_dict)
                if temp_value is None or len(temp_value) <= 0:  # not sure how i feal about the explicit check of len<0
                    self.debug_print(colored(f"✗ value preprocessing returned no matches", "magenta"), end=" > ")
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)

                self.debug_print(colored(f"✓ field", "green"))
                temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))

            # TODO: gather more samples of awful marc and process it
        elif sub_dict['source'] == "dict":
            self.debug_print(colored("Source Dict", "yellow"), end="-> ")

            if "if_condition" in sub_dict:  # condition cancels out the entire node, triggers callback
                if not self._handle_if(raw_dict, sub_dict, 'flexible'):
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)  # ! i created call_fallback just for this

            # graph_field matching - some additional checks necessary
            # the existence of graph_field invalidates the rest if graph field does not match
            if "graph_field" in sub_dict:
                # ? i really hope this works like intended, if there is graph_field, do nothing of the normal matching
                graph_value = self._graph_map(raw_dict, sub_dict)
                if graph_value is not None:  # ? why i am even checking for that? Fallbacks, that's why
                    self.debug_print(colored("✓ graph_field", "green"))
                    return graph_value
            # normal field matching
            elif 'insert_into' in sub_dict:  # ? similar to graph field this is an alternate mode
                inserted_ones = self._inserter_string(raw_dict, sub_dict)
                if inserted_ones is not None:
                    self.debug_print(colored("✓ insert_field", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(inserted_ones, sub_dict))
                # ! dont forget post processing
            elif sub_dict['field'] in raw_dict:  # main field name
                temp_value = raw_dict[sub_dict['field']]  # the raw value
                temp_value = Spcht._node_preprocessing(temp_value, sub_dict)  # filters out entries
                if temp_value is not None and len(temp_value) > 0:
                    temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                    self.debug_print(colored("✓ simple field", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))
            # ? since i prime the sub_dict what is even the point for checking the existence of the key, its always there
            # alternatives matching, like field but as a list of alternatives
            elif 'alternatives' in sub_dict and sub_dict['alternatives'] is not None:  # traverse list of alternative field names
                self.debug_print(colored("Alternatives", "yellow"), end="-> ")
                for entry in sub_dict['alternatives']:
                    if entry in raw_dict:
                        temp_value = Spcht._node_preprocessing(raw_dict[entry], sub_dict)
                        if temp_value is not None and len(temp_value) > 0:
                            temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                            self.debug_print(colored("✓ alternative field", "green"))
                            return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))
        return self._call_fallback(sub_dict, raw_dict, marc21_dict)

    def _call_fallback(self, sub_dict, raw_dict, marc21_dict):
        if 'fallback' in sub_dict and sub_dict['fallback'] is not None:  # we only get here if everything else failed
            # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
            # * librarian was who wrote the descriptor format
            self.debug_print(colored("Fallback triggered", "yellow"), end="-> ")
            recursion_node = copy.deepcopy(sub_dict['fallback'])
            if 'graph' not in recursion_node:
                recursion_node['graph'] = sub_dict['graph']  # so in theory you can define new graphs for fallbacks
            return self._recursion_node(recursion_node, raw_dict, marc21_dict)
        else:
            self.debug_print(colored("absolutely nothing", "red"), end=" |\n")
            return None  # usually i return false in these situations, but none seems appropriate

    @staticmethod
    def _node_return_iron(graph: str, subject: list or str) -> list or None:
        """
            Used in processing of content as last step before signing off to the processing functions
            equalizes the output, desired is a format where there is a list of tuples, after the basic steps we normally
            only get a string for the graph but a list for the subject, this makes it so that the graph is copied.
            Only case when there is more than one graph would be the graph_mapping function

            :param graph: the mapped graph for this node
            :param subject: a single mapped string or a list of such
            :rtype: list or none
            :return: a list of tuples where the first entry is the graph and the second the mapped subject
        """
        # this is a simple routine to adjust the output from the nodeprocessing to a more uniform look so that its always
        # a list of tuples that is returned, instead of a tuple made of a string and a list.
        if not isinstance(graph, str):
            raise TypeError("Graph has to be a string")  # ? has it thought?
        if isinstance(subject, int) or isinstance(subject, float) or isinstance(subject, complex):
            subject = str(subject)  # i am feeling kinda bad here, but this should work right? # ? complex numbers?
        if subject is None:
            return None
        if isinstance(subject, str):
            return [(graph, subject)]  # list of one tuple
        if isinstance(subject, list):
            new_list = []
            for each in subject:
                if each is not None:
                    new_list.append((graph, each))
            if len(new_list) > 0:  # at least one not-None element
                return new_list
            else:
                return None
        raise TypeError("Could handle graph, subject pair")

    @staticmethod
    def _node_preprocessing(value: str or list, sub_dict: dict, key_prefix="") -> list or None:
        """
        used in the processing after entries were found, this acts basically as filter for everything that does
        not match the provided regex in sub_dict

        :param str or list value: value of the found field/subfield, can be a list
        :param dict sub_dict: sub dictionary containing a match key, if not nothing happens
        :return: None if not a single match was found, always a list of values, even its just one
        :rtype: list or None
        """
        # if there is a match-filter, this filters out the entry or all entries not matching
        if f'{key_prefix}match' not in sub_dict:
            return value  # the nothing happens clause
        if isinstance(value, str):
            finding = re.search(sub_dict[f'{key_prefix}match'], str(value))
            if finding is not None:
                return [finding.string]
            else:
                return None
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                finding = re.search(sub_dict[f'{key_prefix}match'], str(item))
                if finding is not None:
                    list_of_returns.append(finding.string)
            if len(list_of_returns) <= 0:
                return None
            else:
                return list_of_returns
        else:  # fallback if its anything else i dont intended to handle with this
            raise TypeError(f"SPCHT.node_preprocessing - Found a {type(value)}")
            # return value

    def _node_postprocessing(self, value: str or list, sub_dict: dict, key_prefix="") -> list:
        """
        Used after filtering and mapping took place, this appends the pre and post text before the value if provided,
        further also replaces part of the value with the replacement text or just removes the part that is
        specified by cut if no replacement was provided. Without 'cut' there will be no replacement.
        Order is first replace and cut and THEN appending text

        :param str or list value: the content of the field that got mapped till now
        :param dict sub_dict: the subdictionary of the node containing the 'cut', 'prepend', 'append' and 'replace' key
        :return: returns the same number of provided entries as input, always a list
        :rtype: list
        """
        # after having found a value for a given key and done the appropriate mapping the value gets transformed
        # once more to change it to the provided pattern

        # as i have manipulated the preprocessing there should be no strings anymore
        if isinstance(value, str):
            if f'{key_prefix}cut' in sub_dict:
                value = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), value)
                self._addToSaveAs(value, sub_dict)
            else:
                self._addToSaveAs(value, sub_dict)
            return [sub_dict.get(f'{key_prefix}prepend', "") + value + sub_dict.get(f'{key_prefix}append', "")]
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                if f'{key_prefix}cut' not in sub_dict:
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + str(item) + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._addToSaveAs(item, sub_dict)
                else:
                    pure_filter = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), str(item))
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + pure_filter + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._addToSaveAs(pure_filter, sub_dict)
                list_of_returns.append(rest_str)
            if len(list_of_returns) < 0:
                return None
            return list_of_returns
        else:  # fallback if its anything else i dont intended to handle with this
            return value

    def _node_mapping(self, value, mapping, settings):
        """
        Used in the processing after filtering via match but before the postprocesing. This replaces every matched
        value from a dictionary or the default if no match. Its possible to set the default to inheritance to pass
        the value through

        :param str or list value: the found value in the source, can be also a list of values, usually strings
        :param dict mapping: a dictionary of key:value pairs provided to replace parameter value one by one
        :param dict settings: a set list of settings that were defined in the node
        :return: returns the same number of values as input, might replace all non_matches with the default value. It CAN return None if something funky is going on with the settings and mapping
        :rtype: str or list or None
        """
        the_default = False
        if not isinstance(mapping, dict) or mapping is None:
            return value
        if settings is not None and isinstance(settings, dict):
            if '$default' in settings:
                the_default = settings['$default']
                # if the value is boolean True it gets copied without mapping
                # if the value is a str that is default, False does nothing but preserves the default state of default
                # Python allows me to get three "boolean" states here done, value, yes and no. Yes is inheritance
            if '$type' in settings:
                pass  # placeholder # TODO: regex or rigid matching
        # no big else block cause it would indent everything, i dont like that, and this is best practice anyway right?
        if isinstance(value, list):  # ? repeated dictionary calls not good for performance?
            # ? default is optional, if not is given there can be a discard of the value despite it being here
            # TODO: make 'default': '$inherit' to an actual function
            response_list = []
            for item in value:
                one_entry = mapping.get(item)
                if one_entry is not None:
                    response_list.append(one_entry)
                else:
                    if isinstance(the_default, bool) and the_default is True:
                        response_list.append(item)  # inherit the former value
                    elif isinstance(the_default, str):
                        response_list.append(the_default)  # use default text
                del one_entry
            if len(response_list) > 0:
                return response_list
            elif len(response_list) <= 0 and isinstance(the_default, str):
                # ? i wonder when this even triggers? when giving an empty list? in any other case default is there
                # * caveat here, if there is a list of unknown things there will be only one default
                response_list.append(the_default)  # there is no inheritance here, i mean, what should be inherited? void?
                return response_list
            else:  # if there is no response list but also no defined default, it crashes back to nothing
                return None

        elif isinstance(value, str):
            if value in mapping:  # rigid key mapping
                return mapping.get(value)
            elif isinstance(the_default, bool) and the_default is True:
                return value
            elif isinstance(the_default, str):
                return the_default
            else:
                return None
                # ? i was contemplating whether it should return value or None. None is the better one i think
                # ? cause if we no default is defined we probably have a reason for that right?
                # ! stupid past me, it should throw an exception
        else:
            print("field contains a non-list, non-string: {}".format(type(value)), file=self.std_err)

    def _graph_map(self, raw_dict, sub_dict):
        # originally i had this as part of the node_recursion function, but i encountered the problem
        # where i had to perform a lot of checks till i can actually do anything which in the structure i had
        # would have resulted in a very nested if chain, as a separate function i can do this more neatly and readable
        if extract_dictmarc_value(raw_dict, sub_dict, 'field') is None or \
                extract_dictmarc_value(raw_dict, sub_dict, 'graph_field') is None:
            # this is a bit awkward, dict doesnt check for existence, marc does, neither do for graph_field, hmm
            self.debug_print(colored(f"✗ no field or graph_field not present", "magenta"), end=" > ")
            return None
        field = extract_dictmarc_value(raw_dict, sub_dict, "field")  # this is just here cause i was tired of typing the full thing every time
        graph_field = extract_dictmarc_value(raw_dict, sub_dict, "graph_field")
        # i am not entirely sure that those conjoined tests are all that useful at this place
        if field is None or graph_field is None:
            self.debug_print(colored(f"✗ field or graphfield could not be found in given data", "magenta"), end=" > ")
            return None
        if field is False or graph_field is False:
            self.debug_print(colored(f"✗ subfield could not be found in given field", "magenta"), end=" > ")
            return None
        if isinstance(field, list) and not isinstance(graph_field, list):
            self.debug_print(colored("GraphMap: list and non-list", "red"), end=" ")
            return None
        if isinstance(field, str) and not isinstance(graph_field, str):
            self.debug_print(colored("GraphMap: str and non-str", "red"), end=" ")
            return None
        if not isinstance(field, str) and not isinstance(field, list):
            self.debug_print(colored("GraphMap: not-str, non-list", "red"), end=" ")
            return None
        if isinstance(field, list) and len(field) != len(graph_field):
            self.debug_print(colored("GraphMap: len difference", "red"), end=" ")
            return None
        # if type(raw_dict[sub_dict['field']]) != type(raw_dict[sub_dict['graph_field']]): # technically possible

        if isinstance(field, str):  # simple variant, a singular string
            temp_value = raw_dict[sub_dict['field']]  # the raw value
            temp_value = Spcht._node_preprocessing(temp_value, sub_dict)  # filters out entries
            if temp_value is not None and len(temp_value) > 0:
                temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                graph = self._node_mapping(graph_field, sub_dict.get("graph_map"), {"$default": sub_dict['graph']})
                return graph, self._node_postprocessing(temp_value, sub_dict)
            else:
                return None
        if isinstance(field, list):  # more complex, two lists that are connected to each other
            result_list = []
            for i in range(0, len(field)):
                if not isinstance(field[i], str) or not isinstance(graph_field[i], str):
                    continue  # we cannot work of non strings, although, what about numbers?
                temp_value = Spcht._node_preprocessing(field[i], sub_dict)  # filters out entries
                if temp_value is not None and len(temp_value) > 0:
                    temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                    # ? when testing all the functions i got very confused at this part. What this does: it basically
                    # ? allows us to use graph_map in conjunction with mapping, i dont know if there is any use ever, but
                    # ? its possible. For reasons unknown to me i wrote this so the value that is mapped to the resulting
                    # ? graph by the mapping function instead of just plain taking the actual value, i think that is cause
                    # ? copied that part from the normal processing to get the pre/postprocessor working. One way or
                    # ? another, since this uses .get it wont fail even if there is no mapping specified but it will work
                    # ? if its the case. The clunky definition in the graph setter below this is the actual default
                    # ? definition, so the default graph is always the graph field if not set to something different.
                    # ? the field is mandatory for all nodes anyway so it should be pretty save
                    graph = self._node_mapping(graph_field[i], sub_dict.get("graph_map"), {"$default": sub_dict['graph']})
                    # danger here, if the graph_map is none, it will return graph_field instead of default, hrrr
                    if sub_dict.get("graph_map") is None:
                        graph = sub_dict['graph']
                    result_list.append((graph, self._node_postprocessing(temp_value, sub_dict)))  # a tuple
                else:
                    continue
            if len(result_list) > 0:
                return result_list
        return None

    def _inserter_string(self, raw_dict: dict, sub_dict: dict):
        """
            This inserts the value of field (and all additional fields defined in "insert_add_fields" into a string,
            when there are less placeholders than add strings those will be omitted, if there are less fields than
            placeholders (maybe cause the data source doesnt score that many hits) then those will be empty "". This
            wont fire at all if not at least field doesnt exits
        :param dict raw_dict: a flat dictionary containing a key sorted list of values to be processes
        :param dict sub_dict: the subdictionary of the node containing all the nodes insert_into and insert_add_fields
        :return: a list of tuple or a singular tuple of (graph, string)
        :rtype: tuple or list
        """
        # ? sometimes i wonder why i bother with the tuple AND list stuff and not just return a list [(graph, str)]
        # * check whether the base field even exists:
        if extract_dictmarc_value(raw_dict, sub_dict) is None:
            return None
        # check what actually exists in this instance of raw_dict
        inserters = []  # each entry is a list of strings that are the values stored in that value, some dict fields are
        # more than one value, therefore everything gets squashed into a list
        if sub_dict['source'] != "dict" and sub_dict['source'] != "marc":
            print(f"Unknown source {sub_dict['source']}found, are you from the future relative to me?")
            return None
        value = extract_dictmarc_value(raw_dict, sub_dict)
        if value is None or value is False:
            raise TypeError("Value for insert fields cannot be None or boolean")
        # inserted MAIN values get the processing
        value = Spcht._node_preprocessing(value, sub_dict)
        if value is None:
            return None  # if for example the value does not match the match filter
        value = self._node_postprocessing(value, sub_dict)
        if isinstance(value, list):
            list_of_values = []
            for every in value:
                if every is not None:
                    list_of_values.append(every)
            if len(list_of_values) <= 0:
                return None
            inserters.append(list_of_values)
        else:
            inserters.append(SpchtUtility.list_wrapper(value))

        if 'insert_add_fields' in sub_dict:
            for each in sub_dict['insert_add_fields']:
                pseudo_dict = {"source": sub_dict['source'], "field": each}
                value = extract_dictmarc_value(raw_dict, pseudo_dict)
                if value is not None and value is not False:
                    inserters.append(SpchtUtility.list_wrapper(value))
                else:
                    inserters.append([""])
        # all_variants iterates through the separate lists and creates a new list or rather matrix with all possible combinations
        # desired format [ ["first", "position", "values"], ["second", "position", "values"]]
        # should lead "xx{}xx{}xx" to "xxfirstxxsecondxx", "xxfirstxxpositionxx", "xxfirstxxvaluesxx" and so on
        all_texts = SpchtUtility.all_variants(inserters)
        self.debug_print(colored(f"Inserts {len(all_texts)}", "grey"), end=" ")
        all_lines = []
        for each in all_texts:
            replaced_line = insert_list_into_str(each, sub_dict['insert_into'], r'\{\}', 2, True)
            if replaced_line is not None:
                all_lines.append(replaced_line)
        if len(all_lines) > 0:
            return all_lines
        else:
            return None

    def _handle_if(self, raw_dict: dict, sub_dict: dict, mode: str):
        # ? for now this only needs one field to match the criteria and everything is fine
        # TODO: Expand if so that it might demand that every single field fulfill the condition
        # here is something to learn, list(obj) is a not actually calling a function and faster for small dictionaries
        # there is the Python 3.5 feature, unpacking generalizations PEP 448, which works with *obj, calling the iterator
        # dictionaries give their keys when iterating over them, it would probably be more clear to do *dict.keys() but
        # that has the same result as just doing *obj --- this doesnt matter anymore cause i was wrong in the thing
        # that triggered this text, but the change to is_dictkey is made and this information is still useful
        if sub_dict['if_condition'] in SpchtUtility.SPCHT_BOOL_OPS:
            sub_dict['if_condition'] = SpchtUtility.SPCHT_BOOL_OPS[sub_dict['if_condition']]
        else:
            return False  # if your comparator is false nothing can be true

        comparator_value = extract_dictmarc_value(raw_dict, sub_dict, "if_field")

        if sub_dict['if_condition'] == "exi":
            if comparator_value is None:
                self.debug_print(colored(f"✗ field {sub_dict['if_field']} doesnt exist", "blue"), end="-> ")
                return False
            self.debug_print(colored(f"✓ field {sub_dict['if_field']}  exists", "blue"), end="-> ")
            return True

        # ! if we compare there is no if_value, so we have to do the transformation later
        sub_dict['if_value'] = if_possible_make_this_numerical(sub_dict['if_value'])

        if comparator_value is None:
            if sub_dict['if_condition'] == "=" or sub_dict['if_condition'] == "<" or sub_dict['if_condition'] == "<=":
                self.debug_print(colored(f"✗ no if_field found", "blue"), end=" ")
                return False
            else:  # redundant else
                self.debug_print(colored(f"✓ no if_field found", "blue"), end=" ")
                return True
            # the logic here is that if you want to have something smaller or equal that not exists it always will be
            # now we have established that the field at least exists, onward
        # * so the point of this is to make shore and coast that we actually get stuff beyond simple != / ==

        #  for proper comparison we also need to use preprocessing and postprocessing to properly filter, i am pondering
        #  to leave this undocumented
        comparator_value = self._node_preprocessing(comparator_value, sub_dict, "if_")
        comparator_value = self._node_postprocessing(comparator_value, sub_dict, "if_")
        # pre and post processing have annoyingly enough a functionality that de-listifies stuff, in this case that is bad
        # so we have to listify again, the usage of pre&postprocessing was an afterthought, i hope this doesnt eat to
        # much performance
        comparator_value = SpchtUtility.list_wrapper(comparator_value)
        # ? i really hope one day i learn how to do this better, this seems SUPER clunky, i am sorry
        # * New Feature, compare to list of values, its a bit more binary:
        # * its either one of many is true or all of many are false
        failure_list = []
        if isinstance(sub_dict['if_value'], list):
            for each in comparator_value:
                for value in sub_dict['if_value']:
                    if sub_dict['if_condition'] == "==":
                        if each == value:
                            self.debug_print(colored(f"✓{value}=={each}", "blue"), end=" ")
                            return True
                    if sub_dict['if_condition'] == "!=":
                        if each == value:
                            self.debug_print(colored(f"✗{value}=={each} (but should not be)", "red"), end=" ")
                            return False  # ! the big difference, ALL values must be unequal
                    if sub_dict['if_condition'] == ">" or sub_dict['if_condition'] == "<" or sub_dict['if_condition'] == ">=" or sub_dict['if_condition'] == "<=":
                        raise TypeError("Cannot do greater/lesser than with a list of Values")
                    # i mean..why bother checking of something is smaller than 15, 20 and 35 if you could easily just check smaller than 35
                    # in theory i could implement this and rightify someone else illogical behaviour
                failure_list.append(each)
            # if we get here and we checked for unequal to our condition was met
            if sub_dict['if_condition'] == "!=":
                self.debug_print(colored(f"✓{sub_dict['if_field']} was not {sub_dict['if_condition']} [conditions] but {failure_list} instead", "blue"), end="-> ")
                return True
        else:
            for each in comparator_value:
                each = if_possible_make_this_numerical(each)
                if sub_dict['if_condition'] == "==":
                    if each == sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}=={each}", "blue"), end=" ")
                        return True
                if sub_dict['if_condition'] == ">":
                    if each > sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<{each}", "blue"), end=" ")
                        return True
                if sub_dict['if_condition'] == "<":
                    if each < sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<{each}", "blue"), end=" ")
                        return True
                if sub_dict['if_condition'] == ">=":
                    if each >= sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}>={each}", "blue"), end=" ")
                        return True
                if sub_dict['if_condition'] == "<=":
                    if each <= sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<={each}", "blue"), end=" ")
                        return True
                if sub_dict['if_condition'] == "!=":
                    if each != sub_dict['if_value']:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}!={each}", "blue"), end=" ")
                        return True
                failure_list.append(each)
        self.debug_print(colored(f" {sub_dict['if_field']} was not {sub_dict['if_condition']} {sub_dict['if_value']} but {failure_list} instead", "magenta"), end="-> ")
        return False

    def _addToSaveAs(self, value, sub_dict):
        # this was originally 3 lines of boilerplate inside postprocessing, i am not really sure if i shouldn't have
        # left it that way, i kinda dislike those mini functions, it divides the code
        if "saveas" in sub_dict:
            if self._SAVEAS.get(sub_dict['saveas'], None) is None:
                self._SAVEAS[sub_dict['saveas']] = []
            self._SAVEAS[sub_dict['saveas']].append(value)

    def get_node_fields(self):
        """
            Returns a list of all the fields that might be used in processing of the data, this includes all
            alternatives, fallbacks and graph_field keys with source dictionary

            :return: a list of strings
            :rtype: list
        """
        if not self:  # requires initiated SPCHT Load
            self.debug_print("list_of_dict_fields requires loaded SPCHT")
            return []

        the_list = []
        the_list.extend(self.default_fields)
        if self._DESCRI['id_source'] == "dict":
            the_list.append(self._DESCRI['id_field'])
        temp_list = SpchtUtility.get_node_fields_recursion(self._DESCRI['id_fallback'])
        if temp_list is not None and len(temp_list) > 0:
            the_list += temp_list
        for node in self._DESCRI['nodes']:
            temp_list = SpchtUtility.get_node_fields_recursion(node)
            if temp_list is not None and len(temp_list) > 0:
                the_list += temp_list
        return sorted(set(the_list))

    @property
    def default_fields(self):
        """
                The fields that are always included by get_node_fields. Per default this is just the explicit modelling of
                the authors usecase, the field 'fullrecord' which contains the marc21 fields. As it doesnt appear normally
                in any spcht descriptor
        """
        return self._default_fields

    @default_fields.setter
    def default_fields(self, list_of_strings: list):
        """
        The fields that are always included by get_node_fields. Per default this is just the explicit modelling of
        the authors usecase, the field 'fullrecord' which contains the marc21 fields. As it doesnt appear in the normal
        spcht descriptor

        :para list_of_strings list: a list of strings that replaces the previous list
        :return: Returns nothing but raises a TypeException is something is off
        :rtype None:
       """
        # ? i first tried to implement an extend list class that only accepts strs as append/extend parameter cause
        # ? you can still append, extend and so on with default_fields and this protects only against a pure set-this-to-x
        # ? but i decided that its just not worth it
        if not isinstance(list_of_strings, list):
            raise TypeError("Given parameter is not a list")
        for each in list_of_strings:
            if not isinstance(each, str):
                raise TypeError("An element in the list is not a string")
        self._default_fields = list_of_strings


    def get_node_graphs(self):
        """
            Returns a list of all different graphs that could be mapped by the loaded spcht file. As for get_node_fields
            this includes the referenced graphs in graph_map and fallbacks. This can theoretically return an empty list
            when there are less than 1 node in the spcht file. But that raises other questions anyway...

            :return: a list of string
            :rtype: list
        """
        if not self:  # requires initiated SPCHT Load
            self.debug_print("list_of_dict_fields requires loaded SPCHT")
            return []
        the_other_list = []
        for node in self._DESCRI['nodes']:
            temp_list = SpchtUtility.get_node_graphs_recursion(node)
            if temp_list is not None and len(temp_list) > 0:
                the_other_list += temp_list
        # list set for deduplication, crude method but best i have for the moment
        return sorted(set(the_other_list))  # unlike the field equivalent this might return an empty list


class SpchtIterator:
    def __init__(self, spcht: Spcht):
        self._spcht = spcht
        self._index = 0

    def __next__(self):
        if isinstance(self._spcht._DESCRI, dict) and \
                'nodes' in self._spcht._DESCRI and \
                self._index < (len(self._spcht._DESCRI['nodes'])):
            result = self._spcht._DESCRI['nodes'][self._index]
            self._index += 1
            return result
        raise StopIteration
