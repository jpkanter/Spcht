#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import argparse
import copy
import json
import math
import sys
import time

import pymarc

from local_tools import is_dictkey, is_dict, cprint_type, super_simple_progress_bar
from os import path
from virt_connect import sparqlQuery
from termcolor import colored, cprint
from legacy_tools import bird_sparkle_insert, bird_sparkle, bird_longhandle, fish_interpret
from solr_tools import marc2list, marc21_fixRecord, load_remote_content, test_json, slice_header_json
from SpchtDescriptorFormat import Spcht

ERROR_TXT = {}
URLS = {}
SETTINGS = {}
SPCHT = None  # SPECHT DESCRIPTOR FORMAT mapping
TESTFOLDER = "./testdata/"


def send_error(message, error_name=None):
    # custom error handling to use the texts provided by the settings
    global ERROR_TXT
    if error_name is None:
        sys.stderr.write(ERROR_TXT.get(message, message))
    else:
        if is_dictkey(ERROR_TXT, error_name):
            sys.stderr.write(ERROR_TXT[error_name].format(message))
        else:
            sys.stderr.write(message)


def load_config(file_path="config.json"):
    # loads json file with all the config settings, uses defaults when possible
    global ERROR_TXT, URLS, SETTINGS
    if not path.exists(file_path):
        return False
    with open(file_path) as json_file:
        data = json.load(json_file)
        try:
            ERROR_TXT = data['errors']
        except KeyError:
            send_error("Cannot find 'error' Listings in {} File".format(file_path))  # in this there is not error field
            ERROR_TXT = None
            return False
        try:
            URLS = data['urls']
        except KeyError:
            send_error("urls")
            URLS = None
            return False
        try:
            SETTINGS = data['settings']
        except KeyError:
            send_error("SETTINGS")
            SETTINGS = None
            return False
    return True


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
    heinz = Spcht("default.spcht.json", debug=True)
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
        jsoned_list = []
        thesparqlset = []
        for entry in thetestset:
            print(colored(debug_dict.get(entry.get('id')), "white", attrs=["bold"]))
            temp = heinz.processData(entry, URLS['graph'])
            if isinstance(temp, list):
                double_list.append(
                    "\n\n=== {} - {} ===\n".format(entry.get('id', "Unknown ID"), debug_dict.get(entry.get('id'))))
                jsoned_list += temp
                # TODO Workeable Sparql
                tmp_sparql_set = []
                for each in temp:
                    if each[3] == 0:
                        tmp_sparql = f"<{each[0]}> <{each[1]}> \"{each[2]}\" . \n"
                    else: # "<{}> <{}> <{}> .\n".format(graph + ressource, node['graph'], facet))
                        tmp_sparql = f"<{each[0]}> <{each[1]}> <{each[2]}> . \n"
                    double_list.append(f"{each[1]} - {each[2]} - [{each[3]}]")
                    tmp_sparql_set.append(tmp_sparql)
                thesparqlset.append(bird_sparkle_insert(URLS['graph'], tmp_sparql_set))
                del tmp_sparql_set

        with open(TESTFOLDER + "bridge_lines.txt", "w") as my_debug_output:
            for line in double_list:
                print(line, file=my_debug_output)

        # TODO: trying all 15 Testsets every time
        with open(TESTFOLDER + "bridge_jsondata.txt", "w") as myfile:
            json.dump(jsoned_list, myfile, indent=2)
        with open(TESTFOLDER + "bridge_turtle.ttl", "w") as myfile:
            myfile.write(Spcht.process2RDF(jsoned_list))

        with open(TESTFOLDER + "bridge_sparql.txt", "w") as myfile:
            for fracta in thesparqlset:
                # sparqlQuery(fracta, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])
                myfile.write(fracta)
                myfile.write("\n\r")


def marc21_display():
    # short test of things
    global URLS
    load_config()
    thetestset = load_from_json(TESTFOLDER + "thetestset.json")
    for entry in thetestset:
        if entry.get('fullrecord') is not None:
            clean_marc21 = Spcht.marc2list(entry.get('fullrecord'))
            spacers = {}
            mll = 40  # max line length
            for key, value in clean_marc21.items():
                if isinstance(value, dict):
                    position = 0
                    for subkey, subvalue in value.items():
                        if subkey == "concat":
                            continue
                        if spacers.get(position, 0) < len(str(subvalue)):
                            spacers[position] = len(str(subvalue)) + 1
                            if len(str(subvalue)) >= mll:
                                spacers[position] = mll
                        position += 1
            for key, value in clean_marc21.items():
                if isinstance(value, str):
                    print(colored((" "*4)[len(str(key)):] + str(key) + " ", "magenta"), colored(value, "cyan"), end="")
                if isinstance(value, dict):
                    print(colored((" "*4)[len(str(key)):] + str(key) + " ", "magenta"), end=" ")
                    position = 0
                    for subkey, subvalue in value.items():
                        if subkey == "concat":
                            continue
                        print(colored(subkey, "yellow"), end=" ")
                        print(colored(subvalue[:mll-3], "cyan") +
                              colored("..."[:(len(subvalue)-mll)], "blue") +
                              (" "*spacers.get(position, 0))[len(str(subvalue)):], end="║")
                        position += 1
                print("\n", end="")
        print("═"*200)


def full_process():
    global URLS, SPCHT
    load_config()
    habicht = Spcht("default.spcht.json")
    big_data = []
    total_nodes = 0

    req_rows = 5000
    req_chunk = 5000
    head_start = 0
    req_para = {'q': "*:*", 'rows': req_rows, 'wt': "json"}

    stormwarden = open(TESTFOLDER + "times.log", "w")
    start_time = time.time()
    print("Starting Process - Time Zero: {}".format(start_time), file=stormwarden)

    # mechanism to not load 50000 entries in one go but use chunks for it
    n = math.floor(int(req_rows) / req_chunk) + 1
    print(f"Solr Source is {URLS['solr']}", file=stormwarden)
    print(f"Target Triplestore is {URLS['virtuoso-write']}", file=stormwarden)
    print(f"Target Graph is {URLS['graph']}", file=stormwarden)
    print(f"Detected {n} chunks of a total of {req_rows} entries with a chunk size of {req_chunk}", file=stormwarden)
    print(f"Start Loading Remote chunks - {delta_now(start_time)}", file=stormwarden)
    temp_url_param = copy.deepcopy(req_para)  # otherwise dicts get copied by reference
    print(("#" * n)[:0] + (" " * n)[:n], f"{0+1} / {n}")
    for i in range(0, n):
        temp_url_param['start'] = i * req_chunk + head_start
        print(f"New Chunk started: [{i}/{n-1}] - {delta_now(start_time)} ms", file=stormwarden)
        if i + 1 != n:
            temp_url_param['rows'] = req_chunk
        else:
            temp_url_param['rows'] = int(int(req_rows) % req_chunk)
        print(f"\tUsing request URL: {URLS['solr']}/{temp_url_param}", file=stormwarden)
        data = test_json(load_remote_content(URLS['solr'], temp_url_param))
        if data:  # no else required, test_json already gives us an error if something fails
            print(f"Chunk finished, using SPCHT - {delta_now(start_time)}", file=stormwarden)
            chunk_data = slice_header_json(data)
            big_data += chunk_data
            number = 0
            # test 1 - chunkwise data import
            inserts = []
            for entry in chunk_data:
                temp = habicht.processData(entry, URLS['graph'])
                if temp:
                    number += len(temp)
                    inserts.append(Spcht.quickSparql(temp, URLS['graph']))  # just by coincidence this is the same in this example
                    big_data.append(temp)
            total_nodes += number
            print(f"Pure Maping for current Chunk done, doing http sparql requests - {delta_now(start_time)}",
                  file=stormwarden)
            incrementor = 0
            for pnguin in inserts:
                sparqlQuery(pnguin, URLS['virtuoso-write'], auth=URLS['sparql_user'], pwd=URLS['sparql_pw'])
                incrementor += 1
                super_simple_progress_bar(incrementor, len(inserts), "HTTP ", f"{incrementor} / {len(inserts)} [{number}]")
            print(f"\n{incrementor} Inserts done, {number} entries, commencing")
            print(f"SPARQL Requests finished total of {number} entries - {delta_now(start_time)}",
                  file=stormwarden)
        print(("#" * n)[:i] + (" " * n)[:(n - i)], f"{i+1} / {n}", f"- {delta_now(start_time)}")
    print(f"Overall Executiontime was {delta_now(start_time, 3)} seconds", file=stormwarden)
    print(f"Total size of all entries is {sys.getsizeof(big_data)}", file=stormwarden)
    print(f"There was a total of {total_nodes} triples", file=stormwarden)
    stormwarden.close()


def delta_now(zero_time, rounding=2):
    return str(round(time.time()-zero_time, rounding))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LOD SPCHT Interpreter", epilog="Config File overwrites individual settings")
    parser.add_argument('-configFile', type=str, help="Defines a (local) config file to load things from")
    parser.add_argument('-TestMode', action="store_true", help="Executes some 'random', flavour of the day testscript")
    parser.add_argument('-MarcView', action="store_true", help="Marc21 Display test")
    parser.add_argument('-FullTest', action="store_true", help="Progressing mappings with the config specified ressources")
    parser.add_argument('-CheckSpcht', type=str, help="Tries to load and validate the specified Spcht JSON File")
    parser.add_argument('-CompileSpcht', type=str, help="Loads a SPCHT File, validates and then compiles it to $file")
    args = parser.parse_args()
    print(args)
    # +++ CONFIG FILE +++
    if args.configFile:
        cfg_status = load_config(args.configFile)
    else:
        cfg_status = load_config() # if that fails everything gets set to None
    if not cfg_status:
        print("Config Loading failed, default Values will be None, proceed with caution")
        del cfg_status

    # +++ SPCHT Checker +++
    if args.CheckSpcht:
        Spcht.check_format(args.checkSpcht)

    # +++ SPCHT Compile
    if args.CompileSpcht:
        sperber = Spcht(args.CompileSpcht)
        sperber.export_full_descriptor(TESTFOLDER + "fll_spcht.json")

    # +++ Daily Debugging +++
    if args.TestMode:
        spcht_object_test()
    if args.MarcView:
        marc21_display()
    if args.FullTest:
        full_process()
    # TODO Insert Arg Interpretation here
    #
    # main_test()

