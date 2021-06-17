#!/usr/bin/env python
# coding: utf-8

# Copyright 2021 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of some open source application.
#
# Some open source application is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# Some open source application is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import argparse
import copy
import errno
import json
import math
import sys
import time
import logging
import os
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

import SpchtErrors
import local_tools
from local_tools import super_simple_progress_bar, sleepy_bar, super_simple_progress_bar_clear, \
    load_remote_content, slice_header_json, sparqlQuery, block_sparkle_insert, solr_handle_return, delta_now, test_json, \
    delta_time_human, load_from_json
from os import path
from termcolor import colored
from SpchtDescriptorFormat import Spcht

ERROR_TXT = {}
PARA = {}
SETTINGS = {}
TESTFOLDER = "./testdata/"

logging.basicConfig(filename='spcht_process.log', format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.INFO)
# logging.basicConfig(filename='spcht_process.log', format='[%(asctime)s] %(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)  # Python 3.9


def send_error(message, error_name=None):
    # custom error handling to use the texts provided by the settings
    global ERROR_TXT
    if error_name is None:
        sys.stderr.write(ERROR_TXT.get(message, message))
    else:
        if Spcht.is_dictkey(ERROR_TXT, error_name):
            sys.stderr.write(ERROR_TXT[error_name].format(message))
        else:
            sys.stderr.write(message)


def load_config(file_path="config.json"):
    """
    Simple config file loader, will raise exceptions if files arent around, will input parameters
    in global var PARA
    :param file_path str: file path to a flat json containing a dictionary with key-value relations
    :return: True if everything went well, will raise exception otherwise
    """
    expected_settings = ["solr_addr", "query", "total_rows", "chunk_size", "spcht_path", "save_folder",
                         "graph", "named_graph", "isql_path", "user", "password", "isql_port", "virt_folder",
                         "processes"]
    config_dict = load_from_json(file_path)
    if not config_dict:
        raise SpchtErrors.OperationalError("Cannot load config file")
    for setting_name in config_dict:
        if setting_name in expected_settings and expected_settings[setting_name] != "":
            PARA[setting_name] = expected_settings[setting_name]
    return True


def spcht_object_test():
    global PARA
    heinz = Spcht(PARA['spcht'], debug=True)
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
        thetestset = load_from_json(TESTFOLDER + PARA['TestMode'])
        double_list = []
        jsoned_list = []
        thesparqlset = []
        for entry in thetestset:
            if Spcht.is_dictkey(PARA, 'isolate'):
                if PARA['isolate'] != entry.get('id'):
                    continue
            print(colored(debug_dict.get(entry.get('id')), "white", attrs=["bold"]))
            temp = heinz.processData(entry, PARA['graph'])
            if isinstance(temp, list):
                double_list.append("\n\n=== {} - {} ===\n".format(entry.get('id', "Unknown ID"), debug_dict.get(entry.get('id'))))
                jsoned_list += temp
                # TODO Workeable Sparql
                tmp_sparql_set = []
                for each in temp:
                    if each[3] == 0:
                        tmp_sparql = f"<{each[0]}> <{each[1]}> \"{each[2]}\" . \n"
                    else:  # "<{}> <{}> <{}> .\n".format(graph + ressource, node['graph'], facet))
                        tmp_sparql = f"<{each[0]}> <{each[1]}> <{each[2]}> . \n"
                    double_list.append(f"{each[1]} - {each[2]} - [{each[3]}]")
                    tmp_sparql_set.append(tmp_sparql)
                thesparqlset.append(block_sparkle_insert(PARA['graph'], tmp_sparql_set))
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
    global PARA
    thetestset = load_from_json(TESTFOLDER + PARA['MarcView'])
    for entry in thetestset:
        if entry.get('fullrecord') is not None:
            clean_marc21 = Spcht.marc2list(entry.get('fullrecord'))
            spacers = {}
            mll = 40  # max line length
            for key, value in clean_marc21.items():
                if isinstance(value, dict):
                    value = [value]  # there was different code here before and this saves boilerplate space
                if isinstance(value, list):
                    for each in value:
                        if isinstance(each, dict):
                            position = 0
                            for subkey, subvalue in each.items():
                                if not isinstance(subvalue, list):
                                    subvalue = [subvalue]
                                for every in subvalue:
                                    if spacers.get(position, 0) < len(str(every)):
                                        spacers[position] = len(str(every)) + 1
                                        if len(str(every)) >= mll:
                                            spacers[position] = mll
                                    position += 1
            for key, value in clean_marc21.items():
                if isinstance(value, str):
                    print(colored((" " * 4)[len(str(key)):] + str(key) + " ", "magenta"), colored(value, "cyan"),
                          end="")
                if isinstance(value, dict):
                    value = [value]
                if isinstance(value, list):
                    for each in value:
                        print(colored((" " * 4)[len(str(key)):] + str(key) + " ", "magenta"), end=" ")
                        position = 0
                        for subkey, subvalue in each.items():
                            if not isinstance(subvalue, list):
                                subvalue = [subvalue]
                            for every in subvalue:
                                print(colored(subkey, "yellow"), end=" ")
                                print(colored(every[:mll - 3], "cyan") +
                                      colored("..."[:(len(every) - mll)], "blue") +
                                      (" " * spacers.get(position, 0))[len(str(every)):], end="║")
                                position += 1
                        print("\n", end="")
        print("═" * 200)


def marc21_test():
    global PARA
    mydata = load_from_json(TESTFOLDER + PARA['MarcTest'])
    if mydata:
        testdata = Spcht.marc2list(mydata[0].get('fullrecord'))


def used_field_test():
    load_config()
    rolf = Spcht("default.spcht.json", debug=True)
    print(rolf.get_node_fields())


def update_data(solr, graph, spcht, sparql, sparql_user, sparql_pw,
                max_age, log=None, rows=100000, chunk=10000, query="*:*", dryrun=False):
    # 1. query solr for new entries
    # 2. use spcht to build new entries to be inserted later on
    # 3. sparql select with the ids for everything we need to update
    # 4. sparql delete everything that gets replaced
    # 5. do the usual full process
    # http://index.ub.uni-leipzig.de/solr/biblio/select?q=source_id%3A0+last_indexed%3A%5B2020-08-12T17%3A33%3A18.772Z+TO+*%5D&wt=json&indent=true
    greif = Spcht(spcht)
    flock = []
    past_time = datetime.now() - timedelta(minutes=max_age)
    searchtime = "last_indexed:[" + past_time.strftime("%Y-%m-%dT%H:%M:%SZ") + " TO *]"
    logging.info("Started new Update Spcht instance, Spcht name is 'greif'")
    query = f"{query} {searchtime}"
    logging.info(f"Update Spcht Query is: '{query}'")
    req_para = {'q': query, 'rows': rows, 'wt': "json", "cursorMark": "*", "sort": "id asc"}
    fieldlist = greif.get_node_fields()
    req_para['fl'] = ""
    for each in fieldlist:
        req_para['fl'] += f"{each} "
    req_para['fl'] = req_para['fl'][:-1]
    logging.debug(f"Fieldlist filter: '{req_para}'")
    time0 = time.time()
    iterator = 0
    n = math.floor(int(rows) / int(chunk)) + 1
    logging.info(f"Internal Time (should be equal to log time) {time.strftime('%d %b %Y %H:%M:%S', time.localtime(time0))} - {time0}")
    logging.info(
        f"The time difference to NOW() is {delta_time_human(minutes=max_age)}, which amounts for the oldest entry to be from {past_time.strftime('%d.%m.%Y %H:%M:%S')}")
    logging.info(f"Starting update process, SOLR is {solr}")
    logging.info(f"Detected {n} chunks of a total of {rows} entries with a chunk size of {chunk}")
    for i in range(0, n):
        logging.debug(f"{delta_now(time0)}\tStarting a new cycle, this is #{iterator + 1}")
        iterator += 1
        if i + 1 != n:
            req_para['rows'] = chunk
        else:
            req_para['rows'] = int(int(rows) % chunk)
        if int(req_para['rows']) == 0:
            continue
        try:
            pureData = load_remote_content(solr, req_para, mode="POST")
            current_dateset = test_json(pureData)
        except Exception as generic:
            logging.critical(f"Couldnt properly Handle remote content in first try- {generic}")
            logging.info("Trying to load data again after 15 seconds")
            time.sleep(15)
            try:
                pureData = load_remote_content(solr, req_para, mode="POST")
                current_dateset = test_json(pureData)
            except Exception as even_more_generic:
                logging.critical(f"Second blind remote load try failed - {even_more_generic}")
                logging.critical(f"Aborted update process in cycle {iterator + 1} / {n}, {delta_now(time0)}ms after start")
                break

        if current_dateset:
            try:
                logging.debug(f"{delta_now(time0)}\tDownload done, subcycle begins, Cursor:  {req_para['cursorMark']}")
                chunk_data = slice_header_json(current_dateset)
                for entry in chunk_data:
                    temp = greif.processData(entry, graph)
                    if temp:  # successful spcht interpretation
                        flock.append(temp)
            except KeyError:
                logging.critical(f"KeyError, ", current_dateset)
                return False
            logging.debug(f"{delta_now(time0)}\tCycle ended")

            if current_dateset.get("nextCursorMark", "*") != "*" and current_dateset['nextCursorMark'] != req_para[
                'cursorMark']:
                req_para['cursorMark'] = current_dateset['nextCursorMark']
            else:
                logging.critical(
                    f"{delta_now(time0)}\tNo further CursorMark was received, therefore there are less results than expected rows. Aborting cycles")
                break
    logging.info(f"{delta_now(time0)}\tDownload & SPCHT finished, commencing updates")
    logging.info(f"There are {len(flock)} updated entries since {past_time.strftime('%d.%m.%Y %H:%M:%S')}")

    if len(flock) > 0:
        counter = 0
        if not dryrun:
            len_of_flock = len(flock)
            logging.info(f"{delta_now(time0)}\tDeleting all {len_of_flock} entries that are about to be replaced")
            for each in flock:
                super_simple_progress_bar(counter, len_of_flock, "DEL ", f"{counter} / {len_of_flock}")
                sparqlQuery(f"WITH <{graph}> DELETE {{ <{each[0][0]}> ?p ?o }} WHERE {{ <{each[0][0]}> ?p ?o }}",
                            sparql, auth=sparql_user, pwd=sparql_pw)
                logging.debug(f"WITH <{graph}> DELETE {{ <{each[0][0]}> ?p ?o }} WHERE {{ <{each[0][0]}> ?p ?o }}")
                counter += 1
            super_simple_progress_bar_clear()
            logging.info(f"{delta_now(time0)}\tDeleting of entries complete, reinserting new data")
            counter = 0
            for each in flock:
                super_simple_progress_bar(counter, len_of_flock, "INS ", f"{counter} / {len_of_flock}")
                sparqlQuery(Spcht.quickSparql(each, graph), sparql, auth=sparql_user, pwd=sparql_pw)
                counter += 1
            super_simple_progress_bar_clear()
        else:
            logging.info(f"{delta_now(time0)}\tDry run - nothing happens")
    else:
        logging.info("The set is empty, therefore no further processing is been done")
    logging.info(f"{delta_now(time0)}\tProcess finished")


if __name__ == "__main__":
    arguments = {
        "CreateOrder":
            {
                "type": str,
                "help": "Creates a blank order without executing it",
                "metavar": ("order_name", "fetch_method", "processing_type", "insert_method"),
                "nargs": 4,
            },
        "CreateOrderPara":
            {
                "action": "store_true",
                "help": "Creates a blank order with executing it with provided variables: --order_name, --fetch, --process and --insert",
            },
        "order_name":
            {
                "type": str,
                "help": "name for a new order",
            },
        "fetch":
            {
                "type": str,
                "help": "Type of fetch mechanismn for data: 'solr' or 'file'"
            },
        "process":
            {
                "type": str,
                "help": "Processing type, either 'insert' or 'update'"
            },
        "insert":
            {
                "type": str,
                "help": "method of inserting into triplestore: 'isql', 'obdc' or 'sparql'",
            },
        "FetchSolrOrder":
            {
                "type": str,
                "help": "Executes a fetch order provided, if the work order file has that current status",
                "metavar": ("work_file", "solr_url", "query", "total_rows", "chunk_size", "spcht_descriptor", "save_folder"),
                "nargs": 7,
            },
        "FetchSolrOrderPara":
            {
                "action": "store_true",
                "help": "Executes a solr fetch work order, needs parameters --work_order_file, --solr_url, --query, --query_rows, --chunk_size, --spcht_descriptor, --save_folder",
            },
        "work_order_file":
            {
                "type": str,
                "help": "Path to work order file",
            },
        "solr_url":
            {
                "type": str,
                "help": "Url to a solr query endpoint"
            },
        "query":
            {
                "type": str,
                "help": "Query for solr ('*' fetches everything)",
                "default": "*",
            },
        "query_rows":
            {
                "type": int,
                "help": "Number of rows that are fetched in total from an external datasource",
                "default": 25000,
            },
        "chunk_size":
            {
                "type": int,
                "help": "Size of a single chunk, determines the number of queries",
                "default": 5000,
            },
        "spcht_descriptor":
            {
                "type": str,
                "help": "Path to a spcht descriptor file, usually ends with '.spcht.json'"
            },
        "save_folder":
            {
                "type": str,
                "help": "The folder were downloaded data is to be saved, will be referenced in work order",
                "default": "./"
            },
        "SpchtProcessing":
            {
                "type": str,
                "help": "Processes the provided work order file",
                "metavar": ("work_file", "graph/subject", "spcht_descriptor"),
                "nargs": 3
            },
        "SpchtProcessingMulti":
            {
                "type": str,
                "help": "Processes the provided work order file in multiple threads",
                "metavar": ("work_file", "graph/subject", "spcht_descriptor", "processes"),
                "nargs": 4,
            },
        "SpchtProcessingPara":
            {
                "action": "store_true",
                "help": "Processes the given work_order file with parameters, needs: --work_order_file, --graph, --spcht_descriptor",
            },
        "SpchtProcessingMultiPara":
            {
                "action": "store_true",
                "help": "Procesesses the given order with multiple processes, needs: --work_order_file, --graph, --spcht_descriptor, --processes",
            },
        "graph":
            {
                "type": str,
                "help": "URI of the subject part the graph gets mapped to in the <subject> <predicate> <object> triple",
            },
        "processes":
            {
                "type": int,
                "help": "Number of parallel processes used, should be <= cpu_count",
                "default": 4,
            },
        "InsertISQLOrder":
            {
                "type": str,
                "help": "Inserts the given work order via the isql interface of virtuoso, copies files in a temporary folder where virtuoso has access, needs credentials",
                "metavar": ("work_file", "isql_path", "user", "password", "named_graph", "virt_folder"),
                "nargs": 6,
            },
        "InsertISQLOrderPara":
            {
                "action": "store_true",
                "help": "Inserts the given order via the isql interace of virtuoso, copies files in a temporary folder, needs paramters: --isql_path, --user, --password, --named_graph, --virt_folder",
            },
        "HandleWorkOrderPara":
            {
                "action": "store_true",
                "help": "Takes any one work order and processes it to the next step, needs all parameters the corresponding steps need",
            },
        "CheckWorkOrder":
            {
                "type": str,
                "help": "Checks the status of any given work order and displays it in the console"
            },
        "config":
            {
                "type": str,
                "help": "loads the defined config file, must be a json file containing a flat dictionary",
                "metavar": ("path/to/config.json"),
                "short": "-c",
            },
        "UpdateData":
            {
                "help": "Special form of full process, fetches data with a filter, deletes old data and inserts new ones",
                "action": "store_true",
            },
    }

    logging.debug("Start of script")
    parser = argparse.ArgumentParser(
        description="solr2virtuoso bridge",
        usage="Main functions: MarcView, SolrSpy, SolrStats, CheckSpcht, CheckFields, CompileSpcht, UpdateData and ProcessData. Each function needs the appropriated amount of commands to work properly",
        epilog="Individual settings overwrite settings from the config file",
        prefix_chars="-")
    # ? in case we want to load arguments from a json
    parser.register('type', 'float', float)
    parser.register('type', 'int', int)
    parser.register('type', 'str', str)
    for key, item in arguments.items():
        if "short" in item:
            short = item["short"]
            del arguments[key]["short"]
            parser.add_argument(f'--{key}', short, **item)
        else:
            parser.add_argument(f'--{key}', **item)

    parser.add_argument('--MarcView', '-mv', type=str,
                        help="Loads the specified json file and displays the mark content", metavar="MARCFILE")
    parser.add_argument('--MarcTest', '-mt', type=str,
                        help="Loads the specified json file does a throughtest", metavar="MARCFILE")
    parser.add_argument('--SolrStat', '-st', action="store_true", help="Creates statitistics regarding the Solr Fields")
    parser.add_argument('--CheckSpcht', '-cs', action="store_true",
                        help="Tries to load and validate the specified Spcht JSON File")
    parser.add_argument('--CheckFields', '-cf', action="store_true",
                        help="Loads a spcht file and displays all dictionary keys used in that descriptor")
    parser.add_argument('--CompileSpcht', '-ct', action="store_true",
                        help="Loads a SPCHT File, validates and then compiles it to $file")
    parser.add_argument('--spcht', '-S', type=str, help="The spcht descriptor file for the mapping", metavar="FILEPATH")
    parser.add_argument('--log', '-l', type=str, help="Name of the logfile", metavar="FILEPATH")
    parser.add_argument('--outfile', '-o', type=str, help="file where results will be saved", metavar="FILEPATH")
    parser.add_argument('--solr', '-s', type=str, help="URL auf the /select/ interface of a Apache solr", metavar="URL")
    parser.add_argument('--filter', '-f', type=str, help="Query Filter for q: ???", metavar="STRING")
    parser.add_argument('--sparql', '-sa', type=str, help="URL of the sparql Interface of a virtuoso",
                        metavar="URL")
    parser.add_argument('--sparql_user', '-su', type=str, help="Username for the sparql authentification",
                        metavar="NAME")
    parser.add_argument('--sparql_pw', '-sp', type=str, help="Password for the sparql authentification",
                        metavar="PASSWORD")
    parser.add_argument('--part', '-p', type=int, help="Size of one chunk/part when loading data from solr",
                        metavar="number")
    parser.add_argument('--rows', '-r', type=int, help="Total Numbers of rows requested for the Operation",
                        metavar="number")
    parser.add_argument('--time', '-t', type=int, help="Time in Minutes", metavar="number")
    parser.add_argument('--isolate', '-i', type=str, help="DEBUG: Isolates the test set to one ID", metavar="number")

    parser.add_argument('--urls', '-u', action="store_true",
                        help="Lists all urls the procedure knows after loading data")
    parser.add_argument('--TestMode', type=str, help="Executes some 'random', flavour of the day testscript")
    parser.add_argument('--FullTest', action="store_true",
                        help="Progressing mappings with the config specified ressources")

    args = parser.parse_args()
    # +++ CONFIG FILE +++
    if args.config:
        cfg_status = load_config(args.config)

    boring_parameters = ["spcht", "log", "outfile", "solr", "sparql", "sparql_user", "sparql_pw", "graph", "part",
                         "rows", "filter", "time", "isolate", "MarcTest", "MarcView", "TestMode", "logging"]

    for arg in vars(args):
        if arg in boring_parameters and getattr(args, arg) is not None:
            if arg == "logging":
                logging.getLogger().setLevel(getattr(args, arg))
            else:
                PARA[arg] = getattr(args, arg)
    if Spcht.is_dictkey(PARA, 'log'):  # replacing part of the string with a datetime:
        time_string = datetime.now().strftime('%Y%m%d-%H%M%S')
        PARA['log'] = PARA['log'].replace("$time", time_string)

    if args.CreateOrder:
        par = args.CreateOrder
        order_name = local_tools.CreateWorkOrder(par[0], par[1], par[2], par[3])
        print(f"Created Order '{order_name}'")

    if args.FetchSolrOrder:
        par = args.FetchSolrOrder
        ara = Spcht(par[5])
        local_tools.FetchWorkOrderSolr(par[0], par[1], par[2], int(par[3]), int(par[4]), ara, par[5])

    if args.CheckWorkOrder:
        local_tools.CheckWorkOrder(args.CheckWorkOrder)

    if args.urls:
        print("URL Entries from Config and Parameters")
        for key in PARA:
            print(f"\t{key}\t{PARA[key]}")
    # ! UpdateProcess - in parts a copy of full process
    if args.UpdateData:
        if not Spcht.is_dictkey(PARA, 'solr', 'graph', 'spcht', 'sparql', 'sparql_user', 'sparql_pw', 'time'):
            print("Some Mandatory Parameters are missing")
            exit(0)
        update_data(PARA['solr'], PARA['graph'], PARA['spcht'], PARA['sparql'], PARA.get('sparql_user'),
                    PARA.get('sparql_pw'), PARA['time'], PARA.get('log'), PARA['rows'], PARA['parts'], PARA['query'])
    # +++ SPCHT Checker +++
    if args.CheckSpcht:
        if not Spcht.is_dictkey(PARA, 'spcht'):
            print("Need to specifcy spcht descriptor file with --spcht <file>")
            exit(1)
        print(f"Loading file {args.spcht}")
        try:
            with open(args.spcht, "r") as file:
                testdict = json.load(file)
        except json.decoder.JSONDecodeError as e:
            print(f"JSON Error: {str(e)}", file=sys.stderr)
            exit(2)
        except FileNotFoundError as e:
            print(f"File not Found: {str(e)}", file=sys.stderr)
            exit(1)
        taube = Spcht()
        if taube.load_descriptor_file(args.spcht):
            print("Spcht Discriptor could be succesfully loaded, everything should be okay")
            exit(0)
        else:
            print("There was an Error loading the Spcht Descriptor")
        #jsoned_spcht = load_from_json(args.CheckSpcht)
        #Spcht.check_format(jsoned_spcht)

    # +++ SPCHT Compile
    if args.CompileSpcht:
        sperber = Spcht(args.CompileSpcht, debug=True)
        sperber.export_full_descriptor(TESTFOLDER + "fll_spcht.json")
        print(colored("Succesfully compiled spcht, file:", "cyan"), colored(TESTFOLDER + "fll_spcht.json", "blue"))

    # +++ Daily Debugging +++
    if args.TestMode:
        spcht_object_test()
    if args.MarcView:
        marc21_display()
    if args.MarcTest:
        marc21_test()
    if args.CheckFields:
        used_field_test()
    # TODO Insert Arg Interpretation here
    #
    # main_test()
