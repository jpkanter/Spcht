#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import json
import sys

import pymarc

from local_tools import is_dictkey, is_dict, cprint_type
from virt_connect import sparqlQuery
from termcolor import colored
from legacy_tools import fish_sparkle_insert, fish_sparkle, fish_longhandle, fish_interpret
from solr_tools import marc2list, marc21_fixRecord

ERROR_TXT = {}
URLS = {}
SETTINGS = {}


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


def check_salmon_format(salmon_dictionary):
    # ! make sure everything that has to be here is here
    return True


def salmon_recursion_node(sub_dict, raw_dict, marc21_dict=None):
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
            if is_dictkey(marc21_dict, sub_dict['field']):
                if sub_dict['subfield'] == 'none':
                    return marc21_dict[sub_dict['field']]
                elif is_dictkey(marc21_dict[sub_dict['field']], sub_dict['subfield']):
                    return marc21_dict[sub_dict['field']][sub_dict['subfield']]
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
        return salmon_recursion_node(sub_dict['fallback'], raw_dict, marc21_dict)
    else:
        print(colored("absolutlty nothing", "yellow"))
        return None  # usually i return false in these situations, but none seems appropriate
# TODO: remove debug prints


def convertMapping(raw_dict, graph, marc21="fullrecord", marc21_source="dict"):
    # takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
    # per default it assumes there is a marc entry in the solrdump but it can be proviced directly
    # it also takes technically any dictionary with entries
    temp_mapping = {
        "id_source": "dict",
        "id_field": "id",
        "id_fallback": {
            "source": "marc",
            "field": "001",
            "subfield": "none"
        },
        "nodes": [
            {
                "name": "ISBN",
                "source": "dict",
                "graph": "http://purl.org/ontology/bibo/isbn",
                "field": "isbn",
                "type": "optional",
                "fallback": {
                    "source": "marc",
                    "field": "020",
                    "subfield": "a"
                }
            },
            {
                "name": "ISSN",
                "source": "dict",
                "graph": "http://purl.org/ontology/bibo/issn/",
                "field": "issn",
                "type": "optional",
                "fallback": {
                    "source": "marc",
                    "field": "022",
                    "subfield": "a"
                }
            },
            {
                "name": "Titel des Werkes",
                "source": "dict",
                "graph": "http://purl.org/dc/terms/title",
                "field": "title",
                "alternatives": ["title_full", "title_fullStr", "title_full_unstemmed"],
                "type": "mandatory",
                "fallback": {
                    "source": "marc",
                    "field": "245",
                    "subfield": "concat",
                    "comment": "concat might not be the best source, marc:245 seems complex, TODO"  # ? how?
                }
            }
        ]
    }
    salmon = temp_mapping  # salmon descriptor format - sdf
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
# generate core graph, i presume we already checked the salmon for being fresh
# TODO check function to make sure the salmon is fresh = the format is correct
# ? instead of making one hard coded go i could insert a special round of the general loop right?
    sub_dict = {
        "source": salmon.get('id_source'),
        "field": salmon.get('id_field'),
        "subfield": salmon.get('id_subfield', None),
        "alternatives": salmon.get('id_alternatives', None),
        "fallback": salmon.get('id_fallback', None)
    }
    ressource = salmon_recursion_node(sub_dict, raw_dict, marc21_record)
    print("Res", colored(ressource, "green"))
    if ressource is not None:
        for node in salmon['nodes']:
            sub_dict = {  # this is boilerplate from above but i found no apparent solution to it
                "source": node['source'],  # i want to throw this exceptions, but the format is checked anyway right?!
                "field": node['field'],
                "subfield": node.get('subfield', None),  # i am aware that .get returns none anyway, this is about you
                "alternatives": node.get('alternatives', None),
                "fallback": node.get('fallback', None)
            }
            facet = salmon_recursion_node(sub_dict, raw_dict, marc21_record)
            print(colored(facet, "cyan"))
            if facet is None:
                if node['type'] == "mandatory":
                    return False  # cannot continue without mandatory fields
            elif isinstance(facet, str):
                list_of_sparql_inserts.append(fish_sparkle(graph + ressource, node['graph'], facet))
            elif isinstance(facet, list):
                for item in facet:
                    list_of_sparql_inserts.append(fish_sparkle(graph + ressource, node['graph'], item))
            else:
                print(facet, colored("I cannot handle that for the moment", "magenta"))
    else:
        return False  # ? or none?
    print(list_of_sparql_inserts)

# TODO: Error logs for known error entries and total failures as statistic
# TODO: Grouping of graph descriptors in an @context
# TODO: remove debug prints
# TODO: learn how to properly debug in python, i am quite sure print isn't the way to go


# * other stuff that gets definetly deleted later on
def other_fish():
    print(colored("Programmstart", "green"))
    data = load_from_json("2nd-entry.txt")
    sparql = fish_interpret(data)
    print(colored("Anzahl an Sparql Inserts: {}".format(len(sparql)), "cyan"))
    print(colored(fish_sparkle_insert(URLS['graph'], sparql), "green", attrs=["bold"]))
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
    convertMapping(test, URLS['graph'])


# TODO: create real config example file without local/vpn data in it
