#!/usr/bin/env python
# Stand-Alone Tool, gets some statistics about the specified solr.
# Function: fetches x (def: 5000) entries, the enumerate over every data field to determine how many of those exist
# Why? To see how good certain files in the database are actually filled

# global python packages
import copy
from datetime import datetime
import json
import math
import os

import requests
import sys
import time

# local files
from local_tools import is_dict, is_dictkey

# technically you could replace every instance of is_dict with 'isinstance(variable, dict)'

# global variables for later use
# probably bad practice on my part
MAIN_URL = ""
MAIN_URL_PARAM = {}
CHUNK_SIZE = 50
GLOBAL = {}
ERROR = {}
STRUCTURE = {}
STATISTIC = {}
start_time = time.time()  # time for execution time


# load config data

# error message handler, requires load config before, else it will do just send message
def send_error(message, error_name=None):
    global ERROR
    if error_name is None:
        sys.stderr.write(message)
    else:
        if is_dictkey(ERROR, error_name):
            sys.stderr.write(ERROR[error_name].format(message))
        else:
            sys.stderr.write(message)


def load_config(file_path="settings.json"):
    global MAIN_URL, MAIN_URL_PARAM, ERROR, STRUCTURE, CHUNK_SIZE
    with open(file_path) as json_file:
        data = json.load(json_file)
        try:
            ERROR = data['errors']
        except KeyError:
            send_error("Cannot find 'error' Listings in {} File".format(file_path))  # in this there is not error field
            sys.exit()

        try:
            STRUCTURE = data['structure']
        except KeyError:
            send_error("structure", "key")
            sys.exit()

        if is_dictkey(data, "url"):
            MAIN_URL = data['url']
            MAIN_URL_PARAM = data['url_para']
        if is_dictkey(data, "chunk_size"):
            CHUNK_SIZE = int(data['chunk_size'])
        if is_dictkey(data, "dump_file"):
            GLOBAL['dump_file'] = data.get('dump_file', "default_dump_file.json")


# directly requests from solr
def load_remote_content(url, params, response_type=0):
    # starts a GET request to the specified solr server with the provided list of parameters
    # response types: 0 = just the content, 1 = just the header, 2 = the entire GET-RESPONSE
    time1 = time.time()
    try:
        resp = requests.get(url, params=params)
        print("Trying URL {}".format(resp.url))
        print("Request Code {}".format(resp))
        print("Header: \n {}".format(resp.headers))

        # print("Content:"
        print("Remote load took {} seconds".format(str(round(time.time() - time1, 3))))
        if response_type == 0 or response_type > 2:  # this seems ugly
            return resp.text
        elif response_type == 1:
            return resp.headers
        elif response_type == 2:
            return resp
    except requests.exceptions.RequestException as e:
        send_error(e, "file")


def test_json(json_str):
    #  i am almost sure that there is already a build in function that does something very similar, embarrassing
    global ERROR
    try:
        data = json.loads(json_str)
        return data
    except ValueError:
        print(ERROR['json'])
        return False


def traverse_json_data(data):
    # all this does ist to traverse the json to the point where the entries are
    # which is in this hardcoded case the second level in a structure defined by
    # the setting structure['content'], in my cases its called "docs"
    global STRUCTURE
    i = 0
    for (key, value) in data.items():
        if key == STRUCTURE['header']:
            header = value
            continue
        elif key == STRUCTURE['body'] and is_dict(value):  # next iteration, we know this is a dataset
            for (key2, value2) in value.items():
                if key2 != STRUCTURE['content']:
                    continue
                else:
                    for value3 in enumerate(value2):
                        add_entry2statistic(value3)


def traverse_json_response(data):
    # just looks for the header information in a solr GET response
    # technically i probably could just do data.get['response']
    global STRUCTURE
    for (key, value) in data.items():
        if key == STRUCTURE['body']:
            return value
    return False  # inexperience with Python #45: is it okay to return a value OR just boolean False?


def slice_header_json(data):
    # cuts the header from the json response according to the provided structure (which is probably constant anyway)
    # returns list of dictionaries
    global STRUCTURE
    if is_dict(data.get(STRUCTURE['body'])):
        return data.get(STRUCTURE['body']).get(STRUCTURE['content'])

    # either some ifs or a try block, same difference



debug_json = []


def add_entry2statistic(entry):
    global STATISTIC, ERROR, debug_json
    try:
        for (key, value) in entry[1].items():  # tuples start at 1, urg
            # the actual entries are actually tuples and dont really possess a key and value like a dict does
            if is_dictkey(STATISTIC, key):
                STATISTIC[key] += 1
            else:
                STATISTIC[key] = 1
            # print("{} = {}".format(key, str(value)))
        debug_json.append(entry[1])
    except TypeError:
        send_error("add_entry", "typeerror")


def write_statistic(file_path="stats.json"):
    # this functions seems rather redundant, but it makes main a bit prettier
    global STATISTIC, start_time

    now = datetime.now()
    parameters = {'totalRows': MAIN_URL_PARAM['rows'],
                  'date': now.strftime("%d.%m.%Y %H:%M:%S"),
                  'excutionTime': "{} s".format(str(round(time.time() - start_time, 3)))}
    # i have some seconds thoughts about writing tons of functions i a dictionary declaration
    temp_list = {'parameters': parameters, 'stats': STATISTIC}
    try:
        with open(file_path, 'w') as outfile:
            json.dump(temp_list, outfile, indent=4)
        print("{} Bytes of Data were written to {}".format(os.stat(file_path).st_size, file_path))
    except FileExistsError:
        send_error("", "FileExistsError")
    except FileNotFoundError:
        send_error("", "FileNotFoundError")


def crawl_statistic():
    # this checks for all entries that are not always there, for that it just looks what entries we dont have as
    # often as the total number of rows. Unfortunately this will generate a lot of empty request to the solr
    global STATISTIC, MAIN_URL_PARAM, MAIN_URL
    if(is_dictkey(MAIN_URL_PARAM, "rows")) and len(STATISTIC) > 0:  # just makes sure there is anything
        for (key, value) in STATISTIC.items():
            #if value < int(MAIN_URL_PARAM.get('rows', 0)):  # this would be a prime case for multi processing
            # http://172.18.85.143:8080/solr/biblio/select?q=author2:*&rows=0&start=0
            print("=> Getting Full Stats for: {}".format(key))
            request_param = {'q': key+':*', 'rows': '0', 'start': '0', 'wt': 'json'}  # all we really want is the head
            data = test_json(load_remote_content(MAIN_URL, request_param))
            response = traverse_json_response(data)  # or data.get['response']
            STATISTIC[key] = response.get('numFound', STATISTIC.get(key, 0))  # holy recursion batman


def main():
    load_config()  # default path should suffice

    big_data = []

    # mechanism to not load 50000 entries in one go but use chunks for it
    n = math.floor(int(MAIN_URL_PARAM.get('rows')) / CHUNK_SIZE) + 1
    temp_url_param = copy.deepcopy(MAIN_URL_PARAM)  # otherwise dicts get copied by reference
    for i in range(0, n):
        temp_url_param['start'] = i*CHUNK_SIZE
        print("New Chunk started: [{}/{}] - {} ms".format(i, n-1, round(time.time(), 2)))
        if i+1 != n:
            temp_url_param['rows'] = CHUNK_SIZE
        else:
            print(MAIN_URL_PARAM.get('rows'))
            temp_url_param['rows'] = int(int(MAIN_URL_PARAM.get('rows')) % CHUNK_SIZE)
        print(temp_url_param)
        data = test_json(load_remote_content(MAIN_URL, temp_url_param))
        if data:  # no else required, test_json already gives us an error if something fails
            traverse_json_data(data)
            big_data += slice_header_json(data)

    with open(GLOBAL['dump_file'], "w") as fw:
        #  json.dump(big_data, fw, indent=4)
        json.dump(big_data, fw, indent=None, separators=(",", ":"))
    crawl_statistic()
    write_statistic()


def crawl_multi(list_of_ids, outfile):
    global MAIN_URL
    load_config()
    file = open(list_of_ids, "r")
    lines = file.readlines()
    file.close()
    entries = []
    for item in lines:
        temp_url_param = copy.deepcopy(MAIN_URL_PARAM)
        temp_url_param['q'] = "id:"+item.rstrip()
        temp_url_param['rows'] = "1"
        data = test_json(load_remote_content(MAIN_URL, temp_url_param))
        entries.append(data.get('response').get('docs')[0])
    out = open(outfile, "w")
    json.dump(entries, out, indent=4)
    out.close()


if __name__ == "__main__":
    main()
    print("Overall Executiontime was {} seconds".format(str(round(time.time() - start_time, 3))))
    print("Statistic has {} entries".format(len(STATISTIC)))
    with open("debug.json", "w") as fw:
        json.dump(debug_json, fw, indent=4)