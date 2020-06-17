#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import json
import sys


from local_tools import is_dictkey, is_dict
from virt_connect import sparqlQuery
from termcolor import colored

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


def load_from_jsonld(file_path):
    try:
        with open(file_path,mode='r') as rdf_file:
            return json.load(rdf_file)

    except FileNotFoundError:
        send_error("nofile")
    except ValueError:
        send_error("json_parser")
    except:
        send_error("graph_parser")


def init_graph_name(file_path="init_labels.json"):
    global URLS
    # inserts all the description things for the other graphs, should only run once but the way
    # sparql works it matters little to repeat it...at least i hoe that
    try:
        json_file = open(file_path, mode="r")
        rdf = json.load(json_file)
    except FileNotFoundError:
        return -1
    all_sparql = ""
    for item in rdf:
        if('s' not in item or
           'p' not in item or
           'o' not in item ):
            continue
        all_sparql += "INSERT DATA {{ GRAPH <{}> {{ {} {} {} }} }}".\
            format(URLS['graph_label'], item['s'], item['p'], item['o'])

    return sparqlQuery(all_sparql, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])


# monkey as in monkeypatch, its not meant to be offensive, its just that i feel pretty bad about the
# whole things, i write a lot of lines to create something that is really only use able in development


def monkey_interpret_herring(data):
    #  this function interprets the specific file format i got from another script, it feels very hacky
    shorts = {}
    subject = ""
    node = {}
    sparsql_queries = []
    for entry in data.items():
        if entry[0] == "@context":
            for handle in entry[1].items():
                shorts[handle[0]] = handle[1]
                # there are some entries in @context that are not mappings, doesnt matter for the time being
        elif entry[0] == "@id":
            subject = entry[1]
        else:
            node[entry[0]] = entry[1]

    for key, value in node.items():
        if isinstance(value, list):
            print(key, "|", type(value), " - ", colored(value, "green"))
            for element in value:  # iterate through list, statement for each entry
                # not proud on this one
                try:
                    sparsql_queries.append(monkey_sparkle(subject, monkey_longhandle(shorts, key), element))
                except TypeError:  # mostly cause monkey handle gives False
                    pass  # error message is handled by monkey handle
        elif isinstance(value, tuple):
            print(key, "|", type(value), " - ", colored(value, "yellow"))
        elif isinstance(value, str):
            print(key, "|", type(value), " - ", colored(value, "magenta"))
            try:
                sparsql_queries.append(monkey_sparkle(subject, monkey_longhandle(shorts, key), value))
            except TypeError:  # mostly cause monkey handle gives False
                pass  # error message is handled by monkey handle
        elif isinstance(value, dict):
            print(key, "|", type(value), " - ", colored(value, "cyan"))
        else:
            print(key, "|", type(value), " - ", colored(value, "red"))

    return sparsql_queries


def monkey_longhandle(shorts, statement):
    # this, which is not advisable, makes every short statement to a long statement, again
    # shorts - list of @context stuff
    # statement - already short handled stuff, example: dct:isPartOf
    parts = statement.split(":")
    if is_dictkey(shorts, parts[0]) and len(parts) == 2:
        return shorts[parts[0]] + parts[1]
    elif len(parts) == 1:
        return statement  # basically does nothing
    else:
        send_error(parts[0], "@context")
        return False


def monkey_sparkle(subject, predicate, object):
    # creates a simple sparkSQL query without any frills, not to be used in production
    global URLS
    return """INSERT DATA 
                { GRAPH <"""+URLS['graph']+""">
                    { 
                        <"""+subject+"""> 
                        <"""+predicate+"""> 
                        '"""+object+"""' .
                      }  
                }
            """


def test_stdin():
    data = sys.stdin.readlines()
    print("Counted", len(data), "lines.")

if __name__ == "__main__":
    load_config()
    print(colored("Programmstart", "green"))
    test_stdin()
    # data = load_from_jsonld("2nd-entry.txt")
    sparql = monkey_interpret_herring(data)
    print(colored("Anzahl an Sparql Inserts: {}".format(len(sparql)), "cyan"))
    for entry in sparql:
        print(colored(entry, "green", attrs=["bold"]))
        # sparqlQuery(entry, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])