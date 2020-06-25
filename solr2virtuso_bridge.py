#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import json
import sys

import pymarc

from local_tools import is_dictkey, is_dict, cprint_type
from virt_connect import sparqlQuery
from termcolor import colored, cprint
from legacy_tools import bird_sparkle_insert, bird_sparkle, bird_longhandle, fish_interpret
from solr_tools import marc2list, marc21_fixRecord

ERROR_TXT = {}
URLS = {}
SETTINGS = {}
SPCHT = None  # SPECHT DESCRIPTOR FORMAT mapping


def send_error(message, error_name=None):
    # custom error handling to use the texts provided by the settings
    global ERROR_TXT
    if error_name is None:
        if is_dictkey(ERROR_TXT, message):  # if there is a short handle for the error simply use that one
            sys.stderr.write(ERROR_TXT[message])
        else:
            sys.stderr.write(message)
    else:
        if is_dictkey(ERROR_TXT, error_name):
            sys.stderr.write(ERROR_TXT[error_name].format(message))
        else:
            sys.stderr.write(message)


def load_config(file_path="config.json"):
    # loads json file with all the config settings, uses defaults when possible
    global ERROR_TXT, URLS, SETTINGS
    with open(file_path) as json_file:
        data = json.load(json_file)
        try:
            ERROR_TXT = data['errors']
        except KeyError:
            send_error("Cannot find 'error' Listings in {} File".format(file_path))  # in this there is not error field
            sys.exit()
        try:
            URLS = data['urls']
        except KeyError:
            send_error("urls")
            sys.exit()  #  maybe to harsh,
        try:
            SETTINGS = data['settings']
        except KeyError:
            send_error("SETTINGS")
            sys.exit()


def load_from_json(file_path):
    try:
        with open(file_path,mode='r') as rdf_file:
            return json.load(rdf_file)

    except FileNotFoundError:
        send_error("nofile")
    except ValueError:
        send_error("json_parser")
    except:
        send_error("graph_parser")
    # this looks like ripe for a finally block right? wrong, finally gets ALWAYS executed, we dont want that
    return False


def init_graph_name(file_path="init_labels.json"):
    global URLS
    # inserts all the description things for the other graphs, should only run once but the way
    # sparql works it matters little to repeat it...at least i hoe that
    try:
        json_file = open(file_path, mode="r")
        rdf = json.load(json_file)
    except FileNotFoundError:
        return False
    all_sparql = "INSERT IN GRAPH <{}> {\n".format(URLS['graph_label'])
    for item in rdf:
        if('s' not in item or
           'p' not in item or
           'o' not in item ):
            continue
        all_sparql += " {} {} {} .\n".format(item['s'], item['p'], item['o'])
    all_sparql += "}"
    return sparqlQuery(all_sparql, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])


def check_spcht_format(spcht_dictionary, out=sys.stderr, i18n=None):
    # checks the format for any miss shaped data structures
    # * what it does not check for is illogical entries like having alternatives for a pure marc source
    # for language stuff i give you now the ability to actually provide local languages
    error_desc = {
        "header_miss": "The main header informations [id_source, id_field, main] are missing, is this even the right file?",
        "header_mal": "The header information seems to be malformed",
        "basic_struct": "Elements of the basic structure ( [source, field, type] ) are missing",
        "marc_subfield": "Every marc entry needs a field AND a subfield item, cannot find subfield.",
        "field_str": "The field entry has to be a string",
        "type_str": "The type entry has to be a string and contain either: 'mandatory' or 'optional",
        "type_chk": "Type-String can only 'mandatory' or 'optional'. Maybe encoding error?",
        "alt_list": "Alternatives must be a list of strings, eg: ['item1', 'item2']",
        "alt_list_str": "Every entry in the alternatives list has to be a string",
        "fallback": "-> structure of the fallback node contains errors",
        "nodes": "-> error in structure of Node",
        "fallback_dict": "Fallback structure must be an dictionary build like a regular node"
    }
    if isinstance(i18n, dict):
        for key, value in error_desc.items():
            if is_dictkey(i18n, key) and isinstance(i18n[key], str):
                error_desc[key] = i18n[key]
    # ? this should probably be in every reporting function which bears the question if its not possible in another way
    # checks basic infos
    if not is_dictkey(spcht_dictionary, 'id_source', 'id_field', 'nodes'):
        print(error_desc['header_miss'], file=out)
        return False
    # transforms header in a special node to avoid boiler plate code
    header_node = {
        "source": spcht_dictionary.get('id_source'),
        "field": spcht_dictionary.get('id_field'),
        "subfield": spcht_dictionary.get('id_subfield', None),
        "alternatives": spcht_dictionary.get('id_alternatives', None),
        "fallback": spcht_dictionary.get('id_fallback', None)
    }  # ? there must be a better way for this mustn't it?
    # a lot of things just to make sure the header node is correct, its almost like there is a better way
    plop = []
    for key, value in header_node.items():  # this removes the none existent entries cause i dont want to add more checks
        if value is None:
            plop.append(key)  # what you cant do with dictionaries you iterate through is removing keys while doing so
    for key in plop:
        header_node.pop(key, None)
    del plop

    #the actual header check
    if not check_spcht_format_node(header_node, error_desc, out):
        print("header_mal", file=out)
        return False
    # end of header checks
    for node in spcht_dictionary['nodes']:
        if not check_spcht_format_node(node, error_desc, out, True):
            print(error_desc['nodes'], node.get('name', node.get('field', "unknown")), file=out)
            return False
    # ! make sure everything that has to be here is here
    return True


def check_spcht_format_node(node, error_desc, out, is_root=False):
    # @param node - a dictionary with a single node in it
    # @param error_desc - the entire flat dictionary of error texts
    # * i am writing print & return a lot here, i really considered making a function so i can do "return funct()"
    # * but what is the point? Another sub function to save one line of text each time and obfuscate the code more?
    if not is_root and not is_dictkey(node, 'source', 'field'):
        print(error_desc['basic_struct'], file=out)
        return False
    if is_root and not is_dictkey(node, 'source', 'field', 'type'):
        print(error_desc['basic_struct'], file=out)
        return False
    if node['source'] == "marc":
        if not is_dictkey(node, 'subfield'):
            print(error_desc['marc_subfield'], file=out)
            return False
    if not isinstance(node['field'], str):  # ? is a one character string a chr?
        print(error_desc['field_str'], file=out)
        return False
    # root node specific things
    if is_root:
        if not isinstance(node['type'], str):
            print(error_desc['type_str'], file=out)
            return False
        if node['type'] != "optional" and node['type'] != "mandatory":
            print(error_desc['type_chk'], file=out)
            return False
    if is_dictkey(node, 'alternatives'):
        if not isinstance(node['alternatives'], list):
            print(error_desc['alt_list'], file=out)
            return False
        else:  # this else is redundant, its here for you dear reader
            for item in node['alternatives']:
                if not isinstance(item, str):
                    print(error_desc['alt_list_str'], file=out)
                    return False
    if is_dictkey(node, 'fallback'):
        if isinstance(node['fallback'], dict):
            if not check_spcht_format_node(node['fallback'], error_desc, out):  # ! this is recursion
                print(error_desc['fallback'], file=out)
                return False
        else:
            print(error_desc['fallback_dict'], file=out)
            return False
    return True


def spcht_recursion_node(sub_dict, raw_dict, marc21_dict=None):
    # i do not like the general use of recursion, but for traversing trees this seems the best solution
    # there is actually not so much overhead in python, its more one of those stupid feelings, i googled some
    # random reddit thread: https://old.reddit.com/r/Python/comments/4hkds8/do_you_recommend_using_recursion_in_python_why_or/
    # @param sub_dict = the part of the descriptor dictionary that is in ['fallback']
    # @param raw_dict = the big raw dictionary that we are working with
    # @param marc21_dict = an alternative marc21 dictionary, already cooked and ready
    # the header/id field is special in some sense, therefore there is a separated function for it
    # ! this can return anything, string, list, dictionary, it just takes the content, careful
    if sub_dict['source'] == "marc":
        if marc21_dict is None:
            print(colored("No Marc", "yellow"))
            pass
        else:
            print(colored("some Marc", "yellow"))
            if is_dictkey(marc21_dict, sub_dict['field'].lstrip("0")):
                if sub_dict['subfield'] == 'none':
                    return marc21_dict[sub_dict['field']]
                elif is_dictkey(marc21_dict[sub_dict['field'].lstrip("0")], sub_dict['subfield']):
                    return marc21_dict[sub_dict['field'].lstrip("0")][sub_dict['subfield']]
        # ! this handling of the marc format is probably too simply
        # TODO: gather more samples of awful marc and process it
    elif sub_dict['source'] == "dict":
        print(colored("Source Dict", "yellow"))
        if is_dictkey(raw_dict, sub_dict['field']):  # main field name
            return raw_dict[sub_dict['field']]
        # ? since i prime the sub_dict what is even the point for checking the existence of the key, its always there
        elif is_dictkey(sub_dict, 'alternatives') and sub_dict['alternatives'] is not None:  # traverse list of alternative field names
            print(colored("Alternatives", "yellow"))
            for entry in sub_dict['alternatives']:
                if is_dictkey(raw_dict, entry):
                    return raw_dict[entry]
    if is_dictkey(sub_dict, 'fallback') and sub_dict['fallback'] is not None:  # we only get here if everything else failed
        # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
        # * librarian was who wrote the descriptor format
        print(colored("Fallback triggered", "yellow"), sub_dict.get('fallback'))
        return spcht_recursion_node(sub_dict['fallback'], raw_dict, marc21_dict)
    else:
        print(colored("absolutlty nothing", "yellow"))
        return None  # usually i return false in these situations, but none seems appropriate
# TODO: remove debug prints


def convertMapping(raw_dict, graph, marc21="fullrecord", marc21_source="dict"):
    # takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
    # per default it assumes there is a marc entry in the solrdump but it can be provided directly
    # it also takes technically any dictionary with entries as input
    global SPCHT
    spcht = SPCHT  # spcht descriptor format - sdf
    # ! this is temporarily here, i am not sure how i want to handle the descriptor dictionary for now
    # ! there might be a use case to have a different mapping file for every single call instead of a global one
# Preparation of Data to make it more handy in the further processing
    marc21_record = None # setting a default here
    if marc21_source == "dict":
        marc21_record = marc2list(raw_dict.get(marc21))
    elif marc21_source == "none":
        pass  # this is more a nod to anyone reading this than actually doing anything
    else:
        return False  # TODO alternative marc source options
        # ? what if there are just no marc data and we know that in advance?
    list_of_sparql_inserts = []
# generate core graph, i presume we already checked the spcht for being corredct
# ? instead of making one hard coded go i could insert a special round of the general loop right?
    sub_dict = {
        "source": spcht.get('id_source'),
        "field": spcht.get('id_field'),
        "subfield": spcht.get('id_subfield', None),
        "alternatives": spcht.get('id_alternatives', None),
        "fallback": spcht.get('id_fallback', None)
    }
    ressource = spcht_recursion_node(sub_dict, raw_dict, marc21_record)
    print("Res", colored(ressource, "green"))
    if ressource is not None:
        for node in spcht['nodes']:
            sub_dict = {  # this is boilerplate from above but i found no apparent solution to it
                "source": node['source'],  # i want to throw this exceptions, but the format is checked anyway right?!
                "field": node['field'],
                "subfield": node.get('subfield', None),  # i am aware that .get returns none anyway, this is about you
                "alternatives": node.get('alternatives', None),
                "fallback": node.get('fallback', None)
            }
            facet = spcht_recursion_node(sub_dict, raw_dict, marc21_record)
            print(node.get('name'), colored(facet, "cyan"))
            if facet is None:
                if node['type'] == "mandatory":
                    return False  # cannot continue without mandatory fields
            elif isinstance(facet, str):
                list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], facet))
            elif isinstance(facet, tuple):
                print(colored("Tuple found", "red"), facet)
            elif isinstance(facet, list):
                for item in facet:
                    list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], item))
            else:
                print(facet, colored("I cannot handle that for the moment", "magenta"))
    else:
        return False  # ? or none?
    for line in list_of_sparql_inserts:
        print(line, end="\r")

# TODO: Error logs for known error entries and total failures as statistic
# TODO: Grouping of graph descriptors in an @context
# TODO: remove debug prints
# TODO: learn how to properly debug in python, i am quite sure print isn't the way to go


# * other stuff that gets definitely deleted later on
def other_fish():
    print(colored("Programmstart", "green"))
    data = load_from_json("2nd-entry.txt")
    sparql = fish_interpret(data)
    print(colored("Anzahl an Sparql Inserts: {}".format(len(sparql)), "cyan"))
    print(colored(bird_sparkle_insert(URLS['graph'], sparql), "green", attrs=["bold"]))
    # sparqlQuery(entry, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])


def marc_test():
    print(colored("Test Marc Stuff", "cyan"))

    myfile = open("marc21test.json", "r")
    marctest = json.load(myfile)
    myfile.close()

    print(colored(marctest, "yellow"))
    print(json.dumps(marc2list(marctest.get('fullrecord')), indent=4))


if __name__ == "__main__":
    load_config()
    test = load_from_json("1fromsolrs.json")
    # load spcht format
    temp = load_from_json("default.spcht.json")
    if check_spcht_format(temp):
        cprint("SPCHT Format o.k.", "green", attrs=["bold"])
        SPCHT = temp
        del temp
    if SPCHT is not None:
        convertMapping(test, URLS['graph'])


# TODO: create real config example file without local/vpn data in it
