import sys

from termcolor import colored
from local_tools import is_dictkey


def fish_interpret(data):
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
            # print(key, "|", type(value), " - ", colored(value, "green"))
            for element in value:  # iterate through list, statement for each entry
                # not proud on this one
                try:
                    sparsql_queries.append(bird_sparkle(subject, bird_longhandle(shorts, key), element))
                except TypeError:  # mostly cause monkey handle gives False
                    pass  # error message is handled by monkey handle
        elif isinstance(value, tuple):
            print(key, "|", type(value), " - ", colored(value, "yellow"))
        elif isinstance(value, str):
            # print(key, "|", type(value), " - ", colored(value, "magenta"))
            try:
                sparsql_queries.append(bird_sparkle(subject, bird_longhandle(shorts, key), value))
            except TypeError:  # mostly cause monkey handle gives False
                pass  # error message is handled by monkey handle
        elif isinstance(value, dict):
            print(key, "|", type(value), " - ", colored(value, "cyan"))
        else:
            print(key, "|", type(value), " - ", colored(value, "red"))

    return sparsql_queries


def bird_longhandle(shorts, statement):
    # this, which is not advisable, makes every short statement to a long statement, again
    # shorts - list of @context stuff
    # statement - already short handled stuff, example: dct:isPartOf
    parts = statement.split(":")
    if is_dictkey(shorts, parts[0]) and len(parts) == 2:
        return shorts[parts[0]] + parts[1]
    elif len(parts) == 1:
        return statement  # basically does nothing
    else:
        sys.stderr.write("Mapping unvollständig, unauflösbare Kurzform gefunden {}\n".format(statement))
        return False


def bird_sparkle(subject, predicate, object):
    # creates a simple sparkSQL query without any frills, not to be used in production
    return "<{}> <{}> \"{}\" .\n".format(subject, predicate, object)


def bird_sparkle_insert(graph, insert_list):
    sparkle = "INSERT IN GRAPH <{}> {{\n".format(graph)
    for entry in insert_list:
        sparkle += entry
    sparkle += "}}"
    return sparkle
