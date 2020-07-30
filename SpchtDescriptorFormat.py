import json
import re
import sys
import pymarc
from pymarc.exceptions import RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid, \
    RecordDirectoryInvalid, NoFieldsFound
from termcolor import colored # only needed for debug print


# the actual class

class Spcht:
    _DESCRI = None  # the finally loaded descriptor file with all references solved
    _SAVEAS = {}
    # * i do all this to make it more customizable, maybe it will never be needed, but i like having options
    std_out = sys.stdout
    std_err = sys.stderr
    debug_out = sys.stdout
    _debug = False

    def __init__(self, filename=None, check_format=False, debug=False):
        if filename is not None:
            self.load_descriptor_file(filename)
        self.debugmode(debug)
        # does absolutely nothing in itself

    def __repr__(self):
        if len(self._DESCRI) > 0:
            some_text = ""
            for item in self._DESCRI['nodes']:
                some_text+= "{}[{},{}] - ".format(item['field'], item['source'], item['required'])
            return some_text[:-3]
        else:
            return "Empty Spcht"

    def debug_print(self, *args, **kwargs):
        # prints only text if debug flag is set, i wonder if it would have been easier to just set the out put for
        # normal prints to None and be done with it. Is this better or worse? Probably no sense questioning this
        if Spcht.is_dictkey(kwargs, "file"):
            del kwargs['file']  # while handing through all the kwargs we have to make one exception, this seems to work
        if self._debug is True:
            print(*args, file=self.debug_out, **kwargs)

    def debugmode(self, status):
        # a setter, i really dont like those
        if not isinstance(status, bool) or status is False:
            self._debug = False
        else:
            self._debug = True

    def export_full_descriptor(self, filename, indent=3):
        # exports the loaded descriptor datas structure, basically a compiled version
        # i really dont know why i wrote this
        try:
            with open(filename, "w") as outfile:
                json.dump(self._DESCRI, outfile, indent=indent)
        except Exception as e:
            print("File Error", e, file=self.std_err)

    def load_json(self, filename):
        try:
            with open(filename, mode='r') as file:
                return json.load(file)
        except FileNotFoundError:
            print("nofile", file=self.std_err)
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
        if self._DESCRI is not None:
            return True
        else:
            return False

    def getSaveAs(self, key=None):
        if key is None:
            return self._SAVEAS
        if Spcht.is_dictkey(self._SAVEAS, key):
            return self._SAVEAS[key]
        else:
            return None

    def cleanSaveaAs(self):
        # i originally had this in the "getSaveAs" function, but maybe you have for some reasons the need to do this
        # manually or not at all. i dont know how expensive set to list is. We will find out
        for key in self._SAVEAS:
            self._SAVEAS[key] = list(set(self._SAVEAS[key]))

    # other boiler plate, general stuff that is used to not write out a lot of code each time
    @staticmethod
    def is_dictkey(dictionary, *keys):
        try:
            for key in keys:
                if not key in dictionary:
                    return False
            return True
        except TypeError:
            print("Non Dictionary provided", file=sys.stderr)

    @staticmethod
    def list_has_elements(iterable):
        # technically this can check more than lists, but i use it to check some crude object on having objects or not
        for item in iterable:
            return True
        return False

    @staticmethod
    def validate_regex(regex_str):
        # another of those super basic function where i am not sure if there isn't an easier way
        try:
            re.compile(regex_str)
            return True
        except re.error:
            return False
        except TypeError: # for the string not beeing one
            return False

    @staticmethod
    def marc21_fixRecord(record="", record_id=0, validation=False, replace_method='decimal'):
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
        # this method is written broader than necessary, reuseable?
        for i in range(0, 3):
            marcFullRecordFixed = marcFullRecordFixed.replace(replace_methods.get(replace_method)[0][i],
                                                              replace_methods.get(replace_method)[1][i])
        if validation:
            try:
                reader = pymarc.MARCReader(marcFullRecordFixed.encode('utf8'), utf8_handling='replace')
                marcrecord = next(reader)  # what does this?
            except (
                    RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid,
                    RecordDirectoryInvalid,
                    NoFieldsFound, UnicodeDecodeError) as e:
                print("record id {0}:".format(record_id) + str(e), file=sys.stderr)
                return False
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
        # to explain it a bit further, this is the direct outout of .as_dict() for an example file
        # {'leader': '02546cam a2200841   4500', 'fields': [{'001': '0-023500557'}, ...
        # the leader is okay, but why are the fields a list of single dictionaries? i really dont get it
        the_long_unnecessary_list = a_so_called_dictionary.get('fields', None)
        an_actual_dictionary = {}
        if the_long_unnecessary_list is not None:
            for mini_dict in the_long_unnecessary_list:
                key = next(iter(mini_dict))  # Python 3.7 feature
                an_actual_dictionary[key] = mini_dict[key]
            return an_actual_dictionary
        return False

    @staticmethod
    def marc2list(marc_full_record, validation=True, replace_method='decimal'):
        clean_marc = Spcht.marc21_fixRecord(marc_full_record, validation=validation, replace_method=replace_method)
        if isinstance(clean_marc, str):  # would be boolean if something bad had happen
            reader = pymarc.MARCReader(clean_marc.encode('utf-8'))
            marc_list = []
            for record in reader:
                tempdict = {}
                record_dict = Spcht.normalize_marcdict(record.as_dict())  # for some reason i cannot access all fields,
                # also funny, i could probably use this to traverse the entire thing ,but better save than sorry i guess
                # sticking to the standard in case pymarc changes in a way or another
                for i in range(1000):
                    if record[f'{i:03d}'] is not None:
                        tempdict[i] = {}
                        for item in record[f'{i:03d}']:
                            # marc items are tuples, for title its basically 'a': 'Word', 'b': 'more Words'
                            tempdict[i][item[0]] = item[1]
                            if Spcht.is_dictkey(tempdict[i], "concat"):
                                tempdict[i]['concat'] += " " + item[1]
                            else:
                                tempdict[i]['concat'] = item[1]
                        if not Spcht.list_has_elements(record[f'{i:03d}']):
                            tempdict[i] = record_dict.get(f'{i:03d}')
                            # normal len doesnt work cause no method, flat element
                marc_list.append(tempdict)
            if 0 < len(marc_list) < 2:
                return marc_list[0]
            elif len(marc_list) > 1:
                return marc_list
            else:
                return None
        else:
            return False
        # i am astonished how diverse the return statement can be, False if something went wrong, None if nothing gets
        # returned but everything else went fine, although, i am not sure if that even triggers and under what circumstances

    def load_descriptor_file(self, filename):
        # returns None if something is amiss, returns the descriptors as dictionary
        # ? turns out i had to add some complexity starting with the "include" mapping
        descriptor = self.load_json(filename)

        if isinstance(descriptor, bool):  # load json goes wrong if something is wrong with the json
            return None
        if not Spcht.check_format(descriptor):
            return None
        # * goes through every mapping node and adds the reference files, which makes me basically rebuild the thing
        # ? python iterations are not with pointers, so this will expose me as programming apprentice but this will work
        new_node = []
        for item in descriptor['nodes']:
            a_node = self._load_ref_node(item)
            if isinstance(a_node, bool):  # if something goes wrong we abort here
                print("spcht_ref", file=self.std_err)
                return False
            new_node.append(a_node)
        descriptor['nodes'] = new_node  # replaces the old node with the new, enriched ones
        self._DESCRI = descriptor
        return True

    def _load_ref_node(self, node_dict):
        # We are again in beautiful world of recursion. Each node can contain a mapping and each mapping can contain
        # a reference to a mapping json. i am actually quite worried that this will lead to performance issues
        # TODO: Research limits for dictionaries and performance bottlenecks
        # so, this returns False and the actual loading operation returns None, this is cause i think, at this moment,
        # that i can check for isinstance easier than for None, i might be wrong and i have not looked into the
        # cost of that operation if that is ever a concern
        if Spcht.is_dictkey(node_dict, 'fallback'):
            node_dict['fallback'] = self._load_ref_node(node_dict['fallback'])  # ! there it is again, the cursed recursion thing
            if isinstance(node_dict['fallback'], bool):
                return False
        if Spcht.is_dictkey(node_dict, 'mapping_settings') and node_dict['mapping_settings'].get('$ref') is not None:
            file_path = node_dict['mapping_settings']['$ref']  # ? does it always has to be a relative path?

            map_dict = self.load_json(file_path)
            # iterate through the dict, if manual entries have the same key ignore
            if not isinstance(map_dict, dict):  # we expect a simple, flat dictionary, nothing else
                return False  # funnily enough, this also includes bool which happens when json loads fails
            # ! this here is the actual logic that does the thing:
            # there might no mapping key at all
            if not Spcht.is_dictkey(node_dict, 'mapping'):
                node_dict['mapping'] = {}
            for key, value in map_dict.items():
                if not isinstance(value, str):  # only flat dictionaries, no nodes
                    print("spcht_map", file=self.std_out)
                    return False
                if not Spcht.is_dictkey(node_dict['mapping'], key):  # existing keys have priority
                    node_dict['mapping'][key] = value
            del map_dict
            # clean up mapping_settings node
            del (node_dict['mapping_settings']['$ref'])
            if len(node_dict['mapping_settings']) <= 0:
                del (node_dict['mapping_settings'])  # if there are no other entries the entire mapping settings goes

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
        if sub_dict.get('name', "") == "$Identifier$":
            self.debug_print(colored("ID Source:", "red"), end=" ")
        else:
            self.debug_print(colored(sub_dict.get('name', ""), "blue"), end=" ")
        if sub_dict['source'] == "marc":
            if marc21_dict is None:
                self.debug_print(colored("No Marc", "yellow"), end="|")
                pass
            elif not Spcht.is_dictkey(marc21_dict, sub_dict['field'].lstrip("0")):
                self.debug_print(colored("Marc around but not field", "yellow"), end="|")
                pass
            else:
                self.debug_print(colored("some Marc", "yellow"), end="-> ")
                # Variant 1: a singular subfield is taken
                if Spcht.is_dictkey(sub_dict, 'subfield'):
                    if Spcht.is_dictkey(marc21_dict, sub_dict['field'].lstrip("0")):
                        self.debug_print(" ", colored(marc21_dict[sub_dict['field'].lstrip("0")], "yellow"), " ", end="")
                        if sub_dict['subfield'] == 'none':
                            return marc21_dict[sub_dict['field']]
                        elif Spcht.is_dictkey(marc21_dict[sub_dict['field'].lstrip("0")], sub_dict['subfield']):
                            return marc21_dict[sub_dict['field'].lstrip("0")][sub_dict['subfield']]
                # Variant 2: a list of subfields is concat
                if Spcht.is_dictkey(sub_dict, 'subfields'):
                    # check for EVERY subfield to be around, abort this if not
                    combined_string = ""  # ? this seems less than perfect
                    for marc_key in sub_dict['subfields']:
                        if not Spcht.is_dictkey(marc21_dict['field'], marc_key):
                            combined_string = False
                            break
                        else:
                            combined_string += marc21_dict[sub_dict['field'].lstrip("0")][marc_key] + sub_dict.get('concat', " ")
                    if isinstance(combined_string, str):  # feels wrong, if its boolean something went AWOL
                        # * this just deleted the last concat piece with a string[:1] where 1 can be the length of concat
                        return combined_string[:len(sub_dict.get('concat', " "))]

            # ! this handling of the marc format is probably too simply
            # TODO: gather more samples of awful marc and process it
        elif sub_dict['source'] == "dict":
            self.debug_print(colored("Source Dict", "yellow"), end="-> ")
            if Spcht.is_dictkey(raw_dict, sub_dict['field']):  # main field name
                temp_value = raw_dict[sub_dict['field']]  # the raw value
                temp_value = Spcht._node_preprocessing(temp_value, sub_dict) # filters out entries
                if temp_value is not None and len(temp_value) > 0:
                    temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
                    return self._node_postprocessing(temp_value, sub_dict)
            # ? since i prime the sub_dict what is even the point for checking the existence of the key, its always there
            elif Spcht.is_dictkey(sub_dict, 'alternatives') and sub_dict['alternatives'] is not None:  # traverse list of alternative field names
                self.debug_print(colored("Alternatives", "yellow"), end="-> ")
                for entry in sub_dict['alternatives']:
                    if Spcht.is_dictkey(raw_dict, entry):
                        temp_value = Spcht._node_preprocessing(raw_dict[entry], sub_dict)
                        temp_value = self._node_mapping(temp_value, sub_dict.get('mapping'),
                                                  sub_dict.get('mapping_settings'))
                        return self._node_postprocessing(temp_value, sub_dict)

        if Spcht.is_dictkey(sub_dict, 'fallback') and sub_dict['fallback'] is not None:  # we only get here if everything else failed
            # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
            # * librarian was who wrote the descriptor format
            self.debug_print(colored("Fallback triggered", "yellow"), sub_dict.get('fallback'), end="-> ")
            return self._recursion_node(sub_dict['fallback'], raw_dict, marc21_dict)
        else:
            self.debug_print(colored("absolutlty nothing", "yellow"), end=" | ")
            return None  # usually i return false in these situations, but none seems appropriate

    @staticmethod
    def _node_preprocessing(value, sub_dict):
        # if there is a match-filter, this filters out the entry or all entries not matching
        if not Spcht.is_dictkey(sub_dict, "match"):
            return value  # the nothing happens clause
        if isinstance(value, str):
            finding = re.search(sub_dict['match'], value)
            if finding is not None:
                return finding.string
            else:
                return None
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                finding = re.search(sub_dict['match'], item)
                if finding is not None:
                    list_of_returns.append(finding.string)
            if 0 < len(list_of_returns) < 2:
                return list_of_returns[0]  # if there is only one surviving element there is no point in returning a list
            elif len(list_of_returns) > 1:
                return list_of_returns
            else:
                return None
        else:  # fallback if its anything else i dont intended to handle with this
            return value

    def _node_postprocessing(self, value, sub_dict):
        # after having found a value for a given key and done the appropriate mapping the value gets transformed
        # once more to change it to the provided pattern

        if not Spcht.is_dictkey(sub_dict, "cut"):
            return value  # the nothing happens clause, again
        if isinstance(value, str):
            pure_filter = re.sub(sub_dict['cut'], sub_dict.get("replace", ""), value)
            self._addToSaveAs(pure_filter, sub_dict)
            return sub_dict.get('prepend', "") + pure_filter + sub_dict.get('append', "")
        elif isinstance(value, list):
            list_of_returns = []
            for item in value:
                pure_filter = re.sub(sub_dict['cut'], sub_dict.get("replace", ""), item)
                self._addToSaveAs(pure_filter, sub_dict)
                rest_str = sub_dict.get('prepend', "") + pure_filter + sub_dict.get('append', "")
                list_of_returns.append(rest_str)
            if len(list_of_returns) == 1:
                return list_of_returns[0]  # we are handling lists later anyway, but i am cleaning here a bit
            else:
                return list_of_returns # there should always be elements, even if they are empty, we are staying faithful here
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
            # ! this here might be a bug, if there is no mapping but a fallback the fallback gets ignored
            # that bug might be actually more on the SDF Writer than on me
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

    def processData(self, raw_dict, graph, marc21="fullrecord", marc21_source="dict"):
        # takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
        # per default it assumes there is a marc entry in the solrdump but it can be provided directly
        # it also takes technically any dictionary with entries as input
        # spcht descriptor format - sdf
        # ! this is temporarily here, i am not sure how i want to handle the descriptor dictionary for now
        # ! there might be a use case to have a different mapping file for every single call instead of a global one
        # Preparation of Data to make it more handy in the further processing
        marc21_record = None  # setting a default here
        if marc21_source == "dict":
            marc21_record = Spcht.marc2list(raw_dict.get(marc21))
        elif marc21_source == "none":
            pass  # this is more a nod to anyone reading this than actually doing anything
        else:
            return False  # TODO alternative marc source options
            # ? what if there are just no marc data and we know that in advance?
        list_of_sparql_inserts = []
        debug_list = []
        # generate core graph, i presume we already checked the spcht for being corredct
        # ? instead of making one hard coded go i could insert a special round of the general loop right?
        sub_dict = {
            "name": "$Identifier$",  # this does nothing functional but gives the debug text a non-empty string
            "source": self._DESCRI['id_source'],
            # i want to throw this exceptions, but the format is checked anyway right?!
            "field": self._DESCRI['id_field'],
            "subfield": self._DESCRI.get('id_subfield', None),
            # i am aware that .get returns none anyway, this is about you
            "alternatives": self._DESCRI.get('id_alternatives', None),
            "fallback": self._DESCRI.get('id_fallback', None)
        }
        ressource = self._recursion_node(sub_dict, raw_dict, marc21_record)
        self.debug_print("Res", colored(ressource, "green"))
        if ressource is not None:
            for node in self._DESCRI['nodes']:
                facet = self._recursion_node(node, raw_dict, marc21_record)
                self.debug_print(colored(facet, "green"))
                # ? maybe i want to output a more general s p o format? or rather only "p & o"
                if facet is None:
                    if node['required'] == "mandatory":
                        return False  # cannot continue without mandatory fields
                elif isinstance(facet, str):
                    # list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], facet))
                    if node.get('type', "literal") != "triple":
                        list_of_sparql_inserts.append("<{}> <{}> \"{}\" .\n".format(graph + ressource, node['graph'], facet))
                    else:
                        list_of_sparql_inserts.append(
                            "<{}> <{}> <{}> .\n".format(graph + ressource, node['graph'], facet))
                    debug_list.append("{} - {}".format(node['graph'], facet))
                elif isinstance(facet, tuple):
                    self.debug_print("Tuple found", facet)
                elif isinstance(facet, list):
                    for item in facet:
                        # list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], item))
                        debug_list.append("{} - {}".format(node['graph'], item))
                        if node.get('type', "literal") != "triple":
                            list_of_sparql_inserts.append("<{}> <{}> \"{}\" .\n".format(graph + ressource, node['graph'], item))
                        else:
                            list_of_sparql_inserts.append(
                                "<{}> <{}> <{}> .\n".format(graph + ressource, node['graph'], item))
                else:
                    print(facet, "I cannot handle that for the moment", "magenta", file=self.std_err)
        else:
            return False  # ? or none?

        # ! this is NOT final
        # return debug_list
        return list_of_sparql_inserts

    # TODO: Error logs for known error entries and total failures as statistic
    # TODO: Grouping of graph descriptors in an @context
    # TODO: remove debug prints
    # TODO: learn how to properly debug in python, i am quite sure print isn't the way to go

    @staticmethod
    def check_format(descriptor, out=sys.stderr, i18n=None):
        # originally this wasnt a static method, but we want to use it to check ANY descriptor format, not just this
        # for this reasons this has its own out target instead of using that of the instance
        # checks the format for any miss shaped data structures
        # * what it does not check for is illogical entries like having alternatives for a pure marc source
        # for language stuff i give you now the ability to actually provide local languages
        error_desc = {
            "header_miss": "The main header informations [id_source, id_field, main] are missing, is this even the right file?",
            "header_mal": "The header information seems to be malformed",
            "basic_struct": "Elements of the basic structure ( [source, field, required, graph] ) are missing",
            "regex": "The provided regex is not correct",
            "marc_subfield": "Every marc entry needs a field AND a subfield or subfield_s_ item, cannot find subfield/s.",
            "marc_subfield_str": "The subfield key has to be a string value",
            "marc_subfields_list": "The Value of the subfield*S* key has to be a list (of strings)",
            "marc_subfields_str": "Every single element of the subfield*S* list has to be a string",
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
            "fallback_dict": "Fallback structure must be an dictionary build like a regular node"
        }
        if isinstance(i18n, dict):
            for key, value in error_desc.items():
                if Spcht.is_dictkey(i18n, key) and isinstance(i18n[key], str):
                    error_desc[key] = i18n[key]
        # ? this should probably be in every reporting function which bears the question if its not possible in another way
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
        if not Spcht._check_format_node(header_node, error_desc, out):
            print("header_mal", file=out)
            return False
        # end of header checks
        for node in descriptor['nodes']:
            if not Spcht._check_format_node(node, error_desc, out, True):
                print(error_desc['nodes'], node.get('name', node.get('field', "unknown")), file=out)
                return False
        # ! make sure everything that has to be here is here
        return True

    @staticmethod
    def _check_format_node(node, error_desc, out, is_root=False):
        # @param node - a dictionary with a single node in it
        # @param error_desc - the entire flat dictionary of error texts
        # * i am writing print & return a lot here, i really considered making a function so i can do "return funct()"
        # * but what is the point? Another sub function to save one line of text each time and obfuscate the code more?
        if not is_root and not Spcht.is_dictkey(node, 'source', 'field'):
            print(error_desc['basic_struct'], file=out)
            return False
        if is_root and not Spcht.is_dictkey(node, 'source', 'field', 'required', 'graph'):
            print(error_desc['basic_struct'], file=out)
            return False

        if not isinstance(node['field'], str):  # ? is a one character string a chr?
            print(error_desc['field_str'], file=out)
            return False

        if node['source'] == "marc":
            if not Spcht.is_dictkey(node, 'subfield') and not Spcht.is_dictkey(node, 'subfields') :
                print(error_desc['marc_subfield'], file=out)
                return False
            if Spcht.is_dictkey(node, 'subfield') and not isinstance(node['subfield'], str):  # check subfield further
                print(error_desc['marc_subfield_str'], file=out)
                return False
            if Spcht.is_dictkey(node, 'subfields'):  # more than one check for subfields
                if not isinstance(node['subfields'], list):
                    print(error_desc['marc_subfields_list'], file=out)
                    return False
                # we have established that we got a list, now we proceed
                for singular_subfield in node['subfields']:
                    if not isinstance(singular_subfield, str):
                        print(error_desc['marc_subfields_str'], file=out)
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
            if Spcht.is_dictkey(node, "mapping_settings"):
                if not isinstance(node['mapping_settings'], dict):
                    print(error_desc['maps_dict'], file=out)
                    return False
                else:  # ? boilerplatze, boilerplate does whatever boilerplate does
                    for key, value in node['mapping_settings'].items():
                        if not isinstance(value, str):
                            # special cases upon special cases, here its the possibility of true or false for $default
                            if isinstance(value, bool) and key == "$default":
                                pass
                            else:
                                print(error_desc['maps_dict_str'], file=out)
                                return False
        # root node specific things
        # TODO: include dictmap for checking
        if is_root:
            if not isinstance(node['required'], str):
                print(error_desc['required_str'], file=out)
                return False
            if node['required'] != "optional" and node['required'] != "mandatory":
                print(error_desc['required_chk'], file=out)
                return False
            # checks for correct data types, its pretty much 4 time the same code but there might be a case
            # where i want to change the datatype so i let it be split for later handling
            if Spcht.is_dictkey(node, 'cut') and not isinstance(node['cut'], str):
                print(error_desc['must_str'].format("cut"), file=out)
                return False
            if Spcht.is_dictkey(node, 'match') and not isinstance(node['cut'], str):
                print(error_desc['must_str'].format("match"), file=out)
                return False

            if not Spcht.validate_regex(node.get('match', r"")) or not Spcht.validate_regex(node.get('cut', r"")):
                print(error_desc['regex'], file=out)
                return False

            if Spcht.is_dictkey(node, 'prepend') and not isinstance(node['cut'], str):
                print(error_desc['must_str'].format("prepend"), file=out)
                return False
            if Spcht.is_dictkey(node, 'append') and not isinstance(node['cut'], str):
                print(error_desc['must_str'].format("append"), file=out)
                return False

        if Spcht.is_dictkey(node, 'fallback'):
            if isinstance(node['fallback'], dict):
                if not Spcht._check_format_node(node['fallback'], error_desc, out):  # ! this is recursion
                    print(error_desc['fallback'], file=out)
                    return False
            else:
                print(error_desc['fallback_dict'], file=out)
                return False
        return True

