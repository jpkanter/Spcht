#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import argparse
import copy
import json
import math
import sys
import time
import SpchtDescriptorFormat

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




def spcht_object_test():
    global URLS
    load_config()
    heinz = SpchtDescriptorFormat.Spcht("default.spcht.json", debug=True)
    if heinz.descri_status():
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
        thetestset = load_from_json(TESTFOLDER + "thetestset.json")
        double_list = []
        thesparqlset = []
        for entry in thetestset:
            temp = heinz.convertMapping(entry, URLS['graph'])
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
    parser = argparse.ArgumentParser(description="LOD SPCHT Interpreter", epilog="Config File overwrites individual settings")
    parser.add_argument('-configFile', type=str, help="Defines a (local) config file to load things from")
    parser.add_argument('-TestMode', action="store_true", help="Executes some 'random', flavour of the day testscript")
    args = parser.parse_args()
    # TODO Insert Arg Interpretation here
    spcht_object_test()
    # main_test()

