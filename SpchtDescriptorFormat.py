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
import uuid
from pathlib import Path

import SpchtUtility
from SpchtUtility import if_possible_make_this_numerical, insert_list_into_str

import SpchtErrors
try:
    from termcolor import colored  # only needed for debug print
except ModuleNotFoundError:
    def colored(text, *args):
        return text  # throws args away returns non colored text

import logging
logger = logging.getLogger(__name__)

try:
    import rdflib
except ImportError:
    logger.warning("RDFLib import error in Spcht, limits function")


class Spcht:
    def __init__(self, filename=None, schema_path="./SpchtSchema.json", debug=False, log_debug=False):
        self._DESCRI = None  # the finally loaded descriptor file with all references solved
        self._SAVEAS = {}
        # * i do all this to make it more customizable, maybe it will never be needed, but i like having options
        self.std_out = sys.stdout
        self.std_err = sys.stderr
        self.debug_out = sys.stdout
        self._log_debug = log_debug  # if true also write debug texts in log, will lead to SPAM big time
        self._debug = debug
        self.default_fields = ['fullrecord']
        self.descriptor_file = None
        self._raw_dict = None  # processing data
        self._m21_dict = None
        self._schema_path = schema_path
        if filename is not None:
            if not self.load_descriptor_file(filename):
                logger.critical("spcht_init: cannot load initial spcht file")
                raise SpchtErrors.OperationalError("Something with the specified Spcht file was wrong")

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
        return self._DESCRI is not None

    def __iter__(self):
        return SpchtIterator(self)

    def process_data(self, raw_dict, subject, marc21="fullrecord", marc21_source="dict"):
        """
            takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
            per default it assumes there is a marc entry in the solrdump but it can be provided directly
            it also takes technically any dictionary with entries as input

            :param dict raw_dict: a flat dictionary containing a key sorted list of values to be processes
            :param str subject: beginning of the assigned subject all entries become triples of
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
        #export_graph = rdflib.Graph()
        if raw_dict:
            self._raw_dict = raw_dict
        # Preparation of Data to make it more handy in the further processing
        self._m21_dict = None  # setting a default here
        if marc21_source.lower() == "dict":
            try:
                if marc21 in raw_dict:
                    self._m21_dict = SpchtUtility.marc2list(self._raw_dict.get(marc21))
            except AttributeError as e:
                self.debug_print("AttributeError:", colored(e, "red"))
                logger.warning(f"Marc21 could not be loaded due an AttributeError: {e}")
                self._m21_dict = None
            except ValueError as e:  # something is up
                self.debug_print("ValueException:", colored(e, "red"))
                self._m21_dict = None
            except TypeError as e:
                self.debug_print(f"TypeException: (in {self._raw_dict.get('kxp_id_str', '')}", colored(e, "red"))
                self._m21_dict = None
        elif marc21_source.lower() == "none":
            pass  # this is more a nod to anyone reading this than actually doing anything
        else:
            raise SpchtErrors.UndefinedError("The choosen Source option doesnt exists")
            # ? what if there are just no marc data and we know that in advance?
            # * i leave this cause, well, its 2021 and of course this exact thing happened, yeah?

        if 'rdflib' in sys.modules and isinstance(subject, rdflib.URIRef):
            subject = subject.toPython()

        # generates the subject URI, i presume we already checked the spcht for being correct
        # ? instead of making one hard coded go i could insert a special round of the general loop right?
        sub_dict = {
            "name": "$Identifier$",  # this does nothing functional but gives the debug text a non-empty string
            "source": self._DESCRI['id_source'],
            "predicate": "none",  # std recursion process assumes a predicate field that isnt used here but needed anyway
            "field": self._DESCRI['id_field'],
            # i am aware that .get returns none anyway, this is about clarification
            "alternatives": self._DESCRI.get('id_alternatives', None),
            "fallback": self._DESCRI.get('id_fallback', None)
        }
        # ? what happens if there is more than one resource?
        ressource = self._recursion_node(sub_dict)
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
            self_sufficient_triples = None  # additional informations for sub nodes
            rdf_triples = None
            # ! MAIN CALL TO PROCESS DATA
            try:
                facet = self._recursion_node(node)
                if isinstance(facet, list):  # should nowadays be almost always
                    self_sufficient_triples = [x for x in facet if len(x) == 4]
                    rdf_triples = [x for x in facet if len(x) == 3]
                    facet = [x for x in facet if len(x) == 2]
            except Exception as e:
                facet = None
                logger.debug(f"_recursion_node throws Exception {e.__class__.__name__}: '{e}'")
            # ! Data Output Modelling Try 2
            if node.get('type', "literal") == "uri":
                node_status = 1
            else:
                node_status = 0
            # * mandatory checks
            # there are two ways i could have done this, either this or having the checks split up in every case
            if not facet:
                if node['required'] == "mandatory":
                    logger.info(f"NodeName '{node.get('name', '?')}' required field {node['field']} but its not present")
                    raise SpchtErrors.MandatoryError(f"Field {node['field']} is a mandatory field but not present")
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
                triple_list.append(((subject + ressource), facet[0], facet[1], node_status))
                # tuple form of 4
                # [0] the identifier
                # [1] the subject name
                # [2] the value or graph
                # [3] meta info whether its a graph or a literal
            # * data output - list form
            elif isinstance(facet, list):  # list of tuples form
                for each in facet:  # this is a new thing, me naming the variable "each", i dont know why
                    if each[1] is not None:
                        triple_list.append(((subject + ressource), each[0], each[1], node_status))
                    # here was a check for empty elements, but we already know that not all are empty
                    # this should NEVER return an empty list cause the mandatory check above checks for that
            if self_sufficient_triples:
                triple_list += self_sufficient_triples
            if rdf_triples:
                [export_graph.add((x[0], x[1], x[2])) for x in rdf_triples]
        self._m21_dict = None
        self._raw_dict = None
        #print(export_graph.serialize(format="turtle").decode("utf-8"))
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
        if self.debug is True:
            if 'file' in kwargs:
                del kwargs['file']  # while handing through all the kwargs we have to make one exception, this seems to work
            print(*args, file=self.debug_out, **kwargs)
        if self.log_debug:
            long_string = ""
            sep = " "
            if 'sep' in kwargs:
                sep = kwargs['sep']
            for each in args:
                if not long_string:
                    long_string = each
                else:
                    long_string += sep + each
            logger.debug(long_string)

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
            :return: Returns the loaded object (list or dictionary) or 'None' if something happend
            :rtype: dict or None
        """
        msg0 = "Could not load json file - "
        try:
            with open(filename, mode='r') as file:
                return json.load(file)
        except FileNotFoundError:
            print("nofile -", filename, file=self.std_err)
            logger.critical(f"{msg0}File not found")
            return None
        except ValueError as error:
            print(colored("Error while parsing JSON:\n\r", "red"), error, file=self.std_err)
            logger.critical(f"{msg0}Json could not be parsed {error}")
            return None
        except KeyError as key:
            print("KeyError", file=self.std_err)
            logger.critical(f"{msg0}KeyError '{key}'")
            return None
        except Exception as e:
            print("Unexpected Exception:", e.args, file=self.std_err)
            logger.critical(f"{msg0}surprising exception: '{e}'")
            return None

    def get_save_as(self, key=None):
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

    def clean_save_as(self):
        # i originally had this in the "getSaveAs" function, but maybe you have for some reasons the need to do this
        # manually or not at all. i dont know how expensive set to list is. We will find out, eventually
        self._SAVEAS = {k: list(set(v)) for k, v in self._SAVEAS.items()}

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
        if not descriptor:  # load json goes wrong if something is wrong with the json
            return False
        status, msg = SpchtUtility.schema_validation(descriptor, self._schema_path)
        if not status:
            self.debug_print(colored(msg, "red"))
            return False
        # old method of validation, replaced by jsonSchema
        # if not SpchtUtility.check_format(descriptor, base_path=spcht_path.parent):
        #     return False
        # * goes through every mapping node and adds the reference files, which makes me basically rebuild the thing
        # ? python iterations are not with pointers, so this will expose me as programming apprentice but this will work
        new_node = []
        for item in descriptor['nodes']:
            try:
                a_node = self._load_ref_node(item, str(spcht_path.parent))
                new_node.append(a_node)
            except TypeError as that_type:
                self.debug_print("spcht_ref-type", colored(that_type, "red"))
                logger.critical("load_spcht: cannot load due wrong types in referenced data")
                return False
            except SpchtErrors.OperationalError as text:
                self.debug_print("spcht_ref-load", colored(text, "red"))
                return False
            except Exception as e:
                self.debug_print("spcht_ref", colored(e, "red"))
                # raise ValueError(f"ValueError while working through Reference Nodes: '{e}'")
                return False
        status, msg = SpchtUtility.regex_validation(new_node)
        if not status:
            self.debug_print(f"Regex validation failed, message: {msg}")
            return False
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
                if not map_dict:
                    raise SpchtErrors.OperationalError("Could not load referenced node")
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
            # clean up mapping_settings node
            del (node_dict['mapping_settings']['$ref'])
            if len(node_dict['mapping_settings']) <= 0:
                del (node_dict['mapping_settings'])  # if there are no other entries the entire mapping settings goes
            # * that cleanup step is of interest for the 'compile_spcht' option

        if 'joined_map_ref' in node_dict:  # mostly boiler plate from above, probably not my brightest day
            file_path = node_dict['joined_map_ref']
            map_dict = self.load_json(os.path.normpath(os.path.join(base_path, file_path)))
            if not isinstance(map_dict, dict):
                raise TypeError("Structure of loaded joned_map_reference is not a dictionary")
            node_dict['joined_map'] = node_dict.get('joned_map', {})
            for key, value in map_dict.items():
                if not isinstance(value, (str, int, float)):
                    self.debug_print("spcht_map")
                    raise TypeError("Value of joined_map is not a string, integer or float")
                if not isinstance(key, (str, int, float)):  # is that even possible in json?
                    self.debug_print("spcht_map")
                    raise TypeError("Key of joined_map is not a string, integer or float")
                node_dict['joined_map'][key] = node_dict['joined_map'].get(key, value)   # ? not replacing existing keys
            del node_dict['joined_map_ref']

        return node_dict  # whether nothing has had changed or not, this holds true

    def _recursion_node(self, sub_dict: dict):
        """
        Main function of the data processing, this decides how to handle a specific node, gets also called recursivly
        if a node contains a fallback
        :param dict sub_dict: the sub node that describes the behaviour
        :return: a (predicate, object) tuple or a list of such tuples [(predicate, object), ...] as provided by node_return_iron
        :rtype: tuple
        """
        # i do not like the general use of recursion, but for traversing trees this seems the best solution
        # there is actually not so much overhead in python, its more one of those stupid feelings, i googled some
        # random reddit thread: https://old.reddit.com/r/Python/comments/4hkds8/do_you_recommend_using_recursion_in_python_why_or/
        # @param sub_dict = the part of the descriptor dictionary that is in ['fallback']
        # @param raw_dict = the big raw dictionary that we are working with
        # @param marc21_dict = an alternative marc21 dictionary, already cooked and ready
        # the header/id field is special in some sense, therefore there is a separated function for it
        # UPDATE 03.08.2020 : i made it so that this returns a tuple of the predicate and the actual value
        # this is so cause i rised the need for manipulating the used predicate for that specific object via
        # mappings, it seemed most forward to change all the output in one central place, and that is here
        if sub_dict.get('name', "") == "$Identifier$":
            self.debug_print(colored("ID Source:", "red"), end=" ")
        else:
            self.debug_print(colored(sub_dict.get('name', ""), "cyan"), end=" ")

        full_triples = []

        # * Replacement of old procedure with universal extraction
        # * this funnels a 'main_value' through the procedure and utilises a host of exist nodes
        if sub_dict['source'] == "dict":
            self.debug_print(colored("Source Dict", "yellow"), end="-> ")
        elif sub_dict['source'] == "marc":
            self.debug_print(colored("Source Marc", "yellow"), end="-> ")
        else:
            self.debug_print(colored(f"Source {sub_dict['source']}, this is new!", "magenta"), end="-> ")

        if 'joined_value' in sub_dict:  # joined map procedure
            self.debug_print(colored("✓ joined_field", "green"), end="-> ")
            joined_result = self._joined_map(sub_dict)
            # ? _joined_map does basically the same as before but cojoined with a predicate mappping, because of the
            # ? additional checks i decided to 'externalize' that to make this part of the code more clean
            if not joined_result:
                self.debug_print(colored(f"✗ joined mapping could not be fullfilled", "magenta"), end="-> ")
                return self._call_fallback(sub_dict)
            return joined_result
        else:
            main_value = self.extract_dictmarc_value(sub_dict)
            if 'static_field' in sub_dict:
                main_value = sub_dict['static_field']
            if not main_value:

                if 'alternatives' in sub_dict:
                    self.debug_print(colored("Alternatives", "yellow"), end="-> ")
                    for other_field in sub_dict['alternatives']:
                        main_value = self.extract_dictmarc_value(sub_dict, other_field)
                        if main_value:
                            self.debug_print(colored("✓ alternative field", "green"), end="-> ")
                            break
                    if not main_value:
                        return self._call_fallback(sub_dict)  # ? EXIT 1
                else:
                    return self._call_fallback(sub_dict)  # ? EXIT 2
            else:
                self.debug_print(colored("✓ simple field", "green"), end="-> ")
            main_value = self._node_preprocessing(main_value, sub_dict)
            if not main_value:
                self.debug_print(colored(f"✗ value preprocessing returned no matches", "magenta"), end="-> ")
                return self._call_fallback(sub_dict)  # ? EXIT 3
            if 'if_field' in sub_dict:
                if not self._handle_if(sub_dict):
                    return self._call_fallback(sub_dict)  # ? EXIT 4
            main_value = self._node_postprocessing(main_value, sub_dict)  # post_processing should not delete values
            # in the absolute worst case we have some aggressive cut and we end with a list of empty strings
            if 'mapping' in sub_dict:
                main_value = self._node_mapping(main_value, sub_dict['mapping'], sub_dict.get('mapping_settings', None))
            if not main_value:
                return self._call_fallback(sub_dict)  # ? EXIT 5
            if 'insert_into' in sub_dict:
                main_value = self._inserter_string(main_value, sub_dict)
                self.debug_print(colored("✓ insert_into", "green"), end="-> ")
            if 'append_uuid_object_fields' in sub_dict:
                uuid = self.uuid_generator(sub_dict['source'], *sub_dict['append_uuid_object_fields'])
                main_value = [x + uuid for x in main_value]
            self.debug_print(colored("✓ Main Value", "cyan"))
            # ? temporary tag handling, should be replaced by proper data formats
            if 'tag' in sub_dict:
                main_value = [f"\"{x}\"{sub_dict['tag']}" for x in main_value]
            # ! sub node handling
            if 'sub_nodes' in sub_dict:  # TODO: make this work for joined_map
                self.debug_print(colored("Sub Nodes detected:", "blue"), f"{len(sub_dict['sub_nodes'])} entry instance(s)")
                full_triples += self._handle_sub_node(sub_dict['sub_nodes'], main_value)

            return full_triples + self._node_return_iron(sub_dict['predicate'], main_value)

    def _call_fallback(self, sub_dict):
        if 'fallback' in sub_dict and sub_dict['fallback'] is not None:  # we only get here if everything else failed
            # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
            # * librarian was who wrote the descriptor format
            self.debug_print(colored("Fallback triggered", "magenta"), end="-> ")
            recursion_node = copy.deepcopy(sub_dict['fallback'])
            if 'predicate' not in recursion_node:
                recursion_node['predicate'] = sub_dict['predicate']  # so in theory you can define new graphs for fallbacks
            return self._recursion_node(recursion_node)
        else:
            self.debug_print(colored("absolutely nothing", "red"), end=" |\n")
            return None  # usually i return false in these situations, but none seems appropriate

    @staticmethod
    def _node_return_iron(predicate: str, subject: list or str) -> list:
        """
        Used in processing of content as last step before signing off to the processing functions
        equalizes the output, desired is a format where there is a list of tuples, after the basic steps we normally
        only get a string for the predicate but a list for the subject, this makes it so that there are as many
        predicates as there are value to fill the tuples
        Only case when there is more than one predicate would be the joined_mapping function (and that doesnt call this)

        This method is static, instead of beeing inside SpchtUtility cause it shares close and specific functionality
        with the SpchtDescriptor Core function

        :param predicate: the mapped predicate for this node
        :param subject: a single mapped string or a list of such
        :rtype: list
        :return: a list of tuples where the first entry is the graph and the second the mapped subject, might be empty
        """
        # this is a simple routine to adjust the output from the nodeprocessing to a more uniform look so that its always
        # a list of tuples that is returned, instead of a tuple made of a string and a list.
        if not isinstance(predicate, str):
            raise TypeError("Predicate has to be a string")  # ? has it thought? Could be an URI Object..technically
        if isinstance(subject, (int, float)):
            subject = str(subject)  # i am feeling kinda bad here, but this should work right?
            # although i am not sure how a number or a float can be a valid URI
        if not subject:
            return []
        if isinstance(subject, str):
            return [(predicate, subject)]  # list of one tuple
        if isinstance(subject, list):
            return [(predicate, s) for s in subject if s]
        logger.error(f"While using the node_return_iron something failed while ironing '{str(subject)}'")
        raise TypeError("Could handle predicate, subject pair")

    @staticmethod
    def _node_preprocessing(value: str or list, sub_dict: dict, key_prefix="") -> list:
        """
        Filtering the given value or list of values with the node-parameter 'match' or '{prefix}match', it will then
        return a list with all strings that match, will convert numbers to strings, the entire string will be returned
        not just the matching part. Regex Syntax is used (and regex itself of course) If no entry matches an empty
        list will be returned. Will throw an TypeError if a non-str, non-int and non-float is given as value or as element
        of the given list. List order should be preserved but there is no garantue for that.

        This method is static instead of beeing inside SpchtUtility cause it shares close and specific functionality with
        the SpchtDescriptor Core function

        :param str or list value: value of the found field/subfield, can be a list
        :param dict sub_dict: sub dictionary containing a match key, if not nothing happens
        :return: if not a single match was found, always a list of values, even its just one
        :raise TypeError: for value != (list, str, float, int), and value=list but list elements not str,float,int
        """
        # if there is a match-filter, this filters out the entry or all entries not matching
        if f'{key_prefix}match' not in sub_dict:
            return SpchtUtility.list_wrapper(value)  # the nothing happens clause
        if isinstance(value, (float, int, str)):
            finding = re.search(sub_dict[f'{key_prefix}match'], str(value))
            if finding is not None:
                return [finding.string]
            else:
                return []
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                if not isinstance(item, (float, int, str)):
                    logger.error(f"SPCHT.node_preprocessing - unable to handle data type {type(item)} in list")
                    raise TypeError(f"SPCHT.node_preprocessing - Found a {type(value)} in a given list.")
                finding = re.search(sub_dict[f'{key_prefix}match'], str(item))
                if finding:
                    list_of_returns.append(item)  # ? extend ?
            return list_of_returns
        else:  # fallback if its anything else i dont intended to handle with this
            logger.error(f"SPCHT.node_preprocessing - unable to handle data type {type(value)}")
            raise TypeError(f"SPCHT.node_preprocessing - Found a {type(value)}")
            # return value

    def _node_postprocessing(self, value: str or list, sub_dict: dict, key_prefix="") -> list:
        """
        Changes a string after it was already taken for inclusion as a node, this changes the string in two ways:

        * cut & replace, exchanges the regex from 'cut' with the content of 'replace
        * prepend & append, adds the text of 'prepend' before the string, 'append' to the end

        if none of the parameters is defined it will just return the input value without any transformations. In that
        case a non-list might be returned, if any operation took place, the data will always be in a list

        :param str or list value: the content of the field that got mapped till now
        :param dict sub_dict: the subdictionary of the node containing the 'cut', 'prepend', 'append' and 'replace' key
        :return: returns the same number of provided entries as input, always a list
        :rtype: list
        """
        # after having found a value for a given key and done the appropriate mapping the value gets transformed
        # once more to change it to the provided pattern

        # as i have manipulated the preprocessing there should be no non-strings anymore
        # (Jul/21) there should also be no more strings as everything is a list by now (except in a test case i wrote)
        if isinstance(value, str):
            if f'{key_prefix}cut' in sub_dict:
                value = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), value)
                if key_prefix != "":  # ? in theory this can be used on any value, but 'save' should only save the main one
                    self._add_to_save_as(value, sub_dict)
            else:
                if key_prefix != "":
                    self._add_to_save_as(value, sub_dict)
            return [sub_dict.get(f'{key_prefix}prepend', "") + value + sub_dict.get(f'{key_prefix}append', "")]
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                if f'{key_prefix}cut' not in sub_dict:
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + str(item) + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._add_to_save_as(item, sub_dict)
                else:
                    pure_filter = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), str(item))
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + pure_filter + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._add_to_save_as(pure_filter, sub_dict)
                list_of_returns.append(rest_str)
            return list_of_returns  # [] is falsey, replaces old "return None" clause
        else:  # fallback if its anything else i dont intended to handle with this
            return value

    def _node_mapping(self, value, mapping, settings=None):
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
        the_default = None
        inherit = False
        regex = False
        if not isinstance(mapping, dict) or mapping is None:
            return value
        if settings is not None and isinstance(settings, dict):
            if '$default' in settings:
                the_default = str(settings['$default'])
                # if the value is boolean True it gets copied without mapping
                # if the value is a str that is default, False does nothing but preserves the default state of default
                # Python allows me to get three "boolean" states here done, value, yes and no. Yes is inheritance
            if '$inherit' in settings and settings['$inherit']:
                inherit = True
            if '$regex' in settings and settings['$regex']:
                regex = True
            if '$casesens' in settings and not settings['$casesens']:  # carries the risk of losing entries
                # case insensitivity is achieved by just converting every key to lowercase
                mapping = {str(k).lower(): v for k, v in mapping.items()}

        value = SpchtUtility.list_wrapper(value)

        if isinstance(value, list):  # ? repeated dictionary calls not good for performance?
            response_list = []
            if not regex:
                for item in value:
                    if item in mapping:
                        response_list.append(mapping[item])
                    else:
                        if inherit:
                            response_list.append(item)
            else:  # ! regex call, probably somewhat expensive
                patterns = {}
                for each in mapping:
                    patterns[re.compile(each)] = each
                for entry in value:
                    matching = None
                    if any((match := regex.search(entry)) for regex in patterns):
                        matching = mapping[patterns[match.re]]
                    if matching:
                        response_list.append(matching)
                    elif inherit:
                        response_list.append(entry)

            if len(response_list) > 0:
                return response_list
            else:
                if the_default:
                    # ? i wonder when this even triggers? when giving an empty list? in any other case default is there
                    # * caveat here, if there is a list of unknown things there will be only one default
                    response_list.append(the_default)  # there is no inheritance here, i mean, what should be inherited? void?
                return response_list
                # ? i was contemplating whether it should return value or None. None is the better one i think
                # ? cause if we no default is defined we probably have a reason for that right?
                # ! stupid past me, it should throw an exception
        else:
            logger.error("_node_mapping: got a non-list, non-string as value.")
            print(f"field contains a non-list, non-string: {type(value)}", file=self.std_err)

    def _joined_map(self, sub_dict: dict) -> list:
        """
        This innocent word hides a whole host of operations that mimic the other stuff. Normally the predicate part of
        any one node is constant, this allows to dynamically change the predicate based on another field. For this there
        must be a second field that serves as decider for which kind of predicate the process goes. The value is then
        served to a map and choosen among the values present in that map (and defaults to the static predicate if nothing
        is matching). If the secondary field is more than one value it must have exactly as many list-entries as the
        object value. Each value is then matched to the same position as the predicate.

        * Mode 1: **n=1** predicate field value, many object fields --- dynamic predicate for all values
        * Mode 2: **n=x** predicate field values, **x** object field values --- matching predciate & object
        * **any other combination will fail**

        :param dict sub_dict: the node dictionary containing the data to process this step, namely: graph_field, graph_map
        :type sub_dict:
        :return: a list of tuples
        :rtype: list
        """
        field = self.extract_dictmarc_value(sub_dict, sub_dict["field"])
        # ? alternatives seems to very unlikely to ever work but maybe there is data in the future that has use for this
        if not field:
            if 'alternatives' in sub_dict:
                self.debug_print(colored("Alternatives", "yellow"), end="-> ")
                for other_field in sub_dict['alternatives']:
                    field = self.extract_dictmarc_value(sub_dict, other_field)
                    if field:
                        self.debug_print(colored("✓ alternative field", "green"), end="-> ")
                        break
                if not field:
                    logger.debug("_joined_map: EXIT 1")
                    return []  # ? EXIT 1
            else:
                logger.debug("_joined_map: EXIT 2")
                return []  # ? EXIT 2
        if 'if_field' in sub_dict:  # if filters entire nodes
            if not self._handle_if(sub_dict):
                logger.debug("_joined_map: EXIT 3")
                return []   # ? EXIT 3

        joined_field = self.extract_dictmarc_value(sub_dict, sub_dict["joined_field"])

        # ? About these checks and the commented raises:
        # in the past joined field was the final stop gap, i later changed it to a way that is more natural with the
        # rest of the other Spcht workings, as i was unsure if i keep it that way i kept a few more bytes around
        # also, extract_dictmarc will always return a list, most of these checks here _should_ never trigger
        if not joined_field:
            msg = "joined_field could not be found in given data"
            self.debug_print(colored(f"✗ no joined_field", "magenta"), end="-> ")
            logger.debug(f"_joined_map: {msg}")
            logger.debug("_joined_map: EXIT 4")
            return []
            # raise SpchtErrors.DataError(msg)
        if isinstance(field, list) and not isinstance(joined_field, list):
            self.debug_print(colored("JoinedMap: list and non-list", "red"), end="-> ")
            msg = "joined_field and field are not of the same, allowed, type."
            logger.warning(f"_joined_map {msg}")
            logger.debug("_joined_map: EXIT 5")
            return []
            # raise SpchtErrors.DataError(msg)
        if not isinstance(field, (str, float, int, list)) or not isinstance(joined_field, (str, float, int, list)):
            self.debug_print(colored("JoinedMap: non-value, non-list", "red"), end="-> ")
            msg = "One or both of field and/or joined_field value are not of the allowed type, curious"
            logger.error(f"_joined_map {msg}")
            logger.debug("_joined_map: EXIT 6")
            return []
            # raise SpchtErrors.DataError(msg)
        if isinstance(field, list) and isinstance(joined_field, list):
            # this is a weird one, the extracation procedure above should always result in a list, even with length 1,
            # but i know that i have to extend that function, so i might need to change that, therefore i already added
            # this check to keep the input compatibility
            if len(joined_field) == 1 and len(field) != len(joined_field):
                # ? this is a rather small 'hack' to get the n=1 effect without having a lot of complicated things
                joined_field = [joined_field[0] for _ in enumerate(field)]
            elif len(field) != len(joined_field):
                self.debug_print(colored("JoinedMap: len difference", "red"), end=" ")
                msg = f"Found different lengths for field and joinedfield ({len(field)} vs. {len(joined_field)})"
                logger.debug(f"_joined map {msg}")
                logger.debug("_joined_map: EXIT 7")
                return []
                # raise SpchtErrors.DataError(msg)
        else:  # another of those occasions that shall not happen
            field = SpchtUtility.list_wrapper(field)
            joined_field = SpchtUtility.list_wrapper(joined_field)
        # if type(raw_dict[sub_dict['field']]) != type(raw_dict[sub_dict['joined_field']]): # technically possible

        result_list = []
        for i, item in enumerate(field):  # iterating through the list every time is tedious
            try:
                if not isinstance(field[i], (str, int, float)) or not isinstance(joined_field[i], (str, int, float)):
                    logger.debug(f"_joined_map has in field '{sub_dict['field']}' a non-instance of str either in '{field[i]}' or '{joined_field[i]}'")
                    continue
                sobject = Spcht._node_preprocessing(field[i], sub_dict)  # filters out entries
                if not sobject:
                    continue
                sobject = self._node_mapping(sobject, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                sobject = self._node_postprocessing(sobject, sub_dict)
                if len(sobject) == 1:
                    sobject = sobject[0]
                else:
                    logger.critical("_joined_map, for some unexptected reasons, the output inside the joined_map loop had more than one value for the object, that should not happen, never. Investigate!")
                    raise SpchtErrors.OperationalError("Cannot continue processing with undecisive data")
                # * predicate processing
                predicate = self._node_mapping(joined_field[i], sub_dict.get("joined_map"), {"$default": sub_dict['predicate']})
                if len(predicate) == 1:
                    predicate = predicate[0]

                result_list.append((predicate, sobject))  # a tuple
            except IndexError as e:
                msg = f"joined map found an out of index error for field&joined_field, this means something is wrongly coded: {e}"
                logger.error(msg)
                raise SpchtErrors.OperationalError(msg)
        logger.debug("_joined_map: EXIT 8-INFINITE")
        return result_list  # ? can be empty, [] therefore falsey (but not none so the process itself was successful

    def _inserter_string(self, value, sub_dict: dict):
        """
            This inserts the value of field (and all additional fields defined in "insert_add_fields" into a string,
            when there are less placeholders than add strings those will be omitted, if there are less fields than
            placeholders (maybe cause the data source doesnt score that many hits) then those will be empty "". This
            wont fire at all if not at least field doesnt exits
        :param dict sub_dict: the subdictionary of the node containing all the nodes insert_into and insert_add_fields
        :return: a list of tuple or a singular tuple of (predicate, string)
        :rtype: tuple or list
        """

        # check what actually exists in this instance of raw_dict
        inserters = [value]  # each entry is a list of strings that are the values stored in that value, some dict fields are

        if 'insert_add_fields' in sub_dict:  # ? the two times this gets called it actually checks beforehand, why do i bother?
            for each in sub_dict['insert_add_fields']:
                # ? it feels a bit wrong to do such 'tricks' in my own code
                pseudo_dict = {"source": sub_dict['source'], "field": each['field']}
                others = ['append', 'prepend', 'cut', 'replace', 'source', 'match']
                for every in others:
                    if every in each:
                        pseudo_dict[every] = each[every]
                additional_value = self.extract_dictmarc_value(pseudo_dict)
                # using preprocessing to filter out certain values gives quite a lot of power to this kind of process
                # if used right that is..i see a lot of error potential here
                additional_value = self._node_preprocessing(additional_value, pseudo_dict)
                additional_value = self._node_postprocessing(additional_value, pseudo_dict)
                if additional_value:
                    inserters.append(SpchtUtility.list_wrapper(additional_value))
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
        return all_lines

    def _handle_if(self, sub_dict: dict):
        """
        If portion of the spcht processing, takes place between preprocessing and post processing, means that values
        that were already matched get compared. The dictionary entry that is used for the comparison can but must not be
        the same as the mapped field. Furthermore it is also possible to test for membership in a whitelist or the
        opposite, like if 'VALUE' is either 'X', 'Y' or 'Z' instead of just 'X', it is also possible to make size
        comparison as long the tested field is some kind of number (strings that represent numbers will be converted).
        Its also possible to test for existence of a field only, no previous transformation steps are used in that case.
        For all other checks the full suite of pre&postprocessing operations will be used, so the value of the designated
        field will first be filtered by 'match', then cut by 'cut', extend by 'append' & 'prepend' and only then  compared
        to the content of 'if_value'. If there is more than one value in 'if_field' each field will be checked and as
        long one is able to fulfill the condition this will return true.
        :param dict sub_dict:
        :return: True if the condition can be fulfilled, false if not OR parameters are missing (cause logic demands it)
        :rtype: bool
        """
        # ? for now this only needs one field to match the criteria and everything is fine
        # TODO: Expand if so that it might demand that every single field fulfill the condition
        # here is something to learn, list(obj) is a not actually calling a function and faster for small dictionaries
        # there is the Python 3.5 feature, unpacking generalizations PEP 448, which works with *obj, calling the iterator
        # dictionaries give their keys when iterating over them, it would probably be more clear to do *dict.keys() but
        # that has the same result as just doing *obj --- this doesnt matter anymore cause i was wrong in the thing
        # that triggered this text, but the change to is_dictkey is made and this information is still useful
        if sub_dict['if_condition'] in SpchtUtility.SPCHT_BOOL_OPS:
            condition = SpchtUtility.SPCHT_BOOL_OPS[sub_dict['if_condition']]
        else:
            return False  # if your comparator is false nothing can be true

        comparator_value = self.extract_dictmarc_value(sub_dict, sub_dict["if_field"])

        if condition == "exi":
            if not comparator_value:
                self.debug_print(colored(f"✗ field {sub_dict['if_field']} doesnt exist", "blue"), end="-> ")
                return False
            self.debug_print(colored(f"✓ field {sub_dict['if_field']}  exists", "blue"), end="-> ")
            return True

        # ! if we compare there is no if_value, so we have to do the transformation later
        if_value = if_possible_make_this_numerical(sub_dict['if_value'])

        if not comparator_value:
            if condition in ("=", ">", ">="):
                self.debug_print(colored(f"✗ no if_field found", "blue"), end=" ")
                return False
            else:  # redundant else
                self.debug_print(colored(f"✓ no if_field found", "blue"), end=" ")
                return True
            # the logic here is that if you want to have something smaller or equal that not exists it always will be
            # now we have established that the field at least exists, onward
        # * so the point of this is to make shore and coast that we actually get stuff beyond simple != / ==

        comparator_value = self._node_preprocessing(comparator_value, sub_dict, "if_")
        comparator_value = self._node_postprocessing(comparator_value, sub_dict, "if_")
        # ? i really hope one day i learn how to do this better, this seems SUPER clunky, i am sorry
        # * New Feature, compare to list of values, its a bit more binary:
        # * its either one of many is true or all of many are false
        failure_list = []
        if isinstance(if_value, list):
            for each in comparator_value:
                each = if_possible_make_this_numerical(each)
                for value in if_value:
                    if condition == "==":
                        if each == value:
                            self.debug_print(colored(f"✓{value}=={each}", "blue"), end=" ")
                            return True
                    if condition == "!=":
                        if each == value:
                            self.debug_print(colored(f"✗{value}=={each} (but should not be)", "red"), end=" ")
                            return False  # ! the big difference, ALL values must be unequal
                    if condition == ">" or condition == "<" or condition == ">=" or condition == "<=":
                        logger.error(f"_handle_if: a list of values was provided but not a definite comparator (used {sub_dict['if_condition']} instead)")
                        raise TypeError("Cannot do greater/lesser than with a list of Values")
                    # i mean..why bother checking of something is smaller than 15, 20 and 35 if you could easily just check smaller than 35
                    # in theory i could implement this and rightify someone else illogical behaviour
                failure_list.append(each)
            # if we get here and we checked for unequal to our condition was met
            if condition == "!=":
                self.debug_print(colored(f"✓{sub_dict['if_field']} was not {sub_dict['if_condition']} [conditions] but {failure_list} instead", "blue"), end="-> ")
                return True
        else:
            for each in comparator_value:
                each = if_possible_make_this_numerical(each)
                # ? if we attempt to do this, we just normally get a type error, so why bother?
                numerical = [">", ">=", "<", "<="]
                if not isinstance(if_value, (int, float, complex)) and condition in numerical:
                    logger.error(f"_handle_if: field '{sub_dict['field']}' has a faulty value<>condition combination that tries to compare non-numbers")
                    raise TypeError("Cannot compared with non-numbers")
                if not isinstance(each, (int, float, complex)) and condition in numerical:
                    logger.warning(f"_handle_if: field '{sub_dict['field']}' returns at least one value that is a not-number but condition is '{condition}'")
                    continue
                if condition == "==":
                    if each == if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}=={each}", "blue"), end=" ")
                        return True
                if condition == ">":
                    if each > if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<{each}", "blue"), end=" ")
                        return True
                if condition == "<":
                    if each < if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<{each}", "blue"), end=" ")
                        return True
                if condition == ">=":
                    if each >= if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}>={each}", "blue"), end=" ")
                        return True
                if condition == "<=":
                    if each <= if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}<={each}", "blue"), end=" ")
                        return True
                if condition == "!=":
                    if each != if_value:
                        self.debug_print(colored(f"✓{sub_dict['if_field']}!={each}", "blue"), end=" ")
                        return True
                failure_list.append(each)
        self.debug_print(colored(f" {sub_dict['if_field']} was not {condition} {if_value} but {failure_list} instead", "magenta"), end="-> ")
        return False

    def _handle_sub_node(self, sub_nodes, parent_value):
        """
        Sub Nodes are entire new triples that have a different subject than the original created triple, as that
        the use the value of the parent node as subject , therefore the parent node should be a valid URI, otherwise
        the operation will fail. The most basic, working operation will always return at least two triples in the end:

        * a triple describing the sub_node relation to the main subject
        * a triple describing the new property with the main value as subject

        This creats a tree-like relationship and not independent nodes
        :param dict sub_nodes:
        :param list parent_value:
        :return: a list of tuples containing 4 values describing an entire triple where the last number is "isTriple=True/False"
        :rtype: list
        """
        return_quadros = []
        # return_rdf = []
        if len(parent_value) != 1:
            raise SpchtErrors.ParsingError("Use of sub node required parent values to be singular")
        sub_subject = parent_value[0]
        # cycles = len(sub_nodes)
        for i, single_node in enumerate(sub_nodes):
            try:
                # self.debug_print(colored(f"Cycling node {i}/{cycles} - {single_node.get('name', 'unnamed')}"))
                sub_values = self._recursion_node(single_node)
                if sub_values:
                    self_sufficient_triples = [x for x in sub_values if len(x) == 4]
                    sub_values = [x for x in sub_values if len(x) == 2]
                    if self_sufficient_triples:
                        return_quadros += self_sufficient_triples
                    if 'type' in single_node and single_node['type'] == "uri":
                        # return_rdf += [(rdflib.URIRef(sub_subject), rdflib.URIRef(x[0]), rdflib.URIRef(x[1])) for x in sub_values]
                        return_quadros += [(sub_subject, x[0], x[1], 1) for x in sub_values]
                    else:
                        # if 'tag' in single_node:
                        #   lang, datatype = SpchtUtility.extract_node_tag(single_node['tag'])
                        #   return_rdf += [(rdflib.URIRef(sub_subject), rdflib.URIRef(x[0]), rdflib.Literal(x[1], lang=lang, datatype=datatype)) for x in sub_values]
                        return_quadros += [(sub_subject, x[0], x[1], 0) for x in sub_values]
            except Exception as e:
                logger.warning(f"SubNode throws Exception {e.__class__.__name__}: '{e}'")
                print(colored("✗Processing of sub_node failed.", "red"))
        # return_quadros.append(return_rdf)
        return return_quadros

    def _add_to_save_as(self, value, sub_dict):
        # this was originally 3 lines of boilerplate inside postprocessing, i am not really sure if i shouldn't have
        # left it that way, i kinda dislike those mini functions, it divides the code
        if "saveas" in sub_dict:
            if self._SAVEAS.get(sub_dict['saveas'], None) is None:
                self._SAVEAS[sub_dict['saveas']] = []
            self._SAVEAS[sub_dict['saveas']].append(value)

    def uuid_generator(self, source, *fields):
        names_combined = ""
        for each in fields:
            a_field = self.extract_dictmarc_value({"source": source}, each)
            if a_field:
                names_combined += str(a_field)
            else:
                logger.debug(f"UUID_Gen: Field {each} does not exist in given data")
                raise SpchtErrors.DataError("UUID-Gen - Given field yields no value")
        return str(uuid.uuid5(uuid.NAMESPACE_URL, names_combined))

    def extract_dictmarc_value(self, sub_dict: dict, dict_field=None, dict_tree=None) -> list:
        """
        In the corner case and context of this program there are (for now) two different kinds of 'raw_dict', the first
        is a flat dictionary containing a key:value relationship where the value might be a list, the second is the
        transformed marc21_dict which is the data retrieved from the marc_string inside the datasource. The transformation
        steps contained in spcht creates a dictionary similar to the 'normal' raw_dict. There are additional exceptions
        like that there are marc values without sub-key, for these the special subfield 'none' exists, there are also
        indicators that are actually standing outside of the normal data set but are included by the transformation script
        and accessable with 'i1' and 'i2'. This function abstracts those special cases and just takes the dictionary of
        a spcht node and uses it to extract the neeed data and returns it. If there is no field it will return None instead
        :param dict sub_dict: a spcht node describing the data source
        :param str dict_field: name of the field in sub_dict, usually this is just 'field'
        :return: A list of values, might be empty
        :rtype: list
        """
        # 02.01.21 - Previously this also returned false, this behaviour was inconsistent
        if not dict_field:
            dict_field = sub_dict['field']
        if sub_dict['source'] == 'dict':
            if dict_field not in self._raw_dict:
                return []
            if not isinstance(self._raw_dict[dict_field], list):
                value = [self._raw_dict[dict_field]]
            else:
                value = []
                for each in self._raw_dict[dict_field]:
                    value.append(each)
            return SpchtUtility.list_wrapper(value)
        if sub_dict['source'] == 'tree':
            if not dict_tree:  # a tree dictionary might be a sub plot of existing data, but can also reside on the root of a normal dict source
                dict_tree = self._raw_dict
            if not dict_field:
                dict_field = sub_dict['field']
            # re.search(r"(?:\w+)+(>)*", dict_field) # ? i decided against a pattern check, if it fails it fails
            keys = dict_field.split(">")
            if keys:
                value = dict_tree
                for key in keys:
                    key = key.strip()
                    if key in value:
                        value = value[key]
                    else:
                        logger.debug(f"Cannot extract '{key}' cause it doesnt exist")
                        return []
                return value
            return []
            # re.split(r'(?<!\\)>', str) # ! compile spcht to have those splitters properly handled
        elif sub_dict['source'] == "marc" and self._m21_dict:
            field, subfield = SpchtUtility.slice_marc_shorthand(dict_field)
            if field is None:
                return []  # ! Exit 0 - No Match, exact reasons unknown
            if field not in self._m21_dict:
                return []  # ! Exit 1 - Field not present
            value = []
            if isinstance(self._m21_dict[field], list):
                for each in self._m21_dict[field]:
                    if str(subfield) in each:
                        m21_subfield = each[str(subfield)]
                        if isinstance(m21_subfield, list):
                            for every in m21_subfield:
                                value.append(every)
                        else:
                            value.append(m21_subfield)
                    else:
                        pass  # ? for now we are just ignoring that iteration
                if value is None:
                    return []  # ! Exit 2 - Field around but not subfield
                return SpchtUtility.list_wrapper(value)
            else:
                if subfield in self._m21_dict[field]:
                    if isinstance(self._m21_dict[field][subfield], list):
                        for every in self._m21_dict[field][subfield]:
                            value.append(every)
                        if value is None:  # i honestly cannot think why this should every happen, probably a faulty preprocessor
                            return []  # ! Exit 2 - Field around but not subfield

                        return value
                    else:
                        return [self._m21_dict[field][subfield]]
                else:
                    return []  # ! Exit 2 - Field around but not subfield
        else:
            return []

    def get_node_fields(self):
        """
            Returns a list of all the fields that might be used in processing of the data, this includes all
            alternatives, fallbacks and joined_field keys with source dictionary

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
        if 'id_fallback' in self._DESCRI:
            temp_list = Spcht.get_node_fields_recursion(self._DESCRI['id_fallback'])
            if temp_list:
                the_list += temp_list
        for node in self._DESCRI['nodes']:
            temp_list = Spcht.get_node_fields_recursion(node)
            if temp_list:
                the_list += temp_list
        return sorted(set(the_list))

    def get_node_predicates(self):
        """
            Returns a list of all different predicates that could be mapped by the loaded spcht file. As for get_node_fields
            this includes the referenced predicates in joined_map and fallbacks. This can theoretically return an empty list
            when there are less than 1 node in the spcht file. But that raises other questions anyway...

            :return: a list of string
            :rtype: list
        """
        if not self:  # requires initiated SPCHT Load
            self.debug_print("list_of_dict_fields requires loaded SPCHT")
            return []
        the_other_list = []
        for node in self._DESCRI['nodes']:
            temp_list = Spcht.get_node_predicates_recursion(node)
            if temp_list:
                the_other_list += temp_list
        # list set for deduplication, crude method but best i have for the moment
        return sorted(set(the_other_list))  # unlike the field equivalent this might return an empty list

    @staticmethod
    def get_node_predicates_recursion(sub_dict: dict) -> list:
        """
        Recursivly traverses a node to find the usage of predicate URIs

        This method is static instead of beeing inside SpchtUtility cause it shares close and specific functionality with
        the SpchtDescriptor Core function

        :param dict sub_dict: a Spcht Node
        :return: a list of strings
        :rtype: list
        """
        part_list = []
        if 'predicate' in sub_dict:
            part_list.append(sub_dict['predicate'])
        if 'joined_map' in sub_dict:
            for key, value in sub_dict['joined_map'].items():
                part_list.append(value)  # probably some duplicates here
        if 'fallback' in sub_dict:
            temp_list = Spcht.get_node_fields_recursion(sub_dict['fallback'])
            if temp_list:
                part_list += temp_list
        return part_list

    @staticmethod
    def get_node_fields_recursion(sub_dict: dict) -> list:
        """
        Traverses the given node recursivly to find all usage of fields

        This method is static instead of beeing inside SpchtUtility cause it shares close and specific functionality with
        the SpchtDescriptor Core function

        :param dict sub_dict: a Spcht Node
        :return: a list of used data fields
        :rtype: list
        """
        part_list = []
        if sub_dict['source'] == "dict":
            part_list.append(sub_dict['field'])
            if 'alternatives' in sub_dict:
                part_list += sub_dict['alternatives']
            if 'joined_field' in sub_dict:
                part_list.append(sub_dict['joined_field'])
            if 'insert_add_fields' in sub_dict:
                for each in sub_dict['insert_add_fields']:
                    part_list.append(each)
            if 'if_field' in sub_dict:
                part_list.append(sub_dict['if_field'])
        if 'fallback' in sub_dict:
            temp_list = Spcht.get_node_fields_recursion(sub_dict['fallback'])
            if temp_list:
                part_list += temp_list
        if 'sub_node' in sub_dict:
            for child_node in sub_dict['sub_node']:
                temp_list = Spcht.get_node_fields_recursion(child_node)
                if temp_list:
                    part_list += temp_list
        return part_list

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

    @property
    def debug(self):
        """
        'debug' is a switch that activates deep (and possibly colored) information about the mapping while doing so, it
        also makes some prints a bit more verbose and shows file paths while loading
        """
        return self._debug

    @debug.setter
    def debug(self, mode):
        if mode:
            self._debug = True
        else:
            self._debug = False

    @property
    def log_debug(self):
        """
        if log_debug is true everything that debug writes will also land in the log files, as i used debug print a
        lot to write continuous lines that concat but log writes a new line every call this will be extra spammy
        """
        return self._log_debug

    @log_debug.setter
    def log_debug(self, mode):
        if mode:
            self._log_debug = True
        else:
            self._log_debug = False


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


class SpchtNode:

    pos_keys = ["name", "source", "type", "required", "predicate", "alternatives", "fallback", "insert_into",
                "insert_add_fields", "if_value", "if_condition", "if_field", "prepend", "append", "match",
                "cut", "mapping", "mapping_settings", "joined_map", "joined_field", "comments"]

    def __init__(self, dict = None):
        self.name = ""
        self.source = "dict"
        self.type = "literal"
        self.required = "optional"
        self.predicate = ""
        self.alternatives = []
        self.fallback = None
        self.insert_into = ""
        self.insert_add_fields = []
        self.if_value = ""
        self.if_condition = ""
        self.if_field = ""
        self.prepend = ""
        self.append = ""
        self.match = ""
        self.cut = ""
        self.mapping = {}
        self.mapping_settings = {}
        self.joined_map = {}
        self.joined_field = ""
        self.comments = []

    def __len__(self):
        length = 0
        # this feels expensive
        for key in SpchtNode.pos_keys:
            if self.get(key):
                length += 1
        return length

    def __getitem__(self, item):
        if not isinstance(item, str):
            raise TypeError("key must be a string")
        if item in self.pos_keys:
            temp = self.__getattribute__(item)
            if temp:
                return temp
        else:
            raise KeyError(item)

    def __setitem__(self, key, value):
        if key in self.pos_keys:
            self.__setattr__(key, value)
        else:
            raise KeyError(f"SpchtNode doesnt accept custom keys")

    def __contains__(self, item):
        if item in SpchtNode.pos_keys:
            if self[item] is not None:
                return True
        else:
            return False

    def __iter__(self):
        return SpchtNodeIterator(self)

    def __repr__(self):
        text = "SpchtNode {"
        for key in self:
            if text != "SpchtNode {":
                text += ", "
            text += f"'{key}': "
            if isinstance(self[key], str):
                text += f"\"{self[key]}\""
            elif isinstance(self[key], (int, float)):
                text += f"{self[key]}"
            else:
                text += str(self[key])
        text += "}"
        return text

    def get(self, key, default=None):
        # the save variant of calling something, i used to implement this as "try self[key] but it failed"
        if not isinstance(key, str):
            return default
        if key in SpchtNode.pos_keys:
            temp = self.__getattribute__(key)
            if temp is not None:
                return temp
            else:
                return default
        else:
            return default

    def import_dict(self, dictionary: dict):
        """
        Takes the given dictionary that represents a spcht node and imports it in the correct structure
        """
        for key in SpchtNode.pos_keys:
            if key in dictionary:
                self[key] = dictionary[key]
                dictionary.pop(key)
        for foreign_key in dictionary:
            re.match(r"^(comment).*$")

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, source: str):
        allowed = ["dict", "marc", "literal"]
        if source in allowed:
            self._source = source
        else:
            self._source = "dict"  # TODO: Subject of change

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        if isinstance(name, str):
            self._name = name
        else:
            self._name = None

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, typus: str):
        allowed = ["literal", "triple"]
        if typus in allowed:
            self._type = typus
        else:
            self._type = "literal"

    @property
    def required(self):
        return self._required

    @required.setter
    def required(self, required: str):
        allowed = ["optional", "mandatory"]
        if required.lower() in allowed:
            self._required = required.lower()
        else:
            self._required = "optional"

    @property
    def fallback(self):
        if self._fallback is not None:
            return self._fallback
        else:
            return None

    @fallback.setter
    def fallback(self, fallback):
        if isinstance(fallback, SpchtNode):
            if self._recursive_check(fallback):
                raise AttributeError("any Fallback cannot be this node")
            # i realllly dont want recursion here, better check for subsequent sames
            self._fallback = fallback
        elif fallback is None:
            self._fallback = None
        else:
            self._fallback = None

    def _recursive_check(self, node) -> bool:
        """
        I cannot think of a single use case for recursive nodes, this whole concept of having a node
        in itself is already scary, therefore i try really hard to not allow self EVER in fallback
        :param Node: a SpchtNode Object
        :type Node: SpchtNode
        :return: true if there is another instance of self
        :rtype: bool
        """
        if node == self:
            return True
        if node.get('fallback') is not None:
            if node['fallback'] == self:
                return True
            else:
                return self._recursive_check(node['fallback'])
        return False

    @property
    def predicate(self):
        return self._predicate

    @predicate.setter
    def predicate(self, predicate: str):
        if isinstance(predicate, str):
            self._predicate = predicate
        else:
            self._predicate = None

    @property
    def alternatives(self):
        if len(self._alternatives) <= 0:
            return None
        else:
            return self._alternatives

    @alternatives.setter
    def alternatives(self, alternatives: list or str or None):
        if isinstance(alternatives, str):
            self._alternatives = [alternatives]
        elif isinstance(alternatives, list):
            self._alternatives = alternatives
        else:
            self._alternatives = None

    @property
    def insert_into(self):
        if self._insert_into == "":
            return None
        else:
            return self._insert_into

    @insert_into.setter
    def insert_into(self, insert_into: str):
        if isinstance(insert_into, str):
            self._insert_into = insert_into
        else:
            self._insert_into = None

    @property
    def insert_add_fields(self):
        if len(self._insert_add_fields) > 0:
            return self._insert_add_fields
        else:
            return None

    @insert_add_fields.setter
    def insert_add_fields(self, insert_add_fields: list):
        """
        Can be an empty list, str that are not truthy will result in None
        """
        if isinstance(insert_add_fields, list):
            self._insert_add_fields = insert_add_fields
        elif isinstance(insert_add_fields, str):
            if insert_add_fields:
                self._insert_add_fields = [insert_add_fields]
            else:
                self._insert_add_fields = None
        else:
            self._insert_add_fields = None

    @property
    def if_value(self):
        if isinstance(self._if_value, str) or isinstance(self._if_value, list):
            if self._if_value:
                return self._if_value
            else:
                return None
        else:
            return None

    @if_value.setter
    def if_value(self, if_value: str or list):
        if isinstance(if_value, (str, list)):
            self._if_value = if_value
        else:
            self._if_value = None

    @property
    def if_condition(self):
        if self._if_condition:
            return self._if_condition
        else:
            return None

    @if_condition.setter
    def if_condition(self, if_condition: str):
        if if_condition.lower() in SpchtUtility.SPCHT_BOOL_OPS:
            self._if_condition = if_condition.lower()
        else:
            self._if_condition = None

    @property
    def if_field(self):
        if self._if_field:
            return self._if_field
        else:
            return None

    @if_field.setter
    def if_field(self, if_field: str):
        if isinstance(if_field, str):
            self._if_field = if_field
        else:
            self._if_field = None

    # ! having properties which are named pre & append seems like a slight problem cause those are
    # ! function names for dictionaries and SpchtNode behaves like one..in some sort
    @property
    def prepend(self):
        if self._prepend:
            return self._prepend
        else:
            return None

    @prepend.setter
    def prepend(self, prepend: str):
        if isinstance(prepend, str):
            self._prepend = prepend
        else:
            self._prepend = None

    @property
    def append(self):
        if self._append:
            return self._append
        else:
            return None

    @append.setter
    def append(self, append: str):
        if isinstance(append, str):
            self._append = append
        else:
            self._append = None

    @property
    def match(self):
        if self._match:
            return self._match
        else:
            return None

    @match.setter
    def match(self, match: str):
        if isinstance(match, str):
            if SpchtUtility.validate_regex(match):
                self._match = match
            else:
                self._match = None
        else:
            self._match = None

    @property
    def cut(self):
        if self._cut:
            return self._cut
        else:
            return None

    @cut.setter
    def cut(self, cut: str):
        if isinstance(cut, str):
            if SpchtUtility.validate_regex(cut):
                self._cut = cut
            else:
                self._cut = None
        else:
            self._cut = None

    @property
    def mapping(self):
        if self._mapping:
            return self._mapping
        else:
            return None

    @mapping.setter
    def mapping(self, mapping: dict):
        """
        Sets the mapping file, this first tests if the dictionary is 1-dimension, this might be a bit expensive
        """
        if isinstance(mapping, dict):
            onward = True  # ? as i cannot return to break executions in setter this is necessary
            for key, value in mapping.items():
                if not isinstance(value, str) or not isinstance(key, str):
                    # i thought about making this self correcting, like converting ints/floats to strings
                    # decided against it
                    onward = False
                    break
            if onward:
                self._mapping = mapping
        else:
            self._mapping = None

    @property
    def mapping_settings(self):
        if self._mapping_settings:
            return self._mapping_settings
        else:
            return None

    @mapping_settings.setter
    def mapping_settings(self, mapping_settings: dict):
        # ? there is currently only one setting, and that is default, the other, reference gets
        # ? resolved before it even can become a node object
        if isinstance(mapping_settings, dict):
            self._mapping_settings = {}  # this seems rather clunky
            if mapping_settings.get('$default') and isinstance(mapping_settings['$default'], str):
                self._mapping_settings['$default'] = mapping_settings['$default']
            if mapping_settings.get('$inherit') and isinstance(mapping_settings['$inherit'], bool):
                self._mapping_settings['$inherit'] = mapping_settings['$inherit']
            if mapping_settings.get('$regex') and isinstance(mapping_settings['$regex'], bool):
                self._mapping_settings['$regex'] = mapping_settings['$regex']
            if mapping_settings.get('$casesens') and isinstance(mapping_settings['$casesens'], bool):
                self._mapping_settings['$casesens'] = mapping_settings['$casesens']
            if mapping_settings.get('$ref') and isinstance(mapping_settings['$ref'], bool):
                self._mapping_settings['$ref'] = mapping_settings['$ref']
            if not self._mapping_settings:
                self._mapping_settings = None
        else:
            self._mapping_settings = None

    @property
    def joined_field(self):
        if self._joined_field:
            return self._joined_field
        else:
            return None

    @joined_field.setter
    def joined_field(self, joined_field: str):
        if isinstance(joined_field, str):
            self._joined_field = joined_field
        else:
            self._joined_field = ""

    @property
    def joined_map(self):
        if self._joined_map:
            return self._joined_map
        else:
            return None

    @joined_map.setter
    def joined_map(self, joined_map: dict):
        if isinstance(joined_map, dict):
            onward = True
            for key in joined_map:
                if not isinstance(joined_map[key], str):
                    onward = False
                    break
            if onward:
                self._joined_map = joined_map
        else:
            self._joined_map = {}


class SpchtNodeIterator:
    def __init__(self, spcht_node: SpchtNode):
        self._spcht_node = spcht_node
        self._index = 0
        self._real_indices = []
        for key in SpchtNode.pos_keys:
            if self._spcht_node.get(key):
                self._real_indices.append(key)

    def __next__(self):
        if self._index < len(self._real_indices):
            result = self._real_indices[self._index]
            self._index += 1
            return result
        raise StopIteration