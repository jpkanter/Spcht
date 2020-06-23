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


def convertMapping(raw_dict, marc21="fullrecord", marc21_source="dict"):
    # takes a raw solr query and converts it to a list of sparql queries to be inserted in a triplestore
    # per default it assumes there is a marc entry in the solrdump but it can be proviced directly
    # it also takes technically any dictionary with entries
    temp_mapping = [
        {
            "name": "eindeutige Identifikationsnummer",
            "source": "dict",
            "graph": "http://data.finc.info/resources/",
            "field": "id",
            "type": "mandatory",
            "fallback": {
                "source": "marc",
                "field": "001",
                "subfield": "none"
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
                "field": "020",
                "subfield": "a"
            }
        }
    ]
# TODO: Redesign of the format for head data = id mapping
# TODO: Fallback Mappings and recursive descriptors
# TODO: Error logs for known error entries and total failures as statistic
# TODO: Grouping of graph descriptors in an @context
# TODO: consideration of a `fallback` tag in the dictionary


def main():
    print(colored("Programmstart", "green"))
    data = load_from_json("2nd-entry.txt")
    sparql = fish_interpret(data)
    print(colored("Anzahl an Sparql Inserts: {}".format(len(sparql)), "cyan"))
    print(colored(fish_sparkle_insert(URLS['graph'], sparql), "green", attrs=["bold"]))
    # sparqlQuery(entry, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])


if __name__ == "__main__":
    load_config()
    print(colored("Test Marc Stuff", "cyan"))

    myfile = open("marc21test.json", "r")
    marctest = json.load(myfile)
    myfile.close()

    print(colored(marctest, "yellow"))
    print(json.dumps(marc2list(marctest.get('fullrecord')), indent=4))




