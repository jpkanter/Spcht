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
import os
import sys
import re
import pymarc
from pymarc.exceptions import RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid, \
    RecordDirectoryInvalid, NoFieldsFound
# ? if i import this i get circular imports and i really dont want that so got a bit of boilerplate here in the sincere
# ? hope that the amount of boolean operators never changes
# from SpchtDescriptorFormat import SPCHT_BOOL_OPS
SPCHT_BOOL_OPS = {"equal":"==", "eq":"==","greater":">","gr":">","lesser":"<","ls":"<",
                    "greater_equal":">=","gq":">=", "lesser_equal":"<=","lq":"<=",
                  "unequal":"!=","uq":"!=","=":"==","==":"==","<":"<",">":">","<=":"<=",">=":">=","!=":"!=","exi":"exi"}

import logging
logger = logging.getLogger(__name__)

try:
    NORDF = False
    import rdflib
    from rdflib.namespace import DC, DCTERMS, DOAP, FOAF, SKOS, OWL, RDF, RDFS, VOID, XMLNS, XSD
except ImportError:
    NORDF = True
    logger.info("No RDF Library avaible, some functions will not work")


def is_dictkey(dictionary: dict, *keys: str or int or list):
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
            return True  # all keys are inside the dictionary
        if key not in dictionary:
            return False
    return True


def list_has_elements(iterable):
    # also know as "is object iterable", i dont think this is ever needed
    # technically this can check more than lists, but i use it to check some crude object on having objects or not
    for item in iterable:
        return True
    return False


def list_wrapper(some_element: any) -> list:
    """
    I had the use case that i needed always a list of elements on a type i dont really care about as even when
    its just a list of one element.
    :param some_element: any object that will be wrapped in a list
    :type some_element: any
    :return: Will return the element wrapped in the list unless its already a list, if its something weird it gets wrapped in a list of one
    :rtype: list
    """
    if isinstance(some_element, list):
        return some_element
    else:
        return [some_element]


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


def match_positions(regex_pattern, zeichenkette: str) -> list or None:
    """
    Returns a list of position tuples for the start and end of the matched pattern in a string
    :param str regex_pattern: the regex pattern that matches
    :param str zeichenkette: the string you want to match against
    :return: either a list of tuples or None if no match was found, tuples are start and end of the position
    :rtype: list
    """
    # ? this is one of these things where there is surely a solution already but i couldn't find it in 5 minutes
    pattern = re.compile(regex_pattern)
    poslist = []
    for hit in pattern.finditer(zeichenkette):
        poslist.append((hit.start(), hit.end()))
    return poslist  # empty list is falsy so its good?


def insert_list_into_str(the_string_list: list, string_to_insert: str, regex_pattern=r'\{\}', pattern_len=2, strict=True):
    """
    Inserts a list of list of strings into another string that contains placeholder of the specified kind in regex_pattern
    :param list the_string_list: a list containing another list of strings, one element for each position
    :param str string_to_insert: the string you want to match against
    :param str regex_pattern: the regex pattern searching for the replacement
    :param int pattern_len: the lenght of the matching placeholder pattern, i am open for less clunky input on this
    :param bool strict: if true empty strings will mean nothing gets returned, if false empty strings will replace
    :return: a string with the inserted strings
    :rtype: str
    """
    # ! for future reference: "random {} {} {}".format(*list) will do almost what this does
    # ? and the next problem that has a solution somewhere but i couldn't find the words to find it
    if not isinstance(the_string_list, list):
        raise TypeError("list of strings must be an actual 'list'")
    positions = match_positions(regex_pattern, string_to_insert)
    if len(the_string_list) > len(positions):  # more inserts than slots
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
        if len(string_to_insert) > end:
            string_to_insert = string_to_insert[0:start] + each + string_to_insert[end:len(string_to_insert)]
        else:
            string_to_insert = string_to_insert[0:start] + each
        str_len_correction += len(each)-pattern_len
    return string_to_insert


def fill_var(current_var: list or str or int or float or dict, new_var: any) -> list or any:
    """
    This is another of those functions that probably already exist or what i am trying to do is not wise. Anway
    it either directly returns new_var if current_var is either an empty string or None. If not it creates a new
    list with current_var as first element and new_var as second OR if current_var is already a list it just
    appends, why i am doing that? Cause its boilerplate code and i otherwise had to write it 5 times in one function
    :param list or str or int or float or dict current_var: a variable that might be empty or is not
    :param any new_var: the new value that is to be added to current_var
    :return: most likely a list or just new_var
    :rtype: list or any
    """
    if current_var is None:
        return new_var
    if isinstance(current_var, str) and current_var == "":  # a single space would be enough to not do things
        return new_var
    if isinstance(current_var, list):
        current_var.append(new_var)
        return current_var
    return [current_var, new_var]


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


def if_possible_make_this_numerical(value: str or list):
    """Converts a given var in the best kind of numerical value that it can, if it can be an int it will be one,
    :param str or list value: any kind of value, hopefully something 1-dimensional, lists are okay too
    :return: the converted value, might be an int, might be a float, or just the object that came
    :rtype: int or float or any
    """
    if isinstance(value, list):
        possible_numerical_list = []
        for every in value:
            if is_int(every):
                possible_numerical_list.append(int(every))
            elif is_float(every):
                possible_numerical_list.append(float(every))
            else:
                possible_numerical_list.append(every)
        return possible_numerical_list
    else:
        if is_int(value):
            return int(value)
        elif is_float(value):
            return float(value)
        else:
            return value


def slice_marc_shorthand(string: str) -> tuple:
    """
    Splits a string and gives a tuple of two elements containing the Main Number and the subfield of a marc shorthand
    Calls a regex check to make sure the format is corret
    :param str string: a string describing a marc shorthand, should look like this '504:a', second part can also be a number or 'i1', 'i2' and 'none'
    :return: either (None, False) or (field, subfield)
    :rtype: tuple
    """
    match = re.match(r"^[0-9]{1,3}:\w*$", string)
    if match:
        a_list = string.split(":")
        return int(str(a_list[0]).lstrip("0")), a_list[1]
    else:
        return None, False  # this is a tuple right ?


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


def marc21_fixRecord(record: str, validation=False, record_id=0, replace_method='decimal'):
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
        # ? we only really care if this throws an error, this is why nothing happens
        try:
            reader = pymarc.MARCReader(marcFullRecordFixed.encode('utf8'), utf8_handling='replace')
            # * marcrecord = next(reader)  # in case we care about the actualy record
            next(reader)  # ? iterator for the next marc entry, we only ever handle one so this isn't used
        except (
                RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid,
                RecordDirectoryInvalid,
                NoFieldsFound, UnicodeDecodeError) as e:
            # TODO: write individual handlers for the different errors
            print(f"record id {record_id}: {str(e)}", file=sys.stderr)
            return False
    # TODO: Clean this up
    return marcFullRecordFixed


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
        if f'{i:02d}' in marc_leader_text:
            print(marc_leader_text.get(f'{i:02d}').get('label') + ": " + marc_leader_text.get(f'{i:02d}').get(
                leader[i], "unknown"), file=output)


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


def marc2list(marc_full_record, validation=True, replace_method='decimal', explicit_exception=False):
    """
        This Converts a given, binary marc record as contained in the files i have seen so far into something that is
        actually usable -> a dictionary with proper keys and subkeys

        :param str marc_full_record: string containing the full marc21 record
        :param bool validation: Toogles whether the fixed record will be validated or not
        :param str replace_method: One of the three replacement methods: [decimal, unicode, hex]
        :param bool explicit_exception: If true throws an actual exception while traversing the marc structure, usually this is just one of many entries whichs failure can savely ignored
        :return: Returns a dictionary of ONE Marc Record if there is only one or a list of dictionaries, each a marc21 entry
        :rtype: dict or list
        :raises ValueError: In Case the normalize_marcdict function fails, probably due a failure before
        :raises TypeError: If the given marc data is not a string but something else
    """
    clean_marc = marc21_fixRecord(marc_full_record, validation=validation, replace_method=replace_method)
    if isinstance(clean_marc, str):  # would be boolean if something bad had happen
        reader = pymarc.MARCReader(clean_marc.encode('utf-8'))
        marc_list = []
        for record in reader:
            try:
                record_dict = normalize_marcdict(record.as_dict())  # for some reason i cannot access all fields,
                # also funny, i could probably use this to traverse the entire thing ,but better save than sorry i guess
                # sticking to the standard in case pymarc changes in a way or another
            except ValueError as err:
                raise err  # usually when there is some none-dictionary given
            marcdict = {}
            for i in range(1000):
                if record[f'{i:03d}'] is not None:
                    for single_type in record.get_fields(f'{i:03d}'):
                        temp_subdict = {}
                        for subfield in single_type:
                            if subfield[0] in temp_subdict:
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

                        if i in marcdict:  # already exists, transforms into list
                            if not isinstance(marcdict[i], list):
                                marcdict[i] = [marcdict[i]]
                            marcdict[i].append(temp_subdict)

                        else:
                            marcdict[i] = temp_subdict
                        try:
                            if not list_has_elements(single_type):
                                temp = record_dict.get(f'{i:03d}', None)
                                if temp is not None:
                                    marcdict[i] = {'none': temp}
                        except TypeError as e:
                            if explicit_exception:
                                raise TypeError(f"Spcht.Marc2List: '{i:03d}', {record_dict.get(f'{i:03d}', None)}")
                            logger.warning(f"TypeError in Spcht.Marc2List {i:03d}, {record_dict.get(f'{i:03d}', None)} - {e}")
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


def quickSparql(quadro_list: tuple, graph: str) -> str:
    """
        Does some basic string manipulation to create one solid block of entries for the inserts via sparql
        :param tuple quadro_list: a list of tuples as outputted by Spcht.processData()
        :param str graph: the mapped graph the triples are inserted into, part of the sparql query
        :return: a long, multilined string
        :rtype: str
    """
    if isinstance(quadro_list, list):
        sparkle = f"INSERT IN GRAPH <{graph}> {{\n"
        for each in quadro_list:
            sparkle += quickSparqlEntry(each)
        sparkle += "}"
        return sparkle
    else:
        return f"INSERT IN GRAPH <{graph}> {{ {quickSparqlEntry(quadro_list)} }}"


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


def process2RDF(quadro_list: list, export_format_type="turtle", export=True) -> str or rdflib.Graph:
    """
        Leverages RDFlib to format a given list of tuples into an RDF Format
        See https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.plugins.serializers.html for further information about the used
        library and serializer

        :param list quadro_list: List of tuples with 4 entries as provided by `processData`
        :param str export_format_type: one of the offered formats by rdf lib (n3, nquads, nt, pretty-xml, trig, trix, turtle, xml)
        :param bool export: If True exports as serialized str format, if False exports a 'pure' rdflib.Graph
        :return: a string containing the entire list formated as rdf, turtle format per default
        :rtype: str or rdflib.Graph
    """
    if NORDF:  # i am quite sure that this is not the way to do such  things
        raise ImportError("No RDF Library avaible, cannot process Spcht.process2RDF")
    graph = rdflib.Graph()
    for each in quadro_list:
        try:  # ! using an internal rdflib function is clearly dirty af
            if rdflib.term._is_valid_uri(each[0]) and rdflib.term._is_valid_uri(each[1]):
                if each[3] == 0:
                    graph.add((rdflib.URIRef(each[0]), rdflib.URIRef(each[1]), rdflib.Literal(each[2])))
                elif each[3] == 1 and rdflib.term._is_valid_uri(each[2]):
                    graph.add((rdflib.URIRef(each[0]), rdflib.URIRef(each[1]), rdflib.URIRef(each[2])))
                else:
                    logger.error(
                        f"URL Parsing for <{each[0]}> <{each[1]}> & ({each[2]}) failed due an URI check error")
        except Exception as error:
            print(f"RDF Exception occured with {each[1]} - {error}", file=sys.stderr)
    try:
        if export:
            return graph.serialize(format=export_format_type).decode("utf-8")
        else:
            return graph
    except Exception as e:
        print(f"serialisation couldnt be completed - {e}", file=sys.stderr)
        return f"serialisation couldnt be completed - {e}"


def check_format(descriptor, out=sys.stderr, base_path="", i18n=None):
    """
        This function checks if the correct SPCHT format is provided and if not gives appropriated errors.
        This works without an instatiated copy and has therefore a separated output parameter. Further it is
        possible to provide to custom translations for the error messages in cases you wish to offer a check
        engine working in another non-english language. The keys for that dictionaries can be found in the source
        code of this procedure

        :param dict descriptor: a dictionary of the loaded json file of a descriptor file without references
        :param file out: output pipe for the error messages
        :param path or str base_path: path of the spcht descriptor file, used to check reference files not in script directory
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
        "basic_struct": "Elements of the basic structure ( [source, field, required, predicate] ) are missing",
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
        "joined_map": "When defining joined_field there must also be a joined_map key defining the mapping.",
        "joined_map_dict": "The joined mapping must be a dictionary of strings",
        "joined_map_dict_str": "Each key must reference a string value in the joined_map key",
        "joined_map_ref": "The key joined_map_ref must be a string pointing to a local file",
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
            if key in i18n and isinstance(i18n[key], str):
                error_desc[key] = i18n[key]
    # ? this should probably be in every reporting function which bears the question if its not possible in another way
    if base_path == "":
        base_path = os.path.abspath('.')
    # checks basic infos
    try:
        if not is_dictkey(descriptor, 'id_source', 'id_field', 'nodes'):
            print(error_desc['header_miss'], file=out)
            return False
    except TypeError as e:
        print(f"{error_desc['header_mal']} - {e}: {type(descriptor)}...", file=out)
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
            plop.append(
                key)  # what you cant do with dictionaries you iterate through is removing keys while doing so
    for key in plop:
        header_node.pop(key, None)
    del plop

    # the actual header check
    if not check_format_node(header_node, error_desc, out, base_path):
        print("header_mal", file=out)
        return False
    # end of header checks
    for node in descriptor['nodes']:
        if not check_format_node(node, error_desc, out, base_path, True):
            print(error_desc['nodes'], node.get('name', node.get('field', "unknown")), file=out)
            return False
    # ! make sure everything that has to be here is here
    return True


def check_format_node(node, error_desc, out, base_path, is_root=False):
    # @param node - a dictionary with a single node in it
    # @param error_desc - the entire flat dictionary of error texts
    # * i am writing print & return a lot here, i really considered making a function so i can do "return funct()"
    # * but what is the point? Another sub function to save one line of text each time and obfuscate the code more?
    # ? i am wondering if i shouldn't rather rise a ValueError instead of returning False
    if not is_root and not is_dictkey(node, 'source', 'field'):
        print(error_desc['basic_struct2'], file=out)
        return False

    # root node specific things
    if is_root:
        if not is_dictkey(node, 'source', 'field', 'required', 'predicate'):
            print(error_desc['basic_struct'], file=out)
            return False
        if not isinstance(node['required'], str):
            print(error_desc['required_str'], file=out)
            return False
        if node['required'] != "optional" and node['required'] != "mandatory":
            print(error_desc['required_chk'], file=out)
            return False
        if is_dictkey(node, 'type') and not isinstance(node['type'], str):
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
        if key in node and not isinstance(node[key], str):
            print(error_desc['must_str'].format(key), file=out)
            return False
    for key in must_regex:
        if key in node:
            if not validate_regex(node.get(key, r"")):
                print(error_desc['regex'], file=out)
                return False

    if 'if_condition' in node:
        if not isinstance(node['if_condition'], str):
            print(error_desc['must_str'].format('if_condition'), file=out)
            return False
        else:
            if not is_dictkey(SPCHT_BOOL_OPS, node['if_condition']):
                print(error_desc['if_allowed_expressions'].format(*SPCHT_BOOL_OPS.keys()), file=out)
                return False
        if 'if_field' not in node:
            print(error_desc['if_need_field'], file=out)
            return False
        else:
            if not isinstance(node['if_field'], str):
                print(error_desc['must_str'].format('if_field'), file=out)
                return False
        if 'if_value' not in node and node['if_condition'] != "exi":  # exi doesnt need a value
            print(error_desc['if_need_value'], file=out)
            return False
        if 'if_value' in node:
            if not isinstance(node['if_value'], (str, int, float, list)):
                print(error_desc['if_value_types'], file=out)
                return False
            if isinstance(node['if_value'], list):
                for each in node['if_value']:
                    if not isinstance(each, str, int, float):
                        print(error_desc['if_value_types'], file=out)
                        return False

    if node['source'] == "marc":
        if 'insert_into' in node:
            if not isinstance(node['insert_into'], str):
                print(error_desc['must_str'].format('insert_into'), file=out)
                return False
            if 'insert_add_fields' in node and not isinstance(node['insert_add_fields'], list):
                print(error_desc['add_field_list'],
                      file=out)  # add field is optional, it might not exist but when..
                return False
            if 'insert_add_fields' in node:
                for each in node['insert_add_fields']:
                    if not isinstance(each, str):
                        print(error_desc['add_field_list_str'], file=out)
                        return False
                    else:  # for marc we also need the shorthand validating
                        one, two = slice_marc_shorthand(each)
                        if one is None:
                            print(error_desc['add_field_list_marc_str2'])
                            return False

    if node['source'] == "dict":
        if 'alternatives' in node:
            if not isinstance(node['alternatives'], list):
                print(error_desc['alt_list'], file=out)
                return False
            else:  # this else is redundant, its here for you dear reader
                for item in node['alternatives']:
                    if not isinstance(item, str):
                        print(error_desc['alt_list_str'], file=out)
                        return False
        if 'mapping' in node:
            if not isinstance(node['mapping'], dict):
                print(error_desc['map_dict'], file=out)
                return False
            else:  # ? again the thing with the else for comprehension, this comment is superfluous
                for key, value in node['mapping'].items():
                    if not isinstance(value, str):
                        print(error_desc['map_dict_str'], file=out)
                        return False
        if 'insert_into' in node:
            if not isinstance(node['insert_into'], str):
                print(error_desc['must_str'].format('insert_into'), file=out)
                return False
            if 'insert_add_fields' in node and not isinstance(node['insert_add_fields'], list):
                print(error_desc['add_field_list'],
                      file=out)  # add field is optional, it might not exist but when..
                return False
            if 'insert_add_fields' in node:
                for each in node['insert_add_fields']:
                    if not isinstance(each, str):
                        print(error_desc['add_field_list_str'], file=out)
                        return False

        if 'mapping_settings' in node:
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
        if 'joined_field' in node:
            if not isinstance(node['joined_field'], str):
                print(error_desc['must_str'].format("joined_field"), file=out)
                return False
            if 'joined_map' not in node and 'joined_map_ref' not in node:
                print(error_desc['joined_map'], file=out)
                return False
            if 'joined_map' in node:
                if not isinstance(node['joined_map'], dict):
                    print(error_desc['joined_map_dict'], file=out)
                    return False
                else:
                    for value in node['joined_map'].values():
                        if not isinstance(value, str):
                            print(error_desc['joined_map_dict_str'], file=out)
                            return False
            if 'joined_map_ref' in node and not isinstance(node['joined_map_ref'], str):
                print(error_desc['joined_map_ref'], file=out)
                return False
            if 'joined_map_ref' in node and isinstance(node['joined_map_ref'], str):
                file_path = node['joined_map_ref']
                fullpath = os.path.normpath(os.path.join(base_path, file_path))
                if not os.path.exists(fullpath):
                    print(error_desc['ref_not_exist'].format(fullpath), file=out)
                    return False

        if 'saveas' in node:
            if not isinstance(node['saveas'], str):
                print(error_desc['must_str'].format("saveas"), file=out)
                return False

    if 'fallback' in node:
        if isinstance(node['fallback'], dict):
            if not check_format_node(node['fallback'], error_desc, out, base_path):  # ! this is recursion
                print(error_desc['fallback'], file=out)
                return False
        else:
            print(error_desc['fallback_dict'], file=out)
            return False
    return True