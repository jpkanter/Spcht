import copy
import json
import os
import re
import sys
from pathlib import Path

import pymarc
from pymarc.exceptions import RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid, \
    RecordDirectoryInvalid, NoFieldsFound
try:
    from termcolor import colored  # only needed for debug print
except ModuleNotFoundError:
    def colored(text, *args):
        return text  # throws args away returns non colored text

try:
    NORDF = False
    import rdflib
    from rdflib.namespace import DC, DCTERMS, DOAP, FOAF, SKOS, OWL, RDF, RDFS, VOID, XMLNS, XSD
except ImportError:
    NORDF = True


SPCHT_BOOL_OPS = {"equal":"==", "eq":"==","greater":">","gr":">","lesser":"<","ls":"<",
                    "greater_equal":">=","gq":">=", "lesser_equal":"<=","lq":"<=",
                  "unequal":"!=","uq":"!=","=":"==","==":"==","<":"<",">":">","<=":"<=",">=":">=","!=":"!=","exi":"exi"}

# the actual class


class Spcht:
    _DESCRI = None  # the finally loaded descriptor file with all references solved
    _SAVEAS = {}
    # * i do all this to make it more customizable, maybe it will never be needed, but i like having options
    std_out = sys.stdout
    std_err = sys.stderr
    debug_out = sys.stdout
    _debug = False
    _default_fields = ['fullrecord']

    def __init__(self, filename=None, check_format=False, debug=False):
        self.debugmode(debug)
        if filename is not None:
            self.load_descriptor_file(filename)
        # does absolutely nothing in itself

    def __repr__(self):
        if len(self._DESCRI) > 0:
            some_text = ""
            for item in self._DESCRI['nodes']:
                some_text += "{}[{},{}] - ".format(item['field'], item['source'], item['required'])
            return some_text[:-3]
        else:
            return "Empty Spcht"

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
        if self._DESCRI is None:
            return False
        # Preparation of Data to make it more handy in the further processing
        marc21_record = None  # setting a default here
        if marc21_source == "dict":
            try:
                marc21_record = Spcht.marc2list(raw_dict.get(marc21))
            except AttributeError as e:
                if e == "'str' object has no attribute 'get":
                    raise AttributeError(f"str has no get {raw_dict}")
                else:
                    raise AttributeError(e)  # pay it forward
            except ValueError as e:  # something is up
                self.debug_print("ValueException:", colored(e, "red"))
                marc21_record = None
            except TypeError as e:
                self.debug_print("TypeException:", colored(e, "red"))
                marc21_record = None
        elif marc21_source == "none":
            pass  # this is more a nod to anyone reading this than actually doing anything
        else:
            raise NameError("The choosen Source option doesnt exists")  # TODO alternative marc source options
            # ? what if there are just no marc data and we know that in advance?
        # generate core graph, i presume we already checked the spcht for being correct
        # ? instead of making one hard coded go i could insert a special round of the general loop right?
        sub_dict = {
            "name": "$Identifier$",  # this does nothing functional but gives the debug text a non-empty string
            "source": self._DESCRI['id_source'],
            "graph": "none",  # recursion node presumes a graph but we dont have that for the root, this is a dummy
            # i want to throw this exceptions, but the format is checked anyway right?!
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
                    return False
                else:
                    continue  # nothing happens
            else:
                if isinstance(facet, tuple):
                    if facet[1] is None:  # all those string checks
                        if node['required'] == "mandatory":
                            self.debug_print(colored(f"{node.get('name')} is an empty, mandatory string"), "red")
                            return False
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
                            return False  # there are checks before this, so this should, theoretically, not happen
                        else:
                            continue
                else:  # whatever it is, its weird if this ever happens
                    if node['required'] == "mandatory":
                        return False
                    else:
                        print(facet, colored("I cannot handle that for the moment", "magenta"), file=self.std_err)
                        raise TypeError("Unexpected return from recursive processor, this shouldnt happen")

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
        if len(triple_list) > 0:
            return triple_list
        else:
            return True
    # TODO: Error logs for known error entries and total failures as statistic
    # TODO: Grouping of graph descriptors in an @context

    def debug_print(self, *args, **kwargs):
        """
            prints only text if debug flag is set, prints to *self._debug_out*

            :param any args: pipes all args to a print function
            :param any kwargs: pipes all kwargs **except** file to a print function
        """
        # i wonder if it would have been easier to just set the out put for
        # normal prints to None and be done with it. Is this better or worse? Probably no sense questioning this
        if self._debug is True:
            if Spcht.is_dictkey(kwargs, "file"):
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
        if self._DESCRI is None:
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

    def descri_status(self):
        """
            Return the status of the loaded descriptor format

            :return: True if a working descriptor was load else false
            :rtype: bool
        """
        if self._DESCRI is not None:
            return True
        else:
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
        if Spcht.is_dictkey(self._SAVEAS, key):
            return self._SAVEAS[key]
        else:
            return None

    def cleanSaveaAs(self):
        # i originally had this in the "getSaveAs" function, but maybe you have for some reasons the need to do this
        # manually or not at all. i dont know how expensive set to list is. We will find out, eventually
        for key in self._SAVEAS:
            self._SAVEAS[key] = list(set(self._SAVEAS[key]))

    # other boiler plate, general stuff that is used to not write out a lot of code each time
    @staticmethod
    def is_dictkey(dictionary, *keys: str or int or list):
        """
            Checks the given dictionary or the given list of keys

            :param dict dictionary: a arbitarily dictionary
            :param str or int or list keys: a variable number of dictionary keys, either in a list of strings or as multiple strings
            :return: True if `all` keys are present in the dictionary, else false
            :rtype: bool
            :raises TypeError: if a non-dictionary is provided, or keys is a not valid dictionary key
        """
        if not isinstance(dictionary, dict):
            raise TypeError("Non Dictionary provided")
        for key in keys:
            if isinstance(key, list):
                for each in key:
                    if each not in dictionary:
                        return False
            if key not in dictionary:
                return False
        return True

    @staticmethod
    def list_has_elements(iterable):
        # technically this can check more than lists, but i use it to check some crude object on having objects or not
        for item in iterable:
            return True
        return False

    @staticmethod
    def list_wrapper(some_element):
        """
            I had the use case that i needed always a list of elements on a type i dont really care about as even when
            its just a list of one element.
        :param some_element: any variable that will be wrapped in a list
        :type some_element: any
        :return: Will return the element wrapped in the list unless its already a list, its its something weird returns None
        :rtype: list or None
        """
        if isinstance(some_element, list):
            return some_element
        elif isinstance(some_element, str) or isinstance(some_element, int) or isinstance(some_element, float):
            return [some_element]
        elif isinstance(some_element, bool):
            return [some_element]
        elif isinstance(some_element, dict):
            return [some_element]
        else:
            return None

    @staticmethod
    def all_variants(variant_matrix: list) -> list:
        """
        In case there is a list with lenght x containing a number of entries each
        then this will give you all possible combinations of them. And i am quite
        sure this is a solved problem but i didnt knew what to search for cause
        apparently i lack a classical education in that field so i had to improvise
        :param list variant_matrix: a list containing more lists
        :return: a list of lists of all combinations, throws various TypeErrors if something isnt alright
        :rtype: list
        """
        many = []
        for cur_idx in range(0, len(variant_matrix), 2):
            if len(variant_matrix)-1 > cur_idx:  # there is at least one more position to come
                if len(many) <= 0:  # this are elements 1 & 2
                    for each in variant_matrix[cur_idx]:
                        for every in variant_matrix[cur_idx + 1]:
                            many.append([each, every])
                else:  # these are elements 3+ and 4+
                    much = []
                    for each in variant_matrix[cur_idx]:
                        for every in variant_matrix[cur_idx + 1]:
                            much.append([each, every])
                    temp_list = []
                    for every in many:
                        for each in much:
                            temp_line = every.copy()
                            temp_line.append(each[0])
                            temp_line.append(each[1])
                            temp_list.append(temp_line)
                            del temp_line  # this should do nothing
                    many = temp_list
            else:  # this position is the last one
                if len(many) <= 0:
                    for each in variant_matrix[cur_idx]:
                        many.append([each])  # this is only one entry, a list of list is expected
                else:  # there was already a previous rounds with two entries in a "tuple"
                    temp_list = []
                    for every in many:
                        for each in variant_matrix[cur_idx]:
                            temp_line = every.copy()
                            temp_line.append(each)
                            temp_list.append(temp_line)
                            del temp_line
                    many = temp_list
            if not len(variant_matrix) >= cur_idx + 1:  # there is no next block after this one
                break  # does that really matter? we are doing strides of two anyway right?
        return many

    @staticmethod
    def match_positions(regex_pattern, zeichenkette: str) -> list or None:
        """
        Returns a list of position tuples for the start and end of the matched pattern in a string
        :param str regex_pattern: the regex pattern that matches
        :param str zeichenkette: the string you want to match against
        :return: either a list of tuples or None if no match was found, tuples are start and end of the position
        :rtype: list or None
        """
        # ? this is one of these things where there is surely a solution already but i couldn't find it in 5 minutes
        pattern = re.compile(regex_pattern)
        poslist = []
        for hit in pattern.finditer(zeichenkette):
            poslist.append((hit.start(), hit.end()))
        if len(poslist) <= 0:
            return None
        else:
            return poslist

    @staticmethod
    def insert_list_into_str(the_string_list: list, zeichenkette: str, regex_pattern=r'\{\}', pattern_len=2, strict=True):
        """
        Inserts a list of list of strings into another string that contains placeholder of the specified kind in regex_pattern
        :param list the_string_list: a list containing another list of strings, one element for each position
        :param str zeichenkette: the string you want to match against
        :param str regex_pattern: the regex pattern searching for the replacement
        :param int pattern_len: the lenght of the matching placeholder pattern, i am open for less clunky input on this
        :param bool strict: if true empty strings will mean nothing gets returned, if false empty strings will replace
        :return: a string with the inserted strings
        :rtype: str
        """
        # ! for future reference: "random {} {} {}".format(*list) will do almost what this does
        # ? and the next problem that has a solution somewhere but i couldn't find the words to find it
        positions = Spcht.match_positions(regex_pattern, zeichenkette)
        if len(the_string_list) > len(positions):  # more inserts than slots
            print(f" {len(the_string_list)} > {len(positions)}")  # ? technically debug text
            if strict:
                return None
            # else nothing for now, you would probably see that something isn't right right?
        if len(the_string_list) < len(positions):  # more slots than inserts
            if strict:
                return None  # would lead to empty space, cant have that
            else:
                for i in range(len(positions)-len(the_string_list)):
                    the_string_list.append("")  # to fill up
        slots_iter = iter(positions)  # * this is truly the first time i really need an iterator
        str_len_correction = 0  # * the difference the introduced strings make
        for each in the_string_list:
            if len(each) <= 0 and strict:
                return None
            start, end = next(slots_iter)
            start += str_len_correction
            end += str_len_correction  # * i am almost sure this can be solved more elegantly
            if len(zeichenkette) > end:
                zeichenkette = zeichenkette[0:start] + each + zeichenkette[end:len(zeichenkette)]
            else:
                zeichenkette = zeichenkette[0:start] + each
            str_len_correction += len(each)-pattern_len
        return zeichenkette

    @staticmethod
    def extract_dictmarc_value(raw_dict: dict, sub_dict: dict, dict_field="field") -> list or None:
        """
        In the corner case and context of this program there are (for now) two different kinds of 'raw_dict', the first
        is a flat dictionary containing a key:value relationship where the value might be a list, the second is the
        transformed marc21_dict which is the data retrieved from the marc_string inside the datasource. The transformation
        steps contained in spcht creates a dictionary similar to the 'normal' raw_dict. There are additional exceptions
        like that there are marc values without sub-key, for these the special subfield 'none' exists, there are also
        indicators that are actually standing outside of the normal data set but are included by the transformation script
        and accessable with 'i1' and 'i2'. This function abstracts those special cases and just takes the dictionary of
        a spcht node and uses it to extract the neeed data and returns it. If there is no field it will return None instead
        :param dict raw_dict: either the solr dictionary or the tranformed marc21_dict
        :param dict sub_dict: a spcht node describing the data source
        :param str dict_field: name of the field in sub_dict, usually this is just 'field'
        :return: Either the value extracted or None if no value could be found
        :rtype: list or None
        """
        # 02.01.21 - Previously this also returned false, this behaviour was inconsistent
        if sub_dict['source'] == 'dict':
            if not Spcht.is_dictkey(raw_dict, sub_dict[dict_field]):
                return None
            if not isinstance(raw_dict[sub_dict[dict_field]], list):
                value = [raw_dict[sub_dict[dict_field]]]
            else:
                value = []
                for each in raw_dict[sub_dict[dict_field]]:
                    value.append(each)
            return value
        elif sub_dict['source'] == "marc":
            field, subfield = Spcht.slice_marc_shorthand(sub_dict[dict_field])
            if field is None:
                return None  # ! Exit 0 - No Match, exact reasons unknown
            if not Spcht.is_dictkey(raw_dict, field):
                return None  # ! Exit 1 - Field not present
            value = None
            if isinstance(raw_dict[field], list):
                for each in raw_dict[field]:
                    if Spcht.is_dictkey(each, str(subfield)):
                        m21_subfield = each[str(subfield)]
                        if isinstance(m21_subfield, list):
                            for every in m21_subfield:
                                value = Spcht.fill_var(value, every)
                        else:
                            value = Spcht.fill_var(value, m21_subfield)
                    else:
                        pass  # ? for now we are just ignoring that iteration
                if value is None:
                    return None  # ! Exit 2 - Field around but not subfield

                if isinstance(value ,list):
                    return value  # * Value Return
                else:
                    return [value]

            else:
                if Spcht.is_dictkey(raw_dict[field], subfield):
                    if isinstance(raw_dict[field][subfield], list):
                        for every in raw_dict[field][subfield]:
                            value = Spcht.fill_var(value, every)
                        if value is None:  # i honestly cannot think why this should every happen, probably a faulty preprocessor
                            return None  # ! Exit 2 - Field around but not subfield

                        if isinstance(value, list):
                            return value  # * Value Return
                        else:
                            return [value]
                    else:
                        return [raw_dict[field][subfield]]  # * Value Return  # a singular value
                else:
                    return None  # ! Exit 2 - Field around but not subfield

    @staticmethod
    def fill_var(current_var: list or str, new_var: any) -> list or any:
        """
        this is another of those functions that probably already exist or what i am trying to do is not wise. Anway
        this either directly returns new_var if current_var is either an empty string or None. If not it creates a new
        list with current_var as first element and new_var as second OR if current_var is already a list it just
        appends, why i am doing that? Cause its boilerplate code and i otherwise had to write it 5 times in one function
        :param list or str current_var: a variable that might be empty or is not
        :param any new_var: the new value that is to be added to current_var
        :return: most likely a list or just new_var
        :rtype: list or any
        """
        if current_var is None:
            return new_var
        if isinstance(current_var, str) and current_var == "":  # a single space would be enough to not do things
            return [new_var]
        if isinstance(current_var, list):
            current_var.append(new_var)
            return current_var
        return [current_var, new_var]

    @staticmethod
    def is_float(string):
        """
        Checks if a string can be converted to a float
        :param str string: a string of any kind
        :return: True if its possible, False if not
        :rtype: bool
        """
        # ! why exactly i am writing such kind of functions all the time? Do i lack the vision to see the build ins?
        try:
            float(string)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_int(string):
        """
        Checks if a string can be converted to an int
        :param str string: a string of any kind
        :return: True if possible, False if not
        :rtype: bool
        """
        try:
            int(string)
            return True
        except ValueError:
            return False

    @staticmethod
    def if_possible_make_this_numerical(value: str):
        """Converts a given var in the best kind of numerical value that it can, if it can be an int it will be one,
        :param str value: any kind of value, hopefully something 1-dimensional
        :return: the converted value, might be an int, might be a float, or just the object that came
        :rtype: int or float or any
        """
        if Spcht.is_int(value):
            return int(value)
        elif Spcht.is_float(value):
            return float(value)
        else:
            return value

    @staticmethod
    def slice_marc_shorthand(string: str) -> tuple:
        """
        Splits a string and gives a tuple of two elements containing the Main Number and the subfield of a marc shorthand
        Calls a regex check to make sure the format is corret
        :param str string: a string describing a marc shorthand, should look like this '504:a', second part can also be a number or 'i1', 'i2' and 'none'
        :return: either None and False or field and subfield
        :rtype: tuple
        """
        match = re.match(r"^[0-9]{1,3}:\w*$", string)
        if match:
            a_list = string.split(":")
            return int(str(a_list[0]).lstrip("0")), a_list[1]
        else:
            return None, False  # this is a tuple right ?

    @staticmethod
    def validate_regex(regex_str):
        """
            Checks if a given string is valid regex

            :param str regex_str: a suspicios string that may or may not be valid regex
            :rtype: bool
            :return: True if valid regex was give, False in case of TypeError or re.error
        """
        # another of those super basic function where i am not sure if there isn't an easier way
        try:
            re.compile(regex_str)
            return True
        except re.error:
            return False
        except TypeError:  # for the string not being one
            return False

    @staticmethod
    def marc21_fixRecord(record, validation=False, record_id=0, replace_method='decimal'):
        """
        Not my own work. Attributed to Bernhard Hering (SLUB). Converts the raw string coming from a solr source into
        something readable by replacing the special chars with the correct representation, further uses pymarc
        to process  the given data.
        :param str record: Marc21 raw record as given in a database field
        :param int record_id: ID that gets displayed in the validation error message, default is 0
        :param bool validation: if true pymarc is used to validate the record right here, returns false if not succesful
        :param str replace_method: 'decimal', 'unicode' or 'hex'
        :return: a fixed marc21 Record string with the correct characters, nothing else
        :rtype: str
        """
        # imported from the original finc2rdf.py
        # its needed cause the marc21_fullrecord entry contains some information not in the other solr entries
        # record id is only needed for the error text so its somewhat transparent where stuff went haywire
        # i think what it does is replacing some characters in the response of solr, the "replace_method" variable
        # was a clue.
        replace_methods = {
            'decimal': (('#29;', '#30;', '#31;'), ("\x1D", "\x1E", "\x1F")),
            'unicode': (('\u001d', '\u001e', '\u001f'), ("\x1D", "\x1E", "\x1F")),
            'hex': (('\x1D', '\x1E', '\x1F'), ("\x1D", "\x1E", "\x1F"))
        }
        marcFullRecordFixed = record
        # replaces all three kinds of faults in the choosen method (decimal, unicode or hex)
        # this method is written broader than necessary, reusable?
        for i in range(0, 3):
            marcFullRecordFixed = marcFullRecordFixed.replace(replace_methods.get(replace_method)[0][i],
                                                              replace_methods.get(replace_method)[1][i])
        if validation:
            try:
                reader = pymarc.MARCReader(marcFullRecordFixed.encode('utf8'), utf8_handling='replace')
                marcrecord = next(reader)  # what does this? - handling more than one marc entry i would guess
            except (
                    RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid,
                    RecordDirectoryInvalid,
                    NoFieldsFound, UnicodeDecodeError) as e:
                print(f"record id {record_id}: {str(e)}", file=sys.stderr)
                return False
        # TODO: Clean this up
        return marcFullRecordFixed

    @staticmethod
    def marcleader2report(leader, output=sys.stdout):
        # outputs human readable information about a marc leader
        # text source: https://www.loc.gov/marc/bibliographic/bdleader.html
        marc_leader_text = {
            "05": {"label": "Record status",
                   "a": "Increase in encoding level",
                   "c": "Corrected or revised",
                   "d": "Deleted",
                   "n": "New",
                   "p": "Increase in encoding level from prepublication"
                   },
            "06": {"label": "Type of record",
                   "a": "Language material",
                   "c": "Notated music",
                   "d": "Manuscript notated music",
                   "e": "Cartographic material",
                   "f": "Manuscript cartographic material",
                   "g": "Projected medium",
                   "i": "Non-musical sound recording",
                   "j": "Musical sound recourding",
                   "k": "Two-dimensional non-projectable graphic",
                   "m": "Computer file",
                   "o": "Kit",
                   "p": "Mixed Materials",
                   "r": "Three-dimensional or naturally occurring object",
                   "t": "Manuscript language material"
                   },
            "07": {"label": "Bibliographic level",
                   "a": "Monographic component part",
                   "b": "Serial component part",
                   "c": "Collection",
                   "d": "Subunit",
                   "i": "Integrating resource",
                   "m": "Monograph/Item",
                   "s": "Serial"
                   },
            "08": {"label": "Type of control",
                   " ": "No specified type",
                   "a": "archival"
                   },
            "09": {"label": "Character coding scheme",
                   " ": "MARC-8",
                   "a": "UCS/Unicode"
                   },
            "18": {"label": "Descriptive cataloging form",
                   " ": "Non-ISBD",
                   "a": "AACR 2",
                   "c": "ISBD punctuation omitted",
                   "i": "ISBD punctuation included",
                   "n": "Non-ISBD punctuation omitted",
                   "u": "Unknown"
                   }
        }

        for i in range(23):
            if i < 4 or (12 <= i <= 15):
                continue
            if i == 5:  # special case one, length is on the fields 0-4
                print("Record length: " + leader[0:5])
                continue
            if i == 16:
                print("Leader & directory length " + leader[12:16])
            if Spcht.is_dictkey(marc_leader_text, f'{i:02d}'):
                print(marc_leader_text.get(f'{i:02d}').get('label') + ": " + marc_leader_text.get(f'{i:02d}').get(
                    leader[i], "unknown"), file=output)

    @staticmethod
    def normalize_marcdict(a_so_called_dictionary):
        # all this trouble cause for some reasons pymarc insists on being awful
        # to explain it a bit further, this is the direct out of .as_dict() for an example file
        # {'leader': '02546cam a2200841   4500', 'fields': [{'001': '0-023500557'}, ...
        # the leader is okay, but why are the fields a list of single dictionaries? i really dont get it
        the_long_unnecessary_list = a_so_called_dictionary.get('fields', None)
        an_actual_dictionary = {}
        if the_long_unnecessary_list is not None:
            for mini_dict in the_long_unnecessary_list:
                key = next(iter(mini_dict))  # Python 3.7 feature
                an_actual_dictionary[key] = mini_dict[key]
            return an_actual_dictionary
        raise ValueError("Spcht.normalize_marcdict: Couldnt find any fields")

    @staticmethod
    def marc2list(marc_full_record, validation=True, replace_method='decimal'):
        """
            This Converts a given, binary marc record as contained in the files i have seen so far into something that is
            actually usable -> a dictionary with proper keys and subkeys

            :param str marc_full_record: string containing the full marc21 record
            :param bool validation: Toogles whether the fixed record will be validated or not
            :param str replace_method: One of the three replacement methods: [decimal, unicode, hex]
            :return: Returns a dictionary of ONE Marc Record if there is only one or a list of dictionaries, each a marc21 entry
            :rtype: dict or list
            :raises ValueError: In Case the normalize_marcdict function fails, probably due a failure before
            :raises TypeError: If the given marc data is not a string but something else
        """
        clean_marc = Spcht.marc21_fixRecord(marc_full_record, validation=validation, replace_method=replace_method)
        if isinstance(clean_marc, str):  # would be boolean if something bad had happen
            reader = pymarc.MARCReader(clean_marc.encode('utf-8'))
            marc_list = []
            for record in reader:
                try:
                    record_dict = Spcht.normalize_marcdict(record.as_dict())  # for some reason i cannot access all fields,
                    # also funny, i could probably use this to traverse the entire thing ,but better save than sorry i guess
                    # sticking to the standard in case pymarc changes in a way or another
                except ValueError as err:
                    raise err # usually when there is some none-dictionary given
                marcdict = {}
                for i in range(1000):
                    if record[f'{i:03d}'] is not None:
                        for single_type in record.get_fields(f'{i:03d}'):
                            temp_subdict = {}
                            for subfield in single_type:
                                if Spcht.is_dictkey(temp_subdict, subfield[0]):
                                    if not isinstance(temp_subdict[subfield[0]], list):
                                        temp_subdict[subfield[0]] = [temp_subdict[subfield[0]]]
                                    temp_subdict[subfield[0]].append(subfield[1])
                                else:
                                    temp_subdict[subfield[0]] = subfield[1]
                                # ? this is a bit unfortunately cause the indicator technically hangs at the subfield
                                # ? not the individual item of the subfield, i will just copy it to every single one
                                if hasattr(single_type, 'indicator1') and single_type.indicator1.strip() != "":
                                    temp_subdict['i1'] = single_type.indicator1
                                if hasattr(single_type, 'indicator2') and single_type.indicator2.strip() != "":
                                    temp_subdict['i2'] = single_type.indicator2

                            if Spcht.is_dictkey(marcdict, i):  # already exists, transforms into list
                                if not isinstance(marcdict[i], list):
                                    marcdict[i] = [marcdict[i]]
                                marcdict[i].append(temp_subdict)
                            else:
                                marcdict[i] = temp_subdict
                            try:
                                if not Spcht.list_has_elements(single_type):
                                    temp = record_dict.get(f'{i:03d}', None)
                                    if temp is not None:
                                        marcdict[i]['none'] = temp
                            except TypeError:
                                print("NOTICE: TypeError in Spcht.Marc2List", f'{i:03d}', record_dict.get(f'{i:03d}', None))
                            # normal len doesnt work cause no method, flat element
                marc_list.append(marcdict)
            if 0 < len(marc_list) < 2:
                return marc_list[0]
            elif len(marc_list) > 1:
                return marc_list
            else:
                return None
        else:
            raise TypeError("Spcht.marc2list: given 'clean_marc' is not of type str'")
        # i am astonished how diverse the return statement can be, False if something went wrong, None if nothing gets
        # returned but everything else went fine, although, i am not sure if that even triggers and under what circumstances

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
        if not Spcht.check_format(descriptor, base_path=spcht_path.parent):
            return False
        # * goes through every mapping node and adds the reference files, which makes me basically rebuild the thing
        # ? python iterations are not with pointers, so this will expose me as programming apprentice but this will work
        new_node = []
        for item in descriptor['nodes']:
            try:
                a_node = self._load_ref_node(item, str(spcht_path.parent))
            except Exception as e:
                self.debug_print("spcht_ref", colored(e, "red"))
                #raise ValueError(f"ValueError while working through Reference Nodes: '{e}'")
                return False
            new_node.append(a_node)
        descriptor['nodes'] = new_node  # replaces the old node with the new, enriched ones
        self._DESCRI = descriptor
        return True

    def _load_ref_node(self, node_dict, base_path) -> dict:
        """

        :param dict node_dict:
        :param str base_path:
        :return: Returns
        :rtype:  dict
        :raises ValueError:
        :raises TypeError: if the loaded file is the wrong format
        :raises FileNotFounderror: if the given file could not be found
        """
        # We are again in beautiful world of recursion. Each node can contain a mapping and each mapping can contain
        # a reference to a mapping json. i am actually quite worried that this will lead to performance issues
        # TODO: Research limits for dictionaries and performance bottlenecks
        # so, this returns False and the actual loading operation returns None, this is cause i think, at this moment,
        # that i can check for isinstance easier than for None, i might be wrong and i have not looked into the
        # cost of that operation if that is ever a concern
        if Spcht.is_dictkey(node_dict, 'fallback'):
            try:
                node_dict['fallback'] = self._load_ref_node(node_dict['fallback'], base_path)  # ! there it is again, the cursed recursion thing
            except Exception as e:
                raise e  # basically lowers the exception by one level
        if Spcht.is_dictkey(node_dict, 'mapping_settings') and node_dict['mapping_settings'].get('$ref') is not None:
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
                if not Spcht.is_dictkey(node_dict['mapping'], key):  # existing keys have priority
                    node_dict['mapping'][key] = value
            del map_dict
            # clean up mapping_settings node
            del (node_dict['mapping_settings']['$ref'])
            if len(node_dict['mapping_settings']) <= 0:
                del (node_dict['mapping_settings'])  # if there are no other entries the entire mapping settings goes

        if Spcht.is_dictkey(node_dict, 'graph_map_ref'):  # mostly boiler plate from above, probably not my brightest day
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

    def _recursion_node(self, sub_dict, raw_dict, marc21_dict=None):
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
            if Spcht.is_dictkey(sub_dict, "if_condition"):  # condition cancels out the entire node, triggers callback
                if not self._handle_if(marc21_dict, sub_dict, 'flexible'):
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)  # ! i created call_fallback just for this

            m21_value = Spcht.extract_dictmarc_value(marc21_dict, sub_dict)
            if m21_value is None:
                self.debug_print(colored(f"Marc around but not field {sub_dict['field']}", "yellow"), end=" > ")
                return self._call_fallback(sub_dict, raw_dict, marc21_dict)

            self.debug_print(colored("Marc21", "yellow"), end="-> ")  # the first step
            # ? Whats the most important step a man can take? --- Always the next one

            if m21_value is False:  # r"^[0-9]{1,3}:\w*$"
                self.debug_print(colored(f"✗ field found but subfield not present in marc21 dict", "magenta"), end=" > ")
                return self._call_fallback(sub_dict, raw_dict, marc21_dict)

            if Spcht.is_dictkey(sub_dict, 'graph_field'):  # original boilerplate from dict
                graph_value = self._graph_map(marc21_dict, sub_dict)
                if graph_value is not None:  # ? why i am even checking for that? Fallbacks, that's why
                    self.debug_print(colored("✓ graph_field", "green"))
                    return graph_value
                self.debug_print(colored(f"✗ graph mapping could not be fullfilled", "magenta"), end=" > ")
            elif Spcht.is_dictkey(sub_dict, 'insert_into'):
                inserted_ones = self._inserter_string(marc21_dict, sub_dict)
                if inserted_ones is not None:
                    self.debug_print(colored("✓ insert_into", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], inserted_ones)
                    # ! this handling of the marc format is probably too simply
            else:
                temp_value = Spcht._node_preprocessing(m21_value, sub_dict)
                if temp_value is None or len(temp_value) <= 0:
                    self.debug_print(colored(f"✗ value preprocessing returned no matches", "magenta"), end=" > ")
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)

                self.debug_print(colored(f"✓ field&subfield", "green"))
                return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))

            # TODO: gather more samples of awful marc and process it
        elif sub_dict['source'] == "dict":
            self.debug_print(colored("Source Dict", "yellow"), end="-> ")

            if Spcht.is_dictkey(sub_dict, "if_condition"):  # condition cancels out the entire node, triggers callback
                if not self._handle_if(raw_dict, sub_dict, 'flexible'):
                    return self._call_fallback(sub_dict, raw_dict, marc21_dict)  # ! i created call_fallback just for this

            # graph_field matching - some additional checks necessary
            # the existence of graph_field invalidates the rest if graph field does not match
            if Spcht.is_dictkey(sub_dict, "graph_field"):
                # ? i really hope this works like intended, if there is graph_field, do nothing of the normal matching
                graph_value = self._graph_map(raw_dict, sub_dict)
                if graph_value is not None:  # ? why i am even checking for that? Fallbacks, that's why
                    self.debug_print(colored("✓ graph_field", "green"))
                    return graph_value
            # normal field matching
            elif Spcht.is_dictkey(sub_dict, 'insert_into'):  # ? similar to graph field this is an alternate mode
                inserted_ones = self._inserter_string(raw_dict, sub_dict)
                if inserted_ones is not None:
                    self.debug_print(colored("✓ insert_field", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(inserted_ones, sub_dict))
                # ! dont forget post processing
            elif Spcht.is_dictkey(raw_dict, sub_dict['field']):  # main field name
                temp_value = raw_dict[sub_dict['field']]  # the raw value
                temp_value = Spcht._node_preprocessing(temp_value, sub_dict)  # filters out entries
                if temp_value is not None and len(temp_value) > 0:
                    temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                    self.debug_print(colored("✓ simple field", "green"))
                    return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))
            # ? since i prime the sub_dict what is even the point for checking the existence of the key, its always there
            # alternatives matching, like field but as a list of alternatives
            elif Spcht.is_dictkey(sub_dict, 'alternatives') and sub_dict['alternatives'] is not None:  # traverse list of alternative field names
                self.debug_print(colored("Alternatives", "yellow"), end="-> ")
                for entry in sub_dict['alternatives']:
                    if Spcht.is_dictkey(raw_dict, entry):
                        temp_value = Spcht._node_preprocessing(raw_dict[entry], sub_dict)
                        if temp_value is not None and len(temp_value) > 0:
                            temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'),
                                            sub_dict.get('mapping_settings'))
                            self.debug_print(colored("✓ alternative field", "green"))
                            return Spcht._node_return_iron(sub_dict['graph'], self._node_postprocessing(temp_value, sub_dict))
        return self._call_fallback(sub_dict, raw_dict, marc21_dict)

    def _call_fallback(self, sub_dict, raw_dict, marc21_dict):
        if Spcht.is_dictkey(sub_dict, 'fallback') and sub_dict['fallback'] is not None:  # we only get here if everything else failed
            # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
            # * librarian was who wrote the descriptor format
            self.debug_print(colored("Fallback triggered", "yellow"), end="-> ")
            recursion_node = copy.deepcopy(sub_dict['fallback'])
            if not Spcht.is_dictkey(recursion_node, 'graph'):
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
    def _node_preprocessing(value: str or list, sub_dict: dict, key_prefix="") -> str or list or None:
        """
        used in the processing after entries were found, this acts basically as filter for everything that does
        not match the provided regex in sub_dict

        :param str or list value: value of the found field/subfield, can be a list
        :param dict sub_dict: sub dictionary containing a match key, if not nothing happens
        :return: None if not a single match was found, str or list if one or more matches were made or no 'match'
        :rtype: str or list or None
        """
        # if there is a match-filter, this filters out the entry or all entries not matching
        if not Spcht.is_dictkey(sub_dict, f'{key_prefix}match'):
            return value  # the nothing happens clause
        if isinstance(value, str):
            finding = re.search(sub_dict[f'{key_prefix}match'], str(value))
            if finding is not None:
                return finding.string
            else:
                return None
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                finding = re.search(sub_dict[f'{key_prefix}match'], str(item))
                if finding is not None:
                    list_of_returns.append(finding.string)
            if 0 < len(list_of_returns) < 2:
                return list_of_returns[0]  # if there is only one surviving element there is no point in returning a list
                # although an argument could be made that always list would be more uniform....
            elif len(list_of_returns) > 1:
                return list_of_returns
            else:
                return None
        else:  # fallback if its anything else i dont intended to handle with this
            return value

    def _node_postprocessing(self, value: str or list, sub_dict: dict, key_prefix=""):
        """
        Used after filtering and mapping took place, this appends the pre and post text before the value if provided,
        further also replaces part of the value with the replacement text or just removes the part that is
        specified by cut if no replacement was provided. Without 'cut' there will be no replacement.
        Order is first replace and cut and THEN appending text

        :param str or list value: the content of the field that got mapped till now
        :param dict sub_dict: the subdictionary of the node containing the 'cut', 'prepend', 'append' and 'replace' key
        :return: returns the same number of provided entries as input, if only one its just a string
        :rtype: str or list
        """
        # after having found a value for a given key and done the appropriate mapping the value gets transformed
        # once more to change it to the provided pattern

        if isinstance(value, str):
            if Spcht.is_dictkey(sub_dict, f'{key_prefix}cut'):
                value = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), value)
                self._addToSaveAs(value, sub_dict)
            else:
                self._addToSaveAs(value, sub_dict)
            return sub_dict.get(f'{key_prefix}prepend', "") + value + sub_dict.get(f'{key_prefix}append', "")
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                if not Spcht.is_dictkey(sub_dict, f'{key_prefix}cut'):
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + str(item) + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._addToSaveAs(item, sub_dict)
                else:
                    pure_filter = re.sub(sub_dict.get(f'{key_prefix}cut', ""), sub_dict.get(f'{key_prefix}replace', ""), str(item))
                    rest_str = sub_dict.get(f'{key_prefix}prepend', "") + pure_filter + sub_dict.get(f'{key_prefix}append', "")
                    if key_prefix != "":
                        self._addToSaveAs(pure_filter, sub_dict)
                list_of_returns.append(rest_str)
            if len(list_of_returns) == 1:
                return list_of_returns[0]  # we are handling lists later anyway, but i am cleaning here a bit
            else:
                return list_of_returns  # there should always be elements, even if they are empty, we are staying faithful here
        else:  # fallback if its anything else i dont intended to handle with this
            return value

    def _addToSaveAs(self, value, sub_dict):
        # this was originally 3 lines of boilerplate inside postprocessing, i am not really sure if i shouldn't have
        # left it that way, i kinda dislike those mini functions, it divides the code
        if Spcht.is_dictkey(sub_dict, "saveas"):
            if self._SAVEAS.get(sub_dict['saveas'], None) is None:
                self._SAVEAS[sub_dict['saveas']] = []
            self._SAVEAS[sub_dict['saveas']].append(value)

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
            if Spcht.is_dictkey(settings, '$default'):
                the_default = settings['$default']
                # if the value is boolean True it gets copied without mapping
                # if the value is a str that is default, False does nothing but preserves the default state of default
                # Python allows me to get three "boolean" states here done, value, yes and no. Yes is inheritance
            if Spcht.is_dictkey(settings, '$type'):
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
            if Spcht.is_dictkey(mapping, value):  # rigid key mapping
                return mapping.get(value)
            elif isinstance(the_default, bool) and the_default is True:
                return value
            elif isinstance(the_default, str):
                return the_default
            else:
                return None
                # ? i was contemplating whether it should return value or None. None is the better one i think
                # ? cause if we no default is defined we probably have a reason for that right?
        else:
            print("field contains a non-list, non-string: {}".format(type(value)), file=self.std_err)

    def _graph_map(self, raw_dict, sub_dict):
        # originally i had this as part of the node_recursion function, but i encountered the problem
        # where i had to perform a lot of checks till i can actually do anything which in the structure i had
        # would have resulted in a very nested if chain, as a separate function i can do this more neatly and readable
        if Spcht.extract_dictmarc_value(raw_dict, sub_dict, 'field') is None or \
                Spcht.extract_dictmarc_value(raw_dict, sub_dict, 'graph_field') is None:
            # this is a bit awkward, dict doesnt check for existence, marc does, neither do for graph_field, hmm
            self.debug_print(colored(f"✗ no field or graph_field not present", "magenta"), end=" > ")
            return None
        field = Spcht.extract_dictmarc_value(raw_dict, sub_dict, "field")  # this is just here cause i was tired of typing the full thing every time
        graph_field = Spcht.extract_dictmarc_value(raw_dict, sub_dict, "graph_field")
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
        if Spcht.extract_dictmarc_value(raw_dict, sub_dict) is None:
            return None
        # check what actually exists in this instance of raw_dict
        inserters = []  # each entry is a list of strings that are the values stored in that value, some dict fields are
        # more than one value, therefore everything gets squashed into a list
        if sub_dict['source'] != "dict" and sub_dict['source'] != "marc":
            print(f"Unknown source {sub_dict['source']}found, are you from the future relative to me?")
            return None
        value = Spcht.extract_dictmarc_value(raw_dict, sub_dict)
        if value is None or value is False:
            return None
        inserters.append(Spcht.list_wrapper(value))

        if Spcht.is_dictkey(sub_dict, 'insert_add_fields'):
            for each in sub_dict['insert_add_fields']:
                pseudo_dict = {"source": sub_dict['source'], "field": each}
                value = Spcht.extract_dictmarc_value(raw_dict, pseudo_dict)
                if value is not None and value is not False:
                    inserters.append(Spcht.list_wrapper(value))
                else:
                    inserters.append([""])
        # all_variants iterates through the separate lists and creates a new list or rather matrix with all possible combinations
        all_texts = Spcht.all_variants(inserters)
        self.debug_print(colored(f"Inserts {len(all_texts)}", "grey"), end=" ")
        all_lines = []
        for each in all_texts:
            replaced_line = Spcht.insert_list_into_str(each, sub_dict['insert_into'], r'\{\}', 2, True)
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
        if Spcht.is_dictkey(SPCHT_BOOL_OPS, sub_dict['if_condition']):
            sub_dict['if_condition'] = SPCHT_BOOL_OPS[sub_dict['if_condition']]
        else:
            return False  # if your comparator is false nothing can be true

        comparator_value = self.extract_dictmarc_value(raw_dict, sub_dict, "if_field")

        if sub_dict['if_condition'] == "exi":
            if comparator_value is None:
                self.debug_print(colored(f"✗ field {sub_dict['if_field']} doesnt exist", "blue"), end="-> ")
                return False
            self.debug_print(colored(f"✓ field {sub_dict['if_field']}  exists", "blue"), end="-> ")
            return True

        # ! if we compare there is no if_value, so we have to do the transformation later
        sub_dict['if_value'] = Spcht.if_possible_make_this_numerical(sub_dict['if_value'])

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
        comparator_value = Spcht.list_wrapper(comparator_value)
        # ? i really hope one day i learn how to do this better, this seems SUPER clunky, i am sorry
        failure_list = []
        for each in comparator_value:
            each = Spcht.if_possible_make_this_numerical(each)
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
        self.debug_print(colored(f"✗ {sub_dict['if_field']} was not {sub_dict['if_condition']} {sub_dict['if_value']} but {failure_list} instead", "magenta"), end="-> ")
        return False

    def get_node_fields(self):
        """
            Returns a list of all the fields that might be used in processing of the data, this includes all
            alternatives, fallbacks and graph_field keys with source dictionary

            :return: a list of strings
            :rtype: list
        """
        if self._DESCRI is None:  # requires initiated SPCHT Load
            self.debug_print("list_of_dict_fields requires loaded SPCHT")
            return None

        the_list = []
        the_list += self._default_fields
        if self._DESCRI['id_source'] == "dict":
            the_list.append(self._DESCRI['id_field'])
        temp_list = Spcht._get_node_fields_recursion(self._DESCRI['id_fallback'])
        if temp_list is not None and len(temp_list) > 0:
            the_list += temp_list
        for node in self._DESCRI['nodes']:
            temp_list = Spcht._get_node_fields_recursion(node)
            if temp_list is not None and len(temp_list) > 0:
                the_list += temp_list
        return sorted(set(the_list))

    @staticmethod
    def _get_node_fields_recursion(sub_dict):
        part_list = []
        if sub_dict['source'] == "dict":
            part_list.append(sub_dict['field'])
            if Spcht.is_dictkey(sub_dict, 'alternatives'):
                part_list += sub_dict['alternatives']
            if Spcht.is_dictkey(sub_dict, 'graph_field'):
                part_list.append(sub_dict['graph_field'])
            if Spcht.is_dictkey(sub_dict, 'insert_add_fields'):
                for each in sub_dict['insert_add_fields']:
                    part_list.append(each)
            if Spcht.is_dictkey(sub_dict, 'if_field'):
                part_list.append(sub_dict['if_field'])
        if Spcht.is_dictkey(sub_dict, 'fallback'):
            temp_list = Spcht._get_node_fields_recursion(sub_dict['fallback'])
            if temp_list is not None and len(temp_list) > 0:
                part_list += temp_list
        return part_list

    def set_default_fields(self, list_of_strings):
        """
        Sets the fields that are always included by get_node_fields, useful if your marc containing field isnt
        otherwise included in the dictionary

        :para list_of_strings list: a list of strings that replaces the previous list
        :return: Returns nothing but raises a TypeException is something is off
        :rtype None:
        """
        if not isinstance(list_of_strings, list):
            raise TypeError("given parameter is not a list")
        for each in list_of_strings:
            if not isinstance(each, str):
                raise TypeError("an element in the list is not a string")
        # i might as well throw a TypeException shouldn't i?
        self._default_fields = list_of_strings

    def get_node_graphs(self):
        """
            Returns a list of all different graphs that could be mapped by the loaded spcht file. As for get_node_fields
            this includes the referenced graphs in graph_map and fallbacks. This can theoretically return an empty list
            when there are less than 1 node in the spcht file. But that raises other questions anyway...

            :return: a list of string
            :rtype: list
        """
        if self._DESCRI is None:  # requires initiated SPCHT Load
            self.debug_print("list_of_dict_fields requires loaded SPCHT")
            return None
        the_other_list = []
        for node in self._DESCRI['nodes']:
            temp_list = Spcht._get_node_graphs_recursion(node)
            if temp_list is not None and len(temp_list) > 0:
                the_other_list += temp_list
        # list set for deduplication, crude method but best i have for the moment
        return sorted(set(the_other_list))  # unlike the field equivalent this might return an empty list

    @staticmethod
    def _get_node_graphs_recursion(sub_dict):
        part_list = []
        if Spcht.is_dictkey(sub_dict, 'graph'):
            part_list.append(sub_dict['graph'])
        if Spcht.is_dictkey(sub_dict, 'graph_map'):
            for key, value in sub_dict['graph_map'].items():
                part_list.append(value)   #probably some duplicates here
        if Spcht.is_dictkey(sub_dict, 'fallback'):
            temp_list = Spcht._get_node_fields_recursion(sub_dict['fallback'])
            if temp_list is not None and len(temp_list) > 0:
                part_list += temp_list
        return part_list

    @staticmethod
    def quickSparql(quadro_list: list, graph: str) -> str:
        """
            Does some basic string manipulation to create one solid block of entries for the inserts via sparql
            :param list quadro_list: a list of tuples as outputted by Spcht.processData()
            :param str graph: the mapped graph the triples are inserted into, part of the sparql query
            :return: a long, multilined string
            :rtype: str
        """
        if isinstance(quadro_list, list):
            sparkle = f"INSERT IN GRAPH <{graph}> {{\n"
            for each in quadro_list:
                sparkle += Spcht.quickSparqlEntry(each)
            sparkle += "}"
            return sparkle
        else:
            return f"INSERT IN GRAPH <{graph}> {{ " + Spcht.quickSparqlEntry(quadro_list) + "}"

    @staticmethod
    def quickSparqlEntry(quadro):
        """
            Converts the tuple format of the data processing into a sparql query string
            :param tuple quadro: a tuple with 4 entries containing the graph plus identifier
            :rtype: str
            :return: a sparql query of the structure <s> <p> <o> .
        """
        if quadro[3] == 1:
            return f"<{quadro[0]}> <{quadro[1]}> <{quadro[2]}> . \n"
        else:
            return f"<{quadro[0]}> <{quadro[1]}> \"{quadro[2]}\" . \n"

    @staticmethod
    def process2RDF(quadro_list: list, format_type="turtle") -> str:
        """
            Leverages RDFlib to format a given list of tuples into an RDF Format

            :param list quadro_list: List of tuples with 4 entries as provided by `processData`
            :param str format_type: one of the offered formats by rdf lib
            :return: a string containing the entire list formated as rdf, turtle format per default
            :rtype: str
        """
        if NORDF:  # i am quite sure that this is not the way to do such  things
            raise ImportError("No RDF Library avaible, cannot process Spcht.process2RDF")
        graph = rdflib.Graph()
        for each in quadro_list:
            if each[3] == 0:
                graph.add((rdflib.URIRef(each[0]), rdflib.URIRef(each[1]), rdflib.Literal(each[2])))
            else:
                graph.add((rdflib.URIRef(each[0]), rdflib.URIRef(each[1]), rdflib.URIRef(each[2])))
        return graph.serialize(format=format_type).decode("utf-8")

    @staticmethod
    def check_format(descriptor, out=sys.stderr, base_path="", i18n=None):
        """
            This function checks if the correct SPCHT format is provided and if not gives appropriated errors.
            This works without an instatiated copy and has therefore a separated output parameter. Further it is
            possible to provide to custom translations for the error messages in cases you wish to offer a check
            engine working in another non-english language. The keys for that dictionaries can be found in the source
            code of this procedure

            :param dict descriptor: a dictionary of the loaded json file of a descriptor file without references
            :param file out: output pipe for the error messages
            :param base_path: path of the spcht descriptor file, used to check reference files not in script directory
            :param dict i18n: a flat dictionary containing the error texts. Not set keys will default to the standard ones
            :return: True if everything is in order, False and a message about the located failure in the output
            :rtype: bool
        """
        # originally this wasn't a static method, but we want to use it to check ANY descriptor format, not just this
        # for this reasons this has its own out target instead of using that of the instance
        # * what it does not check for is illogical entries like having alternatives for a pure marc source
        # for language stuff i give you now the ability to actually provide local languages
        # 01.02.2021 i toyed with the thought of replacing all the 'return false' with Exceptions but i decided that had
        # no use as i only ever return  true or false and nothing else
        error_desc = {
            "header_miss": "The main header informations [id_source, id_field, main] are missing, is this even the right file?",
            "header_mal": "The header information seems to be malformed",
            "basic_struct": "Elements of the basic structure ( [source, field, required, graph] ) are missing",
            "basic_struct2": "An Element of the basic sub node structure is missing [source or field]",
            "ref_not_exist": "The file {} cannot be found (probably either rights or wrong path)",
            "type_str": "the type key must contain a string value that is either 'triple' or anything else",
            "regex": "The provided regex is not correct",
            "field_str": "The field entry has to be a string",
            "required_str": "The required entry has to be a string and contain either: 'mandatory' or 'optional",
            "required_chk": "Required-String can only 'mandatory' or 'optional'. Maybe encoding error?",
            "alt_list": "Alternatives must be a list of strings, eg: ['item1', 'item2']",
            "alt_list_str": "Every entry in the alternatives list has to be a string",
            "map_dict": "Translation mapping must be a dictionary",
            "map_dict_str": "Every element of the mapping must be a string",
            "maps_dict": "Settings for Mapping must be a dictionary",
            "maps_dict_str": "Every element of the mapping settings must be a string",
            "must_str": "The value of the {} key must be a string",
            "fallback": "-> structure of the fallback node contains errors",
            "nodes": "-> error in structure of Node",
            "fallback_dict": "Fallback structure must be an dictionary build like a regular node",
            "graph_map": "When defining graph_field there must also be a graph_map key defining the mapping.",
            "graph_map_dict": "The graph mapping must be a dictionary of strings",
            "graph_map_dict_str": "Each key must reference a string value in the graph_map key",
            "graph_map_ref": "The key graph_map_ref must be a string pointing to a local file",
            "add_fields_list": "The additional fields for the insert string have to be in a list, even if its only one ['str']",
            "add_field_list_str": "Every element of the add_fields has to be a string",
            "add_field_list_marc_str1": "Every single string in the insert_fields list has to be of the format '604:a'",
            "add_field_list_marc_str2": "Every entry has to be a double point seperated combination of field and subfield",
            "if_allowed_expressions": "The conditions for the if field can only be {}",
            "if_need_value": "The Condition needs the key 'if_value' except for the 'exi' condition",
            "if_need_field": "The Condition needs the key 'if_field' that references the data field for checking",
            "if_value_types": "The Condition value can only be of type string, integer or float"
        }
        if isinstance(i18n, dict):
            for key, value in error_desc.items():
                if Spcht.is_dictkey(i18n, key) and isinstance(i18n[key], str):
                    error_desc[key] = i18n[key]
        # ? this should probably be in every reporting function which bears the question if its not possible in another way
        if base_path == "":
            base_path = os.path.abspath('.')
        # checks basic infos
        if not Spcht.is_dictkey(descriptor, 'id_source', 'id_field', 'nodes'):
            print(error_desc['header_miss'], file=out)
            return False
        # transforms header in a special node to avoid boiler plate code
        header_node = {
            "source": descriptor.get('id_source'),
            "field": descriptor.get('id_field'),
            "subfield": descriptor.get('id_subfield', None),
            "fallback": descriptor.get('id_fallback', None)
            # this main node doesnt contain alternatives or the required field
        }  # ? there must be a better way for this mustn't it?
        # a lot of things just to make sure the header node is correct, its almost like there is a better way
        plop = []
        for key, value in header_node.items():  # this removes the none existent entries cause i dont want to add more checks
            if value is None:
                plop.append(key)  # what you cant do with dictionaries you iterate through is removing keys while doing so
        for key in plop:
            header_node.pop(key, None)
        del plop

        # the actual header check
        if not Spcht._check_format_node(header_node, error_desc, out, base_path):
            print("header_mal", file=out)
            return False
        # end of header checks
        for node in descriptor['nodes']:
            if not Spcht._check_format_node(node, error_desc, out, base_path, True):
                print(error_desc['nodes'], node.get('name', node.get('field', "unknown")), file=out)
                return False
        # ! make sure everything that has to be here is here
        return True

    @staticmethod
    def _check_format_node(node, error_desc, out, base_path, is_root=False):
        # @param node - a dictionary with a single node in it
        # @param error_desc - the entire flat dictionary of error texts
        # * i am writing print & return a lot here, i really considered making a function so i can do "return funct()"
        # * but what is the point? Another sub function to save one line of text each time and obfuscate the code more?
        # ? i am wondering if i shouldn't rather rise a ValueError instead of returning False
        if not is_root and not Spcht.is_dictkey(node, 'source', 'field'):
            print(error_desc['basic_struct2'], file=out)
            return False

        # root node specific things
        if is_root:
            if not Spcht.is_dictkey(node, 'source', 'field', 'required', 'graph'):
                print(error_desc['basic_struct'], file=out)
                return False
            if not isinstance(node['required'], str):
                print(error_desc['required_str'], file=out)
                return False
            if node['required'] != "optional" and node['required'] != "mandatory":
                print(error_desc['required_chk'], file=out)
                return False
            if Spcht.is_dictkey(node, 'type') and not isinstance(node['type'], str):
                print(error_desc['type_str'], file=out)
                return False

        if not isinstance(node['field'], str):  # ? is a one character string a chr?
            print(error_desc['field_str'], file=out)
            return False
        # checks for correct data types, its pretty much 4 time the same code but there might be a case
        # where i want to change the datatype so i let it be split for later handling

        must_strings = ["match", "cut", "prepend", "append", "if_match", "if_cut", "if_prepend", "if_append"]
        must_regex = ['match', 'cut', 'if_match', 'if_cut']
        for key in must_strings:
            if Spcht.is_dictkey(node, key) and not isinstance(node[key], str):
                print(error_desc['must_str'].format(key), file=out)
                return False
        for key in must_regex:
            if Spcht.is_dictkey(node, key):
                if not Spcht.validate_regex(node.get(key, r"")):
                    print(error_desc['regex'], file=out)
                    return False

        if Spcht.is_dictkey(node, 'if_condition'):
            if not isinstance(node['if_condition'], str):
                print(error_desc['must_str'].format('if_condition'), file=out)
                return False
            else:
                if not Spcht.is_dictkey(SPCHT_BOOL_OPS, node['if_condition']):
                    print(error_desc['if_allowed_expressions'].format(*SPCHT_BOOL_OPS.keys()), file=out)
                    return False
            if not Spcht.is_dictkey(node, 'if_field'):
                print(error_desc['if_need_field'], file=out)
                return False
            else:
                if not isinstance(node['if_field'], str):
                    print(error_desc['must_str'].format('if_field'), file=out)
                    return False
            if not Spcht.is_dictkey(node, 'if_value') and node['if_condition'] != "exi":  # exi doesnt need a value
                print(error_desc['if_need_value'], file=out)
                return False
            if Spcht.is_dictkey(node, 'if_value'):
                if not isinstance(node['if_value'], str) \
                        and not isinstance(node['if_value'], int) \
                        and not isinstance(node['if_value'], float):
                    print(error_desc['if_value_types'], file=out)
                    return False

        if node['source'] == "marc":

            if Spcht.is_dictkey(node, 'insert_into'):
                if not isinstance(node['insert_into'], str):
                    print(error_desc['must_str'].format('insert_into'), file=out)
                    return False
                if Spcht.is_dictkey(node, 'insert_add_fields') and not isinstance(node['insert_add_fields'], list):
                    print(error_desc['add_field_list'], file=out)  # add field is optional, it might not exist but when..
                    return False
                if Spcht.is_dictkey(node, 'insert_add_fields'):
                    for each in node['insert_add_fields']:
                        if not isinstance(each, str):
                            print(error_desc['add_field_list_str'], file=out)
                            return False
                        else:  # for marc we also need the shorthand validating
                            one, two = Spcht.slice_marc_shorthand(each)
                            if one is None:
                                print(error_desc['add_field_list_marc_str2'])
                                return False

        if node['source'] == "dict":
            if Spcht.is_dictkey(node, 'alternatives'):
                if not isinstance(node['alternatives'], list):
                    print(error_desc['alt_list'], file=out)
                    return False
                else:  # this else is redundant, its here for you dear reader
                    for item in node['alternatives']:
                        if not isinstance(item, str):
                            print(error_desc['alt_list_str'], file=out)
                            return False
            if Spcht.is_dictkey(node, 'mapping'):
                if not isinstance(node['mapping'], dict):
                    print(error_desc['map_dict'], file=out)
                    return False
                else:  # ? again the thing with the else for comprehension, this comment is superfluous
                    for key, value in node['mapping'].items():
                        if not isinstance(value, str):
                            print(error_desc['map_dict_str'], file=out)
                            return False
            if Spcht.is_dictkey(node, 'insert_into'):
                if not isinstance(node['insert_into'], str):
                    print(error_desc['must_str'].format('insert_into'), file=out)
                    return False
                if Spcht.is_dictkey(node, 'insert_add_fields') and not isinstance(node['insert_add_fields'], list):
                    print(error_desc['add_field_list'], file=out)  # add field is optional, it might not exist but when..
                    return False
                if Spcht.is_dictkey(node, 'insert_add_fields'):
                    for each in node['insert_add_fields']:
                        if not isinstance(each, str):
                            print(error_desc['add_field_list_str'], file=out)
                            return False

            if Spcht.is_dictkey(node, 'mapping_settings'):
                if not isinstance(node['mapping_settings'], dict):
                    print(error_desc['maps_dict'], file=out)
                    return False
                else:  # ? boilerplate, boilerplate does whatever boilerplate does
                    for key, value in node['mapping_settings'].items():
                        if not isinstance(value, str):
                            # special cases upon special cases, here its the possibility of true or false for $default
                            if isinstance(value, bool) and key == "$default":
                                continue
                            else:
                                print(error_desc['maps_dict_str'], file=out)
                                return False
                        if key == "$ref":
                            file_path = value
                            fullpath = os.path.normpath(os.path.join(base_path, file_path))
                            if not os.path.exists(fullpath):
                                print(error_desc['ref_not_exist'].format(fullpath), file=out)
                                return False
            if Spcht.is_dictkey(node, 'graph_field'):
                if not isinstance(node['graph_field'], str):
                    print(error_desc['must_str'].format("graph_field"), file=out)
                    return False
                if not Spcht.is_dictkey(node, 'graph_map') and not Spcht.is_dictkey(node, 'graph_map_ref'):
                    print(error_desc['graph_map'], file=out)
                    return False
                if Spcht.is_dictkey(node, 'graph_map'):
                    if not isinstance(node['graph_map'], dict):
                        print(error_desc['graph_map_dict'], file=out)
                        return False
                    else:
                        for value in node['graph_map'].values():
                            if not isinstance(value, str):
                                print(error_desc['graph_map_dict_str'], file=out)
                                return False
                if Spcht.is_dictkey(node, 'graph_map_ref') and not isinstance(node['graph_map_ref'], str):
                    print(error_desc['graph_map_ref'], file=out)
                    return False
                if Spcht.is_dictkey(node, 'graph_map_ref') and isinstance(node['graph_map_ref'], str):
                    file_path = node['graph_map_ref']
                    fullpath = os.path.normpath(os.path.join(base_path, file_path))
                    if not os.path.exists(fullpath):
                        print(error_desc['ref_not_exist'].format(fullpath), file=out)
                        return False

            if Spcht.is_dictkey(node, 'saveas'):
                if not isinstance(node['saveas'], str):
                    print(error_desc['must_str'].format("saveas"), file=out)
                    return False

        if Spcht.is_dictkey(node, 'fallback'):
            if isinstance(node['fallback'], dict):
                if not Spcht._check_format_node(node['fallback'], error_desc, out, base_path):  # ! this is recursion
                    print(error_desc['fallback'], file=out)
                    return False
            else:
                print(error_desc['fallback_dict'], file=out)
                return False
        return True


class SpchtIterator:
    def __init__(self, spcht: Spcht):
        self._spcht = spcht
        self._index = 0

    def __next__(self):
        if isinstance(self._spcht._DESCRI, dict) and \
                Spcht.is_dictkey(self._spcht._DESCRI, 'nodes') and \
                self._index < (len(self._spcht._DESCRI['nodes'])):
            result = self._spcht._DESCRI['nodes'][self._index]
            self._index += 1
            return result
        raise StopIteration

