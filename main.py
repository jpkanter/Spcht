#!/usr/bin/env python
#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import argparse
import copy
import json
import math
import sys
import time
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from local_tools import super_simple_progress_bar, sleepy_bar, super_simple_progress_bar_clear, \
    load_remote_content, slice_header_json, sparqlQuery, block_sparkle_insert
from os import path
from termcolor import colored
from SpchtDescriptorFormat import Spcht

ERROR_TXT = {}
PARA = {}
SETTINGS = {}
TESTFOLDER = "./testdata/"


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


def test_json(json_str):
    #  i am almost sure that there is already a build in function that does something very similar, embarrassing
    try:
        data = json.loads(json_str)
        return data
    except ValueError:
        send_error("json")
        return False


def load_config(file_path="config.json"):
    # loads json file with all the config settings, uses defaults when possible
    global ERROR_TXT, PARA, SETTINGS
    if not path.exists(file_path):
        return False
    with open(file_path) as json_file:
        data = json.load(json_file)
        try:
            ERROR_TXT = data.get('errors')
        except KeyError:
            send_error("Cannot find 'error' Listings in {} File".format(file_path))  # in this there is not error field
            ERROR_TXT = None
            return False
        try:
            PARA = data['para']
        except KeyError:
            send_error("urls")
            PARA = None
            return False
        try:
            SETTINGS = data.get('settings')
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
    except Exception as error:
        send_error("graph_parser "+str(error))
    return False


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
                    print(colored((" "*4)[len(str(key)):] + str(key) + " ", "magenta"), colored(value, "cyan"), end="")
                if isinstance(value, dict):
                    value = [value]
                if isinstance(value, list):
                    for each in value:
                        print(colored((" "*4)[len(str(key)):] + str(key) + " ", "magenta"), end=" ")
                        position = 0
                        for subkey, subvalue in each.items():
                            if not isinstance(subvalue, list):
                                subvalue = [subvalue]
                            for every in subvalue:
                                print(colored(subkey, "yellow"), end=" ")
                                print(colored(every[:mll-3], "cyan") +
                                      colored("..."[:(len(every)-mll)], "blue") +
                                      (" "*spacers.get(position, 0))[len(str(every)):], end="║")
                                position += 1
                        print("\n", end="")
        print("═"*200)


def marc21_test():
    global PARA
    mydata = load_from_json(TESTFOLDER + PARA['MarcTest'])
    testdata = Spcht.marc2list(mydata[0].get('fullrecord'))


def full_process(solr, graph, spcht, sparql, sparql_user="", sparql_pw="", log=False, req_rows=50000, req_chunk=10000, query=""):
    load_config()
    habicht = Spcht(spcht)
    big_data = []
    total_nodes = 0
    #"source_id:0+institution:DE-15"
    req_para = {'q': query, 'rows': req_rows, 'wt': "json", "cursorMark": "*", "sort": "id asc"}
    # optimising requests a bit and pre filter for the stuff we need
    fieldlist = habicht.get_node_fields()
    req_para['fl'] = ""
    for each in fieldlist:
        req_para['fl'] += f"{each} "
    req_para['fl'] = req_para['fl'][:-1]
    if log:
        try:
            stormwarden = open(log, "w")
        except FileNotFoundError:
            stormwarden = sys.stdout
    else:
        stormwarden = sys.stdout
    start_time = time.time()
    print("Starting Process - Time Zero: {}".format(start_time), file=stormwarden)

    # mechanism to not load 50000 entries in one go but use chunks for it
    n = math.floor(int(req_rows) / int(req_chunk) ) + 1
    print(f"Solr Source is {solr}", file=stormwarden)
    print(f"Target Triplestore is {sparql}", file=stormwarden)
    print(f"Target Graph is {graph}", file=stormwarden)
    print(f"Detected {n} chunks of a total of {req_rows} entries with a chunk size of {req_chunk}", file=stormwarden)
    print(f"Start Loading Remote chunks - {delta_now(start_time)}", file=stormwarden)
    print(("#" * n)[:0] + (" " * n)[:n], f"{0+1} / {n}")
    for i in range(0, n):
        print(f"New Chunk started: [{i+1}/{n-1}] - {delta_now(start_time)} ms", file=stormwarden)
        if i + 1 != n:
            req_para['rows'] = req_chunk
        else:
            req_para['rows'] = int(int(req_rows) % int(req_chunk))
        print(f"\tUsing request URL: {solr}/{req_para}", file=stormwarden)
        data = test_json(load_remote_content(solr, req_para))
        if data:  # no else required, test_json already gives us an error if something fails
            print(f"Chunk finished, using SPCHT - {delta_now(start_time)}", file=stormwarden)
            chunk_data = slice_header_json(data)
            big_data += chunk_data
            number = 0
            # test 1 - chunkwise data import
            inserts = []
            for entry in chunk_data:
                temp = habicht.processData(entry, graph)
                if temp:
                    number += len(temp)
                    inserts.append(Spcht.quickSparql(temp, graph))  # just by coincidence this is the same in this example
                    big_data.append(temp)
            total_nodes += number
            print(f"Pure Maping for current Chunk done, doing http sparql requests - {delta_now(start_time)}",
                  file=stormwarden)
            incrementor = 0
            for pnguin in inserts:
                sparqlQuery(pnguin, sparql, auth=sparql_user, pwd=sparql_pw)
                incrementor += 1
                super_simple_progress_bar(incrementor, len(inserts), "HTTP ", f"{incrementor} / {len(inserts)} [{number}]")
            print(f"\n{incrementor} Inserts done, {number} entries, commencing")
            print(f"SPARQL Requests finished total of {number} entries - {delta_now(start_time)}",
                  file=stormwarden)
        print(("#" * n)[:i] + (" " * n)[:(n - i)], f"{i+1} / {n}", f"- {delta_now(start_time)}")

        if data.get("nextCursorMark", "*") != "*" and data['nextCursorMark'] != req_para['cursorMark']:
            req_para['cursorMark'] = data['nextCursorMark']
        else:
            printing(
                f"{delta_now(start_time)}\tNo further CursorMark was received, therefore there are less results than expected rows. Aborting cycles",
                file=stormwarden)
            break
    print(f"Overall Executiontime was {delta_now(start_time, 3)} seconds", file=stormwarden)
    print(f"Total size of all entries is {sys.getsizeof(big_data)}", file=stormwarden)
    print(f"There was a total of {total_nodes} triples", file=stormwarden)
    stormwarden.close()


def downloadTest(req_rows=100, req_chunk=120, wait_time=0, wait_incrementor=0):
    global PARA, SPCHT
    load_config()
    total_nodes = 0
    head_start = 0
    req_para = {'q': "*:*", 'rows': req_rows, 'wt': "json", "cursorMark": "*", "sort": "id asc", "fl": "source_id:0"}
    temp_url_param = copy.deepcopy(req_para)
    n = math.floor(int(req_rows) / req_chunk) + 1

    start_time = time.time()
    now = datetime.now()
    try:
        time_string = now.strftime('%d%m%Y-%H%M-%S')
        stormwarden = open(TESTFOLDER + f"downloads-{time_string}.log", "w")
    except Exception as e:
        print("Random exception", e)
        return False

    printing(f"API Source is {PARA['solr3']}", file=stormwarden)
    printing(f"Initial wait time is {wait_time} with a cycling increment of {wait_incrementor}", file=stormwarden)
    printing(f"Detected {n} chunks of a total of {req_rows} entries with a chunk size of {req_chunk}", file=stormwarden)
    printing(f"Start Loading Remote chunks - {delta_now(start_time)}", file=stormwarden)
    cursorMark = "*"
    for i in range(0, n):

        temp_url_param['cursorMark'] = cursorMark
        if i + 1 != n:
            temp_url_param['rows'] = req_chunk
        else:
            temp_url_param['rows'] = int(int(req_rows) % req_chunk)
        if int(temp_url_param['rows']) == 0:
            continue
        printing(f"New Chunk started: [{i + 1}/{n}] - {delta_now(start_time)} ms", file=stormwarden)
        printing(f"\tDownload at {delta_now(start_time)}", PARA['solr3'], temp_url_param, file=stormwarden)
        pureData = load_remote_content(PARA['solr3'], temp_url_param)
        if test_json(pureData):
            big_data = test_json(pureData)
            with open(TESTFOLDER + f"downloads-{time_string}-{i}.json", "w") as quickfile:
                json.dump(big_data, quickfile, indent=2)
            cursorMark = big_data['nextCursorMark']
            printing(f"Download of Chunk is good json, next Cursor: {cursorMark}", file=stormwarden)
        else:
            printing(pureData, file=stormwarden)
        printing(f"Chunk {i+1} finished, current time: {delta_now(start_time)}", file=stormwarden)
        printing(f"Sleeping now for {wait_time} seconds", file=stormwarden)
        sleepy_bar(wait_time)
        wait_time += wait_incrementor
    stormwarden.close()


def used_field_test():
    load_config()
    rolf = Spcht("default.spcht.json", debug=True)
    print(rolf.get_node_fields())


def solr_spy(req_url="", req_rows=100000, wait_time=0.0, mode=0):
    # mode 0 - light mode
    # mode 1 - heavy mode
    # ? REGEX ^.*[-][a-zA-Z0-9]{9}$    Not needed
    global PARA
    req_para = {'q': "*:*", 'rows': req_rows, 'wt': "json", "cursorMark": "*", "sort": "id asc", "fl": "id, source_id"}
    castle_going = True  # i wrote KeepGoing before, twisted mind and here we are

    list_of_known_abb = {}
    iterator = 0
    start_time = time.time()
    now = datetime.now()

    try:
        time_string = now.strftime('%d%m%Y-%H%M-%S')
        stormwarden = open(TESTFOLDER + f"SolrSpy-{time_string}.log", "w")
    except Exception as e:
        print("Random exception", e)
        return False

    printing(f"API Source is {req_url}", file=stormwarden)
    printing(f"Retrieving all entries, this might take a while, chunk size is {req_rows}", file=stormwarden)
    while castle_going:
        printing(f"{delta_now(start_time)}\tStarting a new cycle, this is #{iterator+1}", file=stormwarden)
        # various fluff stuff
        stat = {'new': 0, 'add': 0}
        iterator += 1
        # actual logic
        castle_going = False  # precaution
        pureData = load_remote_content(req_url, req_para, mode="POST")
        current_dateset = test_json(pureData)
        if current_dateset:
            if current_dateset.get("nextCursorMark", "*") != "*" and current_dateset['nextCursorMark'] != req_para['cursorMark']:
                castle_going = True
                req_para['cursorMark'] = current_dateset['nextCursorMark']
            try:
                printing(f"{delta_now(start_time)}\tDownload done, subcycle begins, Cursor:  {req_para['cursorMark']}", file=stormwarden)
                for each in current_dateset['response']['docs']:
                    id_key = each.get('source_id')
                    if Spcht.is_dictkey(list_of_known_abb, id_key):
                        list_of_known_abb[id_key]['count'] += 1
                        stat['add'] += 1
                    else:
                        list_of_known_abb[id_key] = {}
                        list_of_known_abb[id_key]['xmpl'] = each['id']
                        list_of_known_abb[id_key]['count'] = 1
                        printing(f"{delta_now(start_time)}\tNew key found: {id_key}", file=stormwarden)
                        stat['new'] += 1
            except KeyError:
                printing(f"KeyError, ", current_dateset, file=stormwarden)
                return False
        printing(f"{delta_now(start_time)}\tCycle ended. Stats: Added: {stat['add']}, Newfound: {stat['new']}", file=stormwarden)

        if mode == 0:  # light mode with iterating filter
            req_para['q'] = ""
            for each in list_of_known_abb.keys():
                if req_para['q'] != "":
                    req_para['q'] += " AND "
                req_para['q'] += "!source_id:" + each
            printing(f"{delta_now(start_time)}\tNew Query {req_para['q']}", file=stormwarden)
            req_para['cursorMark'] = "*"  # resets cursor Mark then

        if iterator > 500:
            castle_going = False
            printing(f"{delta_now(start_time)}\tHALT Condition triggered, curios", file=stormwarden)
        sleepy_bar(wait_time)

    printing(f"{delta_now(start_time)}\tProcess finished, {len(list_of_known_abb)} elements found", file=stormwarden)
    # json.dump(list_of_known_abb, stormwarden, indent=2)
    for each in list_of_known_abb.keys():
        printing(f"{each}\t{list_of_known_abb[each]['count']}\t{list_of_known_abb[each]['xmpl']}", file=stormwarden)

    stormwarden.close()


def printing(*args, **kwargs):
    """
        function that double print things, to be meant to be used with a set file=
        :param object args: stringeable objects that will be printed
        :param any kwargs: anything, the parameter "file" will be replaced in the second printing with std.out
        :return: Nothing, but prints to std.out AND a file
        :rtype: None:
    """
    if Spcht.is_dictkey(kwargs, "file") and kwargs['file'] != sys.stdout:
        print(*args, **kwargs)
        del kwargs['file']
        print(*args, **kwargs)
    else:
        print(*args, **kwargs)


def delta_now(zero_time, rounding=2):
    return str(round(time.time()-zero_time, rounding))


def delta_time_human(**kwargs):
    # https://stackoverflow.com/a/11157649
    attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds', 'microseconds']
    delta = relativedelta(**kwargs)
    human_string = ""
    for attr in attrs:
        if getattr(delta, attr):
            if human_string != "":
                human_string += ", "
            human_string += '%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1])
    return human_string


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
    query = f"{query} {searchtime}"
    req_para = {'q': query, 'rows': rows, 'wt': "json", "cursorMark": "*", "sort": "id asc"}
    fieldlist = greif.get_node_fields()
    req_para['fl'] = ""
    for each in fieldlist:
        req_para['fl'] += f"{each} "
    req_para['fl'] = req_para['fl'][:-1]
    time0 = time.time()
    iterator = 0
    n = math.floor(int(rows) / int(chunk)) + 1
    if log:
        try:
            stormwarden = open(log, "w")
        except FileNotFoundError:
            stormwarden = sys.stdout
    else:
        stormwarden = sys.stdout
    printing(f"{time.strftime('%d %b %Y %H:%M:%S', time.localtime(time0))} - {time0}", file=stormwarden)
    printing(f"The time difference to NOW() is {delta_time_human(minutes=max_age)}, which amounts for the oldest entry to be from {past_time.strftime('%d.%m.%Y %H:%M:%S')}")
    printing(f"Starting update process, SOLR is {solr}", file=stormwarden)
    printing(f"Detected {n} chunks of a total of {rows} entries with a chunk size of {chunk}", file=stormwarden)
    for i in range(0, n):
        printing(f"{delta_now(time0)}\tStarting a new cycle, this is #{iterator + 1}", file=stormwarden)
        iterator += 1
        if i + 1 != n:
            req_para['rows'] = chunk
        else:
            req_para['rows'] = int(int(rows) % chunk)
        if int(req_para['rows']) == 0:
            continue

        pureData = load_remote_content(solr, req_para, mode="POST")
        current_dateset = test_json(pureData)
        if current_dateset:
            try:
                printing(f"{delta_now(time0)}\tDownload done, subcycle begins, Cursor:  {req_para['cursorMark']}", file=stormwarden)
                chunk_data = slice_header_json(current_dateset)
                for entry in chunk_data:
                    temp = greif.processData(entry, graph)
                    if temp:  # successful spcht interpretation
                        flock.append(temp)
            except KeyError:
                printing(f"KeyError, ", current_dateset, file=stormwarden)
                return False
            printing(f"{delta_now(time0)}\tCycle ended", file=stormwarden)

            if current_dateset.get("nextCursorMark", "*") != "*" and current_dateset['nextCursorMark'] != req_para['cursorMark']:
                req_para['cursorMark'] = current_dateset['nextCursorMark']
            else:
                printing(f"{delta_now(time0)}\tNo further CursorMark was received, therefore there are less results than expected rows. Aborting cycles", file=stormwarden)
                break
    printing(f"{delta_now(time0)}\tDownload & SPCHT finished, commencing updates", file=stormwarden)
    printing(f"There are {len(flock)} updated entries since {past_time.strftime('%d.%m.%Y %H:%M:%S')}", file=stormwarden)
    if len(flock) > 0:
        counter = 0
        if not dryrun:
            len_of_flock = len(flock)
            printing(f"{delta_now(time0)}\tDeleting all {len_of_flock} entries that are about to be replaced", file=stormwarden)
            for each in flock:
                super_simple_progress_bar(counter, len_of_flock, "DEL ", f"{counter} / {len_of_flock}")
                sparqlQuery(f"WITH <{graph}> DELETE {{ <{each[0][0]}> ?p ?o }} WHERE {{ <{each[0][0]}> ?p ?o }}",
                            sparql, auth=sparql_user, pwd=sparql_pw)
                counter += 1
            super_simple_progress_bar_clear()
            printing(f"{delta_now(time0)}\tDeleting of entries complete, reinserting new data", file=stormwarden)
            counter = 0
            for each in flock:
                super_simple_progress_bar(counter, len_of_flock, "INS ", f"{counter} / {len_of_flock}")
                sparqlQuery(Spcht.quickSparql(each, graph), sparql, auth=sparql_user, pwd=sparql_pw)
                counter += 1
            super_simple_progress_bar_clear()
        else:
            printing(f"{delta_now(time0)}\tDry run - nothing happens", file=stormwarden)
    else:
        print("The set is empty, therefore no further processing is been done", file=stormwarden)
    printing(f"{delta_now(time0)}\tProcess finished", file=stormwarden)
    stormwarden.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LOD Data Interpreter",
        usage="Main functions: MarcView, SolrSpy, SolrStats, CheckSpcht, CheckFields, CompileSpcht and FullProcess. Each function needs the appropriated amount of commands to work properly",
        epilog="Individual settings overwrite settings from the config file",
        prefix_chars="-")
    parser.add_argument('--MarcView', '-mv', type=str, help="Loads the specified json file and displays the mark content", metavar="MARCFILE")
    parser.add_argument('--MarcTest', '-mt', type=str,
                        help="Loads the specified json file does a throughtest", metavar="MARCFILE")
    parser.add_argument('--SolrSpy', '-sy', action="store_true", help="finds and counts different entries for a field")
    parser.add_argument('--ProcessData', '-P', action="store_true", help="Processes the given data from solr to virtuoso with given spcht")
    parser.add_argument('--UpdateData', '-U', action="store_true", help="Updates the Data with a specific time-diff")
    parser.add_argument('--SolrStat', '-st', action="store_true", help="Creates statitistics regarding the Solr Fields")
    parser.add_argument('--CheckSpcht', '-cs', action="store_true", help="Tries to load and validate the specified Spcht JSON File")
    parser.add_argument('--CheckFields', '-cf', action="store_true",
                        help="Loads a spcht file and displays all dictionary keys used in that descriptor")
    parser.add_argument('--CompileSpcht', '-ct', action="store_true", help="Loads a SPCHT File, validates and then compiles it to $file")

    parser.add_argument('--spcht', '-S', type=str, help="The spcht descriptor file for the mapping", metavar="FILEPATH")
    parser.add_argument('--config', '-c', type=str, help="Defines a config file load general settings from", metavar="FILEPATH")
    parser.add_argument('--log', '-l', type=str, help="Name of the logfile", metavar="FILEPATH")
    parser.add_argument('--outfile', '-o', type=str, help="file where results will be saved", metavar="FILEPATH")
    parser.add_argument('--solr', '-s', type=str, help="URL auf the /select/ interface of a Apache solr", metavar="URL")
    parser.add_argument('--filter', '-f', type=str, help="Query Filter for q: ???", metavar="STRING")
    parser.add_argument('--sparql_auth', '-sa', type=str, help="URL of the sparql Interface of a virtuoso", metavar="URL")
    parser.add_argument('--sparql_user', '-su', type=str, help="Username for the sparql authentification", metavar="NAME")
    parser.add_argument('--sparql_pw', '-sp', type=str, help="Password for the sparql authentification", metavar="PASSWORD")
    parser.add_argument('--graph', '-g', type=str, help="Main Graph for the insert Operations", metavar="URI")
    parser.add_argument('--part', '-p', type=int, help="Size of one chunk/part when loading data from solr", metavar="number")
    parser.add_argument('--rows', '-r', type=int, help="Total Numbers of rows requested for the Operation", metavar="number")
    parser.add_argument('--time', '-t', type=int, help="Time in Minutes", metavar="number")
    parser.add_argument('--isolate', '-i', type=str, help="DEBUG: Isolates the test set to one ID", metavar="number")

    parser.add_argument('--urls', '-u', action="store_true", help="Lists all urls the procedure knows after loading data")
    parser.add_argument('--dry', '-d', action="store_true", help="Pulls (and loads) all data as per protocol but doesnt change anything permanently")
    parser.add_argument('--TestMode', type=str, help="Executes some 'random', flavour of the day testscript")
    parser.add_argument('--FullTest', action="store_true", help="Progressing mappings with the config specified ressources")
    parser.add_argument('--DownloadTest', action="store_true", help="Tries to Download multiple chunks from solr")

    args = parser.parse_args()
    # +++ CONFIG FILE +++
    if args.config:
        cfg_status = load_config(args.config)

    boring_parameters = ["spcht", "log", "outfile", "solr", "sparql_auth", "sparql_user", "sparql_pw", "graph", "part", "rows", "filter", "time", "isolate", "MarcTest", "MarcView", "TestMode"]

    for arg in vars(args):
        if arg in boring_parameters and getattr(args, arg) is not None:
            PARA[arg] = getattr(args, arg)
    if Spcht.is_dictkey(PARA, 'log'):  # replacing part of the string with a datetime:
        time_string = datetime.now().strftime('%Y%m%d-%H%M%S')
        PARA['log'] = PARA['log'].replace("$time", time_string)

    if args.urls:
        print("URL Entries from Config and Parameters")
        for key in PARA:
            print(f"\t{key}\t{PARA[key]}")

    # ! FullProcess, main meat of the code
    if args.ProcessData:
        if not Spcht.is_dictkey(PARA, 'solr', 'graph', 'spcht', 'sparql', 'rows', 'parts', 'query'):
            long_text = """+++processing Data+++
downloads data from the specified solr as json in the defined chunk size, it uses CursorMark
to save strain on the solr. It pre-filters the selection with query, an empty query is '*:*'. 
Afterwards it inserts into the given spaqrl endpoint, a username and password combination are probably 
needed if not secured. For the inserts a main graph has to be specified and a spcht file
## mandatory Parameters / config entries:
\t solr - URL of the '[URL]/select/ part of the SOLR endpoint
\t graph - named graph
\t spcht - file path to the SPCHT Descriptor file
\t sparql - URL of the sparql endpoint
\t query - query for solr ('*:* is an empty one)
\t rows - number of total rows that get requested (script will halt if solr provides less than that)
\t parts - size of the chunks
## optional parameters:
\t sparql_user - user account for the sparql endpoint
\t sparql_pw - password for the aformentioned user account
\t log - filepath for the process log file

if you see this message, not all mandatory parameters were providedh"""
            print(long_text)
            exit(0)
        full_process(PARA['solr'], PARA['graph'], PARA['spcht'], PARA['sparql'], PARA.get('sparql_user'),
                     PARA.get('sparql_pw'), PARA.get('log'), PARA['rows'], PARA['parts'], PARA['query'])
        exit(0)  # does only one of the big commands

    # ! UpdateProcess - in parts a copy of full process
    if args.UpdateData:
        if not Spcht.is_dictkey(PARA, 'solr', 'graph', 'spcht', 'sparql', 'sparql_user', 'sparql_pw', 'time'):
            print("Some Mandatory Parameters are missing")
            exit(0)
        update_data(PARA['solr'], PARA['graph'], PARA['spcht'], PARA['sparql'], PARA.get('sparql_user'),
                     PARA.get('sparql_pw'), PARA['time'], PARA.get('log'), PARA['rows'], PARA['parts'], PARA['query'])
    # +++ SPCHT Checker +++
    if args.CheckSpcht:
        Spcht.check_format(args.checkSpcht)

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
    if args.FullTest:
        full_process(PARA['solr'], PARA['graph'], PARA['spcht'], PARA['sparql'])
    if args.SolrSpy:
        solr_spy("", 2, 0.5, 0)
    if args.CheckFields:
        used_field_test()
    if args.DownloadTest:
        downloadTest(req_rows=100000, req_chunk=10000, wait_time=2, wait_incrementor=0)
    # TODO Insert Arg Interpretation here
    #
    # main_test()

