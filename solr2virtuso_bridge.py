#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import copy
import json
import math
import sys
import time

import pymarc

from local_tools import is_dictkey, is_dict, cprint_type
from virt_connect import sparqlQuery
from termcolor import colored, cprint
from legacy_tools import bird_sparkle_insert, bird_sparkle, bird_longhandle, fish_interpret
from solr_tools import marc2list, marc21_fixRecord, load_remote_content, test_json, slice_header_json

ERROR_TXT = {}
URLS = {}
SETTINGS = {}
SPCHT = None  # SPECHT DESCRIPTOR FORMAT mapping
TESTFOLDER = "./testdata/"


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
    # TODO: give me actually helpful insights about the json here, especially where its wrong, validation and all
    try:
        with open(file_path, mode='r') as file:
            return json.load(file)

    except FileNotFoundError:
        send_error("nofile")
    except ValueError:
        send_error("json_parser")
    except:
        send_error("graph_parser")
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


def load_spcht_descriptor_file(filename):
    # returns None if something is amiss, returns the descriptors as dictionary
    # ? turns out i had to add some complexity starting with the "include" mapping
    descriptor = load_from_json(filename)
    if isinstance(descriptor, bool):  # load json goes wrong if something is wrong with the json
        return None
    if not check_spcht_format(descriptor):
        return None
    # * goes through every mapping node and adds the reference files, which makes me basically rebuild the thing
    # ? python iterations are not with pointers, so this will expose me as programming apprentice but this will work
    new_node = []
    for item in descriptor['nodes']:
        a_node = load_spcht_ref_node(item)
        if isinstance(a_node, bool):  # if something goes wrong we abort here
            send_error("spcht_ref")
            return None
        new_node.append(a_node)
    descriptor['nodes'] = new_node  # replaces the old node with the new, enriched ones
    return descriptor


def load_spcht_ref_node(node_dict):
    # We are again in beautiful world of recursion. Each node can contain a mapping and each mapping can contain
    # a reference to a mapping json. i am actually quite worried that this will lead to performance issues
    # TODO: Research limits for dictionaries and performance bottlenecks
    # so, this returns False and the actual loading operation returns None, this is cause i think, at this moment,
    # that i can check for isinstance easier than for None, i might be wrong and i have not looked into the
    # cost of that operation if that is ever a concern
    if is_dictkey(node_dict, 'fallback'):
        node_dict['fallback'] = load_spcht_ref_node(node_dict['fallback'])  # ! there it is again, the cursed recursion thing
        if isinstance(node_dict['fallback'], bool):
            return False
    if is_dictkey(node_dict, 'mapping_settings') and node_dict['mapping_settings'].get('$ref') is not None:
        file_path = node_dict['mapping_settings']['$ref']  # ? does it always has to be a relative path?
        try:
            map_dict = load_from_json(file_path)
            # iterate through the dict, if manual entries have the same key ignore
            if not isinstance(map_dict, dict):  # we expect a simple, flat dictionary, nothing else
                return False  # funnily enough, this also includes bool which happens when json loads fails
            # ! this here is the actual logic that does the thing:
            # there might no mapping key at all
            if not is_dictkey(node_dict, 'mapping'):
                node_dict['mapping'] = {}
            for key, value in map_dict.items():
                if not isinstance(value, str):  # only flat dictionaries, no nodes
                    send_error("spcht_map")
                    return False
                if not is_dictkey(node_dict['mapping'], key):  # existing keys have priority
                    node_dict['mapping'][key] = value
            del map_dict
            # clean up mapping_settings node
            del(node_dict['mapping_settings']['$ref'])
            if len(node_dict['mapping_settings']) <= 0:
                del(node_dict['mapping_settings'])  # if there are no other entries the entire mapping settings goes

        except FileNotFoundError:
            send_error(file_path, "file")
            return False
        except KeyError:
            send_error("KeyError")
            return False

    return node_dict  # whether nothing has had changed or not, this holds true


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
        "map_dict": "Translation mapping must be a dictionary",
        "map_dict_str": "Every element of the mapping must be a string",
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
        "fallback": spcht_dictionary.get('id_fallback', None)
        # this main node doesnt contain alternatives
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
    # TODO: include dictmap for checking
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
    if is_dictkey(node, 'mapping'):
        if not isinstance(node['mapping'], dict):
            print(error_desc['map_dict'], file=out)
            return False
        else:  # ? again the thing with the else for comprehension, this comment is superfluous
            for key, value in node['mapping'].items():
                if not isinstance(value, str):
                    print(error_desc['map_dict_str'], file=out)
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
    debug_list = []
# generate core graph, i presume we already checked the spcht for being corredct
# ? instead of making one hard coded go i could insert a special round of the general loop right?
    sub_dict = {
        "source": spcht['id_source'],  # i want to throw this exceptions, but the format is checked anyway right?!
        "field": spcht['id_field'],
        "subfield": spcht.get('id_subfield', None),  # i am aware that .get returns none anyway, this is about you
        "alternatives": spcht.get('id_alternatives', None),
        "fallback": spcht.get('id_fallback', None)
    }
    ressource = spcht_recursion_node(sub_dict, raw_dict, marc21_record)
    # print("Res", colored(ressource, "green"))
    if ressource is not None:
        for node in spcht['nodes']:
            facet = spcht_recursion_node(node, raw_dict, marc21_record)
            # print(colored(facet, "green"))
            # ? maybe i want to output a more general s p o format? or rather only "p & o"
            if facet is None:
                if node['type'] == "mandatory":
                    return False  # cannot continue without mandatory fields
            elif isinstance(facet, str):
                # list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], facet))
                list_of_sparql_inserts.append(bird_sparkle(graph+ressource, node['graph'], facet))
                debug_list.append("{} - {}".format(node['graph'], facet))
            elif isinstance(facet, tuple):
                print(colored("Tuple found", "red"), facet)
            elif isinstance(facet, list):
                for item in facet:
                    # list_of_sparql_inserts.append(bird_sparkle(graph + ressource, node['graph'], item))
                    debug_list.append("{} - {}".format(node['graph'], item))
                    list_of_sparql_inserts.append(bird_sparkle(graph+ressource, node['graph'], item))
            else:
                print(facet, colored("I cannot handle that for the moment", "magenta"))
    else:
        return False  # ? or none?

    # ! this is NOT final
    #return debug_list
    return list_of_sparql_inserts

# TODO: Error logs for known error entries and total failures as statistic
# TODO: Grouping of graph descriptors in an @context
# TODO: remove debug prints
# TODO: learn how to properly debug in python, i am quite sure print isn't the way to go


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
            pass
        else:
            if is_dictkey(marc21_dict, sub_dict['field'].lstrip("0")):
                if sub_dict['subfield'] == 'none':
                    return marc21_dict[sub_dict['field']]
                elif is_dictkey(marc21_dict[sub_dict['field'].lstrip("0")], sub_dict['subfield']):
                    return marc21_dict[sub_dict['field'].lstrip("0")][sub_dict['subfield']]
        # ! this handling of the marc format is probably too simply
        # TODO: gather more samples of awful marc and process it
    elif sub_dict['source'] == "dict":
        if is_dictkey(raw_dict, sub_dict['field']):  # main field name
            return spcht_node_mapping(raw_dict[sub_dict['field']], sub_dict.get('mapping'), sub_dict.get('mapping_settings'))
        # ? since i prime the sub_dict what is even the point for checking the existence of the key, its always there
        elif is_dictkey(sub_dict, 'alternatives') and sub_dict['alternatives'] is not None:  # traverse list of alternative field names
            for entry in sub_dict['alternatives']:
                if is_dictkey(raw_dict, entry):
                    return spcht_node_mapping(raw_dict[entry], sub_dict.get('mapping'), sub_dict.get('mapping_settings'))

    if is_dictkey(sub_dict, 'fallback') and sub_dict['fallback'] is not None:  # we only get here if everything else failed
        # * this is it, the dreaded recursion, this might happen a lot of times, depending on how motivated the
        # * librarian was who wrote the descriptor format
        return spcht_recursion_node(sub_dict['fallback'], raw_dict, marc21_dict)
    else:
        return None  # usually i return false in these situations, but none seems appropriate
# TODO: remove debug prints


def spcht_node_mapping(value, mapping, settings):
    the_default = False
    if not isinstance(mapping, dict) or mapping is None:
        return value
    if settings is not None and isinstance(settings, dict):
        if is_dictkey(settings, '$default'):
            the_default = settings['$default']
            # if the value is boolean True it gets copied without mapping
            # if the value is a str that is default, False does nothing but preserves the default state of default
            # Python allows me to get three "boolean" states here done, value, yes and no. Yes is inheritance
        if is_dictkey(settings, '$type'):
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
                    response_list.append(item)         # inherit the former value
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
        if is_dictkey(mapping, value):  # rigid key mapping
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
        print(colored("field contains a non-list, non-string: {}".format(type(value)), "red"))


# * other stuff that gets definitely deleted later on
def other_bird():
    print(colored("Programmstart", "green"))
    data = load_from_json("2nd-entry.txt")
    sparql = fish_interpret(data)
    print(colored("Anzahl an Sparql Inserts: {}".format(len(sparql)), "cyan"))
    print(colored(bird_sparkle_insert(URLS['graph'], sparql), "green", attrs=["bold"]))
    # sparqlQuery(entry, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])


def marc_test():
    global TESTFOLDER
    print(colored("Test Marc Stuff", "cyan"))

    myfile = open(TESTFOLDER+"marc21test.json", "r")
    marctest = json.load(myfile)
    myfile.close()

    print(colored(marctest, "yellow"))
    print(json.dumps(marc2list(marctest.get('fullrecord')), indent=4))


def main_test():
    global URLS
    load_config()
    test = load_from_json(TESTFOLDER + "1fromsolrs.json")
    # load spcht format
    temp = load_spcht_descriptor_file("default.spcht.json")
    if check_spcht_format(temp):
        cprint("SPCHT Format o.k.", "green", attrs=["bold"])
        SPCHT = temp
        del temp
    debug_dict = {
        "0-1172721416": "monographischer Band - Goethes Faust mit Illustrator",
        "0-1172720975": "dazugehörige GA",
        "0-1499736606": "Online-Ressource, Campuslizenz",
        "0-1651221162": "E-Book; LFER, Teil einer gezählten Reihe",
        "0-638069130": "+ dazugehörige Reihe",
        "0-101017634X": "Zeitschrift",
        "0-876618255": "Monographie",
        "0-1575152746": "DVD",
        "0-1353737586": "Handschrift, Hochschulschrift",
        "0-1540394506": "Medienkombination",
        "0-1588127508": "+ Band Medienkombi",
        "0-1563786273": "Mikroform, Hochschulschrift",
        "0-1465972943": "Objekt",
        "0-016092031": "Noten",
        "0-505985926": "CD",
        "0-1648651445": "LFER, GA",
        "0-1385933259": "LFER, dazugehöriger Band",
        "0-1550117564": "japanische Schriftzeichen; Werktitelverknüpfung",
        "0-1550115898": "+ zugehörige GA",
        "0-279416644": "Karte"
    }
    if SPCHT is not None:
        thetestset = load_from_json(TESTFOLDER + "thetestset.json")
        double_list = []
        thesparqlset = []
        for entry in thetestset:
            temp = convertMapping(entry, URLS['graph'])
            if temp:
                double_list.append(
                    "\n\n=== {} - {} ===\n".format(entry.get('id', "Unknown ID"), debug_dict.get(entry.get('id'))))
                double_list += temp
                # TODO Workeable Sparql
                thesparqlset.append(bird_sparkle_insert(URLS['graph'], temp))

        my_debug_output = open("bridgeoutput.txt", "w")
        for line in double_list:
            print(line, file=my_debug_output)
        my_debug_output.close()

        # TODO: trying all 15 Testsets every time
        myfile = open(TESTFOLDER + "newsparql.txt", "w")
        json.dump(thesparqlset, myfile, indent=2)
        myfile.close()

        myfile = open(TESTFOLDER + "testsetsparql.txt", "w")
        for fracta in thesparqlset:
            # sparqlQuery(fracta, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])
            myfile.write(fracta)
            myfile.write("\n\r")
        myfile.close()


# TODO: create real config example file without local/vpn data in it


def full_process():
    global URLS, SPCHT
    load_config()
    SPCHT = load_spcht_descriptor_file("default.spcht.json")
    big_data = []
    total_nodes = 0

    req_rows = 50000
    req_chunk = 1000
    head_start = 50000
    req_para = {'q': "*:*", 'rows': req_rows, 'wt': "json"}

    stormwarden = open(TESTFOLDER + "times.log", "w")
    start_time = time.time()
    print("Starting Process - Time Zero: {}".format(start_time), file=stormwarden)

    # mechanism to not load 50000 entries in one go but use chunks for it
    n = math.floor(int(req_rows) / req_chunk) + 1
    print("Solr Source is {}".format(URLS['solr']), file=stormwarden)
    print("Target Triplestore is {}".format(URLS['virtuoso-write']), file=stormwarden)
    print("Target Graph is {}".format(URLS['graph']), file=stormwarden)
    print("Detected {} chunks of a total of {} entries with a chunk size of {}".format(n, req_rows, req_chunk), file=stormwarden)
    print("Start Loading Remote chunks - {}".format(delta_now(start_time)), file=stormwarden)
    temp_url_param = copy.deepcopy(req_para)  # otherwise dicts get copied by reference
    print(("#" * n)[:0] + (" " * n)[:n], "{} / {}".format(0+1, n))
    for i in range(0, n):
        temp_url_param['start'] = i * req_chunk + head_start
        print("New Chunk started: [{}/{}] - {} ms".format(i, n - 1, delta_now(start_time)), file=stormwarden)
        if i + 1 != n:
            temp_url_param['rows'] = req_chunk
        else:
            temp_url_param['rows'] = int(int(req_rows) % req_chunk)
        print("\tUsing request URL: {}/{}".format(URLS['solr'], temp_url_param), file=stormwarden)
        data = test_json(load_remote_content(URLS['solr'], temp_url_param))
        if data:  # no else required, test_json already gives us an error if something fails
            print("Chunk finished, using SPCHT - {}".format(delta_now(start_time)), file=stormwarden)
            chunk_data = slice_header_json(data)
            big_data += chunk_data
            number = 0
            # test 1 - chunkwise data import
            inserts = []
            for entry in chunk_data:
                temp = convertMapping(entry, URLS['graph'])
                if temp:
                    number += len(temp)

                    inserts.append(bird_sparkle_insert(URLS['graph'], temp))
                    big_data.append(temp)
            total_nodes += number
            print("Pure Maping for current Chunk done, doing http sparql requests - {}".format(delta_now(start_time)),
                  file=stormwarden)
            for pnguin in inserts:
                sparqlQuery(pnguin, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])
            print("SPARQL Requests finished total of {} entries - {}".format(number, delta_now(start_time)),
                  file=stormwarden)
        print(("#" * n)[:i] + (" " * n)[:(n - i)], "{} / {}".format(i+1, n), "- {}".format(delta_now(start_time)))
    print("Overall Executiontime was {} seconds".format(delta_now(start_time, 3)), file=stormwarden)
    print("Total size of all entries is {}".format(sys.getsizeof(big_data)), file=stormwarden)
    print("There was a total of {} triples".format(total_nodes), file=stormwarden)
    stormwarden.close()


def delta_now(zero_time, rounding=2):
    return str(round(time.time()-zero_time, rounding))


if __name__ == "__main__":
    full_process()
