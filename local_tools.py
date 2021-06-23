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
import copy
import math
import multiprocessing
import os
import shutil
import sys
import time
import json
import xml

import requests
import logging
import subprocess
import rdflib

import SpchtErrors
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from termcolor import colored
from requests.auth import HTTPDigestAuth
from SpchtDescriptorFormat import Spcht

logger = logging.getLogger(__name__)

# describes structure of the json response from solr Version 7.3.1 holding the ubl data


def slice_header_json(data):
    STRUCTURE = {
        "header": "responseHeader",
        "body": "response",
        "content": "docs"
    }
    # cuts the header from the json response according to the provided structure (which is probably constant anyway)
    # returns list of dictionaries
    if isinstance(data.get(STRUCTURE['body']), dict):
        return data.get(STRUCTURE['body']).get(STRUCTURE['content'])
    raise TypeError("unex_struct")


def solr_handle_return(data):
    """
    Handles the returned json of an apache solr, throws some "meaningful" TypeErrors in case not everything
    went alright. Otherwise it returns the main body which should be a list of dictionaries

    :param dict data: json-like object coming from an apache solr
    :return: a list of dictionary objects containing the queried content
    :rtype: list
    :raises: TypeError on inconsistencies or error 400
    """
    if 'responseHeader' not in data:
        raise TypeError("no response header found")
    code = data.get('responseHeader').get('status')
    if code == 400:
        if 'error' in data:
            raise TypeError(f"response 400 - {data.get('error').get('msg')}")
        else:
            raise TypeError("response 400 BUT no error identifier!")

    if code != 0:  # currently unhandled errors
        if 'error' in data:
            raise TypeError(f"response code {code} - {data.get('error').get('msg')}")
        else:
            raise TypeError(f"response code {code}, unknown cause")

    if code == 0:
        if not 'response' in data:
            raise TypeError("Code 0 (all okay), BUT no response")

        return data.get('response').get('docs')


def load_remote_content(url, params, response_type=0, mode="GET"):
    # starts a GET request to the specified solr server with the provided list of parameters
    # response types: 0 = just the content, 1 = just the header, 2 = the entire GET-RESPONSE
    try:
        if mode != "POST":
            resp = requests.get(url, params=params)
        else:
            resp = requests.post(url, data=params)
        if resp.status_code != 200:
            raise SpchtErrors.RequestError("Request couldnt be fullfilled, check url")
        if response_type == 0 or response_type > 2:  # this seems ugly
            return resp.text
        elif response_type == 1:
            return resp.headers
        elif response_type == 2:
            return resp
    except requests.exceptions.RequestException as e:
        print("Request not successful,", e, file=sys.stderr)


def block_sparkle_insert(graph, insert_list):
    sparkle = "INSERT IN GRAPH <{}> {{\n".format(graph)
    for entry in insert_list:
        sparkle += entry
    sparkle += "}"
    return sparkle


def sparqlQuery(sparql_query, base_url, get_format="application/json", **kwargs):
    # sends a query to the sparql endpoint of a virtuoso and (per default) retrieves a json and returns the data
    params = {
        "default-graph": "",
        "should-sponge": "soft",
        "query": sparql_query,
        "debug": "off",
        "timeout": "",
        "format": get_format,
        "save": "display",
        "fname": ""
    }
    if "named_graph" in kwargs:
        params['default-graph'] = kwargs['named_graph']
    try:
        if kwargs.get("auth", False) and kwargs.get("pwd", False):
            # response = requests.get(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), params=params)
            response = requests.post(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), data=params)
        else:
            response = requests.get(base_url, params=params)
    except requests.exceptions.ConnectionError:
        sys.stderr.write("Connection to Sparql-Server failed\n\r")
        return False

    try:
        if response is not None:
            if get_format == "application/json":
                return json.loads(response.text)
            else:
                return response.text
        else:
            return False
    except json.decoder.JSONDecodeError:
        return response.text


def cprint_type(object, show_type=False):
    # debug function, prints depending on variable type
    colors = {
        "str": "green",
        "dict": "yellow",
        "list": "cyan",
        "float": "white",
        "int": "grey",
        "tuple": "blue",
        "unknow_object": "magenta"
    }

    if isinstance(object, str):
        color = "str"
    elif isinstance(object, dict):
        color = "dict"
    elif isinstance(object, list):
        color = "list"
    elif isinstance(object, float):
        color = "float"
    elif isinstance(object, int):
        color = "int"
    elif isinstance(object, tuple):
        color = "tuple"
    else:
        color = "unknow_object"

    prefix = "{}:".format(color)
    if not show_type:
        prefix = ""

    print(prefix, colored(object, colors.get(color, "white")))


def sleepy_bar(sleep_time, timeskip=0.1):
    """
        Used more for debugging and simple programs, usage of time.sleep might be not accurate
        Displays a simple progressbar while waiting for time to tick away.
        :param float sleep_time: Time in seconds how long we wait, float for precision
        :param float timeskip: Time between cycles, very low numbers might not actualy happen
        :rtype: None
        :return: Doesnt return anything but prints to console with carriage return to overwrite itsself
    """
    try:
        start_time = time.time()
        stop_time = start_time + sleep_time
        while time.time() < stop_time:
            timenow = round(time.time() - start_time, 1)
            super_simple_progress_bar(timenow, sleep_time, prefix="Time", suffix=f"{timenow} / {sleep_time}")
            # i could have used time.time() and stop_time for the values of the bar as well
            time.sleep(timeskip)
        print("\n", end="")
    except KeyboardInterrupt:
        print(f"Aborting - {time.time()}")
        return True


def super_simple_progress_bar(current_value, max_value, prefix="", suffix="", out=sys.stdout):
    """
        Creates a simple progress bar without curses, overwrites itself everytime, will break when resizing
        or printing more text
        :param float current_value: the current value of the meter, if > max_value its set to max_value
        :param float max_value: 100% value of the bar, ints
        :param str prefix: Text that comes after the bar
        :param str suffix: Text that comes before the bar
        :param file out: output for the print, creator doesnt know why this exists
        :rtype: None
        :return: normalmente nothing, False and an error line printed instead of the bar
    """
    try:
        import shutil
    except ImportError:
        print("Import Error", file=out)
        return False
    try:
        current_value = float(current_value)
        max_value = float(max_value)
        prefix = str(prefix)
        suffic = str(suffix)
    except ValueError:
        print("Parameter Value error", file=out)
        return False
    if current_value > max_value:
        current_value = max_value  # 100%
    max_str, rows = shutil.get_terminal_size()
    del rows
    """
     'HTTP |======>                          | 45 / 256 '
     'HTTP |>                                 | 0 / 256 '
     'HTTP |================================| 256 / 256 '
     'HTTP |===============================>| 255 / 256 '
     '[ 5 ]1[ BAR BAR BAR BAR BAR BAR BAR BA]1[   10   ]'
    """
    bar_space = max_str - len(prefix) - len(suffix) - 3  # magic 3 for |, | and >
    bar_length = round((current_value/max_value)*bar_space)
    if bar_length == bar_space:
        arrow = "="
    else:
        arrow = ">"
    the_bar = "="*bar_length + arrow + " "*(bar_space-bar_length)
    print(prefix + "|" + the_bar + "|" + suffix, file=out, end="\r")


def super_simple_progress_bar_clear(out=sys.stdout):
    try:
        import shutil
    except ImportError:
        print("Import Error", file=out)
        return False
    max_str, rows = shutil.get_terminal_size()
    print(" "*max_str, end="\r")


def delta_now(zero_time, rounding=2):
    return str(round(time.time() - zero_time, rounding))


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


def test_json(json_str: str) -> dict or bool:
    #  i am almost sure that there is already a build in function that does something very similar, embarrassing
    try:
        data = json.loads(json_str)
        return data
    except ValueError:
        logger.error(f"Got supplied an errernous json, started with '{str[:100]}'")
        return None
    except SpchtErrors.RequestError as e:
        logger.error(f"Connection Error: {e}")
        return None


def load_from_json(file_path):
    # TODO: give me actually helpful insights about the json here, especially where its wrong, validation and all
    try:
        with open(file_path, mode='r') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Couldnt open file '{file_path}' cause it couldnt be found")
        print("File not found", file=sys.stderr)
        return None
    except ValueError as e:
        logger.error(f"Couldnt open supposed json file due an error while parsing: '{e}'")
        print("JSON Parsing error", file=sys.stderr)
        return None
    except Exception as error:
        logger.error(f"A general exception occured while tyring to open the supposed json file '{file_path}' - {error.args}")
        return None


def UpdateWorkOrder(file_path: str, **kwargs: tuple or list) -> dict:
    """
    Updates a work order file and does some sanity checks around the whole thing, sanity checks
    involve:

    * checking if the new status is lower than the old one
    * overwritting file_paths for the original json or turtle

    :param str file_path: file path to a valid work-order.json
    :param tuple or list kwargs: 'insert' and/or 'update' as tuple, last value is the value for the nested dictionary keys when using update, when using insert n-1 key is the new key and n key the value
    :return dict: returns a work order dictionary
    """
    # ! i actively decided against writing a file class for work order
    work_order = load_from_json(file_path)
    if work_order is not None:
        if "update" in kwargs:
            if isinstance(kwargs['update'], tuple):
                kwargs['update'] = [kwargs['update']]
            for update in kwargs['update']:
                if len(update) < 2:
                    raise SpchtErrors.ParameterError("Not enough parameters")
                old_value = UpdateNestedDictionaryKey(work_order, *update)
                if old_value is None:
                    raise SpchtErrors.ParameterError("Couldnt update key")
                if update[len(update)-2] == "status":
                    if old_value > update[len(update)-1]:
                        raise SpchtErrors.WorkOrderInconsitencyError("New status higher than old one")
        if "insert" in kwargs:
            if isinstance(kwargs['insert'], tuple):
                kwargs['insert'] = [kwargs['insert']]
            for insert in kwargs['insert']:
                if len(insert) < 3:
                    raise SpchtErrors.ParameterError("Not enough parameters")
                overwritten = AddNestedDictionaryKey(work_order, *insert)
                if overwritten is True:
                    raise SpchtErrors.WorkOrderInconsitencyError("Cannot overwrite any one file path")
        with open(file_path, "w") as work_order_file:
            json.dump(work_order, work_order_file, indent=4)
        return work_order

    else:
        raise SpchtErrors.WorkOrderError


def UpdateNestedDictionaryKey(dictionary: dict, *args) -> None or any:
    old_value = None
    try:
        keys = len(args)
        _ = 0
        value = dictionary
        for key in args:
            _ += 1
            if _ + 1 >= keys:
                old_value = value[key]
                value[key] = args[_]  # * immutable dictionary objects are passed by reference
                # * therefore i change the original object here which is precisely what i want
                break  # * one more round to come..which we dont want
            else:
                value = value.get(key)
                if value is None:
                    raise SpchtErrors.ParameterError(key)
        return old_value
    except KeyError as key:
        raise SpchtErrors.ParameterError(key)


def AddNestedDictionaryKey(dictionary: dict, *args) -> bool:
    overwritten = False
    try:
        keys = len(args)
        _ = 0
        value = dictionary
        for key in args:
            _ += 1
            if _ + 2 >= keys:
                if value[key].get(args[_]) is not None:
                    overwritten = True
                value[key][args[_]] = args[_+1]
                break;
            else:
                value = value.get(key)
                if value is None:
                    raise SpchtErrors.ParameterError(key)
        return overwritten
    except KeyError as key:
        raise SpchtErrors.ParameterError(key)


def CheckForParameters(expectations: tuple, **kwargs):
    missing = []
    for argument in expectations:
        if argument not in kwargs:
            missing.append(argument)
    if len(missing) > 0:
        return missing
    return None
    # ? a list with len > 0 is unfortunately truthy so that i have to violate proper protocol a bit here


def CheckWorkOrder(work_order_file: str):
    print(work_order_file)
    work_order = load_from_json(work_order_file)
    if work_order is None:
        return False
    main_status = ("Freshly created", "fetch started", "fetch completed", "processing started", "processing completed", "inbetween process", "inserting started", "insert completed/finished", "fullfilled")
    time_infos = ("processing", "insert")
    try:
        extremes = {"min_processing": None, "max_processing": None,
                    "min_insert": None, "max_insert": None,
                    "min_all": None, "max_all": None,
                    "min_solr": None, "max_solr": None}
        if 'solr_start' in work_order['meta']:
            extremes['min_all'] = datetime.fromisoformat(work_order['meta']['solr_start'])
            extremes['min_solr'] = datetime.fromisoformat(work_order['meta']['solr_start'])
        if 'solr_stop' in work_order['meta']:
            extremes['max_all'] = datetime.fromisoformat(work_order['meta']['solr_finish'])
            extremes['max_solr'] = datetime.fromisoformat(work_order['meta']['solr_finish'])
        counts = { 'rdf_files': 0, 'files': 0, 'un_processing': 0, 'un_insert': 0}
        for key in work_order['file_list']:
            # ? why, yes 'for key, item in dict.items()' is a thing
            for method in time_infos:
                if f'{method}_start' in work_order['file_list'][key]:
                    temp = datetime.fromisoformat(work_order['file_list'][key][f'{method}_start'])
                    if extremes[f'min_{method}'] is None or extremes[f'min_{method}'] > temp:
                        extremes[f'min_{method}'] = temp
                    if extremes[f'min_all'] is None or extremes['min_all'] > temp:
                        extremes[f'min_all'] = temp
                if f'{method}_finish' in work_order['file_list'][key]:
                    temp = datetime.fromisoformat(work_order['file_list'][key][f'{method}_finish'])
                    if extremes[f'max_{method}'] is None or extremes[f'max_{method}'] < temp:
                        extremes[f'max_{method}'] = temp
                    if extremes[f'max_all'] is None or extremes['max_all'] < temp:
                        extremes[f'max_all'] = temp
            if 'rdf_file' in work_order['file_list'][key]:
                counts['rdf_files'] += 1
            if 'file' in work_order['file_list'][key]:
                counts['files'] += 1
            if work_order['file_list'][key]['status'] == 2:
                counts['un_processing'] += 1
            if work_order['file_list'][key]['status'] == 4:
                counts['un_insert'] += 1

        print("+++++++++++++++++++WORK ORDER INFO++++++++++++++++++")
        print(f"Current status:           {main_status[work_order['meta']['status']]}")
        if counts['un_processing'] > 0:
            print(f"Unfinished processing:    {counts['un_processing']}")
        if counts['un_insert'] > 0:
            print(f"Unfinished inserts:       {counts['un_insert']}")
        print(f"Data retrieval:           {work_order['meta']['fetch']}")
        print(f"Processing type:          {work_order['meta']['type']}")
        if 'processing' in work_order['meta']:
            print(f"Multiprocessing, threads: {work_order['meta']['processing']}")
        print(f"Insert method:            {work_order['meta']['method']}")
        if counts['files'] > 0:
            print(f"Downloaded files:         {counts['files']}")
        if counts['rdf_files'] > 0:
            print(f"Processed files:          {counts['rdf_files']}")
        if extremes['min_all'] is not None and extremes['max_all'] is not None:
            delta = extremes['max_all'] - extremes['min_all']
            print(f"Total execution time:     {delta}")
            print(f"From:                     {extremes['min_all']}")
            print(f"To:                       {extremes['max_all']}")
        if extremes['min_solr'] is not None and extremes['max_solr'] is not None:
            delta = extremes['max_solr'] - extremes['min_solr']
            print(f"Download time:            {delta}")
            print(f"From:                     {extremes['min_solr']}")
            print(f"To:                       {extremes['max_solr']}")

        if extremes['min_processing'] is not None and extremes['max_processing'] is not None:
            delta = extremes['max_processing'] - extremes['min_processing']
            print(f"Processing time:          {delta}")
            print(f"From:                     {extremes['min_processing']}")
            print(f"To:                       {extremes['max_processing']}")
        if extremes['min_insert'] is not None and extremes['max_insert'] is not None:
            delta = extremes['max_insert'] - extremes['min_insert']
            print(f"Inserting time:           {delta}")
            print(f"From:                     {extremes['min_insert']}")
            print(f"To:                       {extremes['max_insert']}")
        print("++++++++++++++++++++END OF REPORT+++++++++++++++++++")
    except KeyError as key:
        print("####WORK ORDER LACKS KEYS, ERROR#####")
        print(f"Missing Key {key}")
    return True


def UseWorkOrder(filename, deep_check = False, repair_mode = False, **kwargs) -> list or int:
    """

    :param filename:
    :type filename:
    :param deep_check:
    :type deep_check:
    :param repair_mode:
    :type repair_mode:
    :param kwargs:
    :type kwargs:
    :return: missing parameters for that step or True
    """
    # ? from CheckWorkOrder
    # ? ("Freshly created", "fetch started", "fetch completed", "processing started", "processing completed", "inserting started", "insert completed/finished", "fullfilled")
    # ? Stati, first index is 0
    work_order = load_from_json(filename)
    if work_order is not None:
        try:
            if work_order['meta']['status'] == 0:  # freshly created
                if work_order['meta']['fetch'] == "solr":
                    # ! checks
                    expected = ("work_order_file", "solr_url", "query", "query_rows", "chunk_size", "spcht_descriptor", "save_folder")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing is not None:
                        return missing
                    # ! process
                    UpdateWorkOrder(filename, update=("meta", "status", 1))
                    FetchWorkOrderSolr(filename, **kwargs)
                    UpdateWorkOrder(filename, update=("meta", "status", 2))
                    return 2
            if work_order['meta']['status'] == 1:  # processing started, not finished
                return 1
            if work_order['meta']['status'] == 2:  # fetching completed
                if work_order['meta']['type'] == "insert":
                    # ! checks
                    expected = ("work_order_file", "spcht_descriptor", "graph")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing is not None:
                        return missing
                    # ! process
                    logger.info(f"Sorted order '{os.path.basename(filename)}' as method 'insert'")
                    UpdateWorkOrder(filename, update=("meta", "status", 3))
                    if 'processes' in kwargs:
                        ProcessOrderMultiCore(filename, **kwargs)
                    else:
                        FullfillProcessingOrder(filename, **kwargs)
                    UpdateWorkOrder(filename, update=("meta", "status", 4))
                    logger.info(f"Turtle Files created, commencing to next step")
                    return 5
                if work_order['meta']['type'] == "update":
                    return 4  # inbetween processing
            if work_order['meta']['status'] == 3:  # processing started
                return 3
            if work_order['meta']['status'] == 4:  # processing done
                return 4
            if work_order['meta']['status'] == 5:  # inbetween processing done
                if work_order['meta']['method'] == "isql":
                    # ! checks
                    expected = ("work_order_file", "named_graph", "isql_path", "user", "password", "virt_folder")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing is not None:
                        return missing
                    # ! process
                    logger.info(f"Sorted order '{os.path.basename(filename)}' with method 'isql'")
                    UpdateWorkOrder(filename, update=("meta", "status", 6))
                    FullfillISqlOrder(filename, **kwargs)
                    UpdateWorkOrder(filename, update=("meta", "status", 7))
                    return 6
                elif work_order['meta']['method'] == "sparql":
                    # ! checks
                    expected = ("work_order_file", "named_graph", "sparql_endpoint", "user", "password")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing is not None:
                        return missing
                    # ! process
                    logger.info(f"Sorted order '{os.path.basename(filename)}' with method 'sparql'")
                    UpdateWorkOrder(filename, update=("meta", "status", 6))
                    FullfillSparqlInsertOrder(filename, **kwargs)
                    UpdateWorkOrder(filename, update=("meta", "status", 7))
                    return 7
            if work_order['meta']['status'] == 6:  # inserting started
                return 6
            if work_order['meta']['status'] == 7:  # inserting completed
                # * cleanup period
                return 7
            if work_order['meta']['status'] == 8:  # fullfilled, cleanup done
                # * do nothing, order finished
                return 8

        except KeyError as key:
            logger.error(f"The supplied json file doesnt appear to have the needed data, '{key}' was missing")


def ProcessOrderMultiCore(work_order_file, **kwargs):
    if 'processes' not in kwargs:
        raise SpchtErrors.WorkOrderInconsitencyError("Cannot call multi core process without defined 'processes' parameter")
    if not isinstance(kwargs['processes'], int):
        raise SpchtErrors.WorkOrderTypeError("Processes must be defined as integer")
    logger.info("Started MultiProcess function, duplicated entries might appear in the log files for each instance of the processing procedure")
    processes = []
    #mod_kwargs = {}
    # ? RE: the zombie commented out parts for copies of kwargs, in the parameters there is this innocent
    # ? looking object called spcht_object which is an entire class with some data, thing of it as enzyme
    # ? in theory nothing the processing does should change anything about the spcht itself, it does it
    # ? it thing and once initiated it shall just process data from one state into another
    # ? if any problems with the finished data arise i would definitely first check if the multiprocessing
    # ? causes problems due some kind of racing condition
    if kwargs['processes'] < 1:
        kwargs['processes'] = 1
        logger.info("Number of processes set to 1, config file review is advised")
    else:
        UpdateWorkOrder(work_order_file, insert=("meta", "processes", kwargs['processes']))
    for i in range(0, kwargs['processes']):
        #del mod_kwargs
        #mod_kwargs = copy.copy(kwargs)
        #mod_kwargs['spcht_object'] = Spcht(kwargs['spcht_object'].descriptor_file)
        time.sleep(1)  # ! this all is file based, this is the sledgehammer way of avoiding problems
        p = multiprocessing.Process(target=FullfillProcessingOrder, args=(work_order_file, ), kwargs=kwargs)
        processes.append(p)
        p.start()
    for process in processes:
        process.join()


def CreateWorkOrder(order_name, fetch: str, typus: str, method: str, **kwargs):
    """
    Creates a basic work order file that serves as origin for all further operation, desribes
    the steps necessary to fullfill the order
    :param str order_name: name of the order, the file name will be generated from this
    :param str fetch: Method of data retrieval, either a 'solr' or a list of plain 'file's
    :param str typus: type or work order, either 'insert' or 'update', update deletes triples with the subject of the new data first
    :param str method: method of inserting the data in a triplestore, 'sparql', 'isql' or 'odbc', also 'none' if no such operating should take place
    :return str: the final name / file path of the work order file with all suffix
    """
    allowed = {
        "fetch": ["file", "solr"],
        "typus": ["insert", "update"],
        "method": ["sparql", "isql", "odbc", "none"]
    }
    if fetch not in allowed['fetch']:
        print(f"Fetch method {fetch} not available, must be {allowed['fetch']}")
        return False  # or raise work order Exception?
    if typus not in allowed['typus']:
        print(f"Operation type {typus} unknown, must be {allowed['typus']}")
        return False
    if method not in allowed['method']:
        print(f"Insert method '{method}' not available, must be {allowed['method']}")
        return False
    logger.info("Starting Process of creating a new work order")
    if order_name == "":
        order_name = "work_order"
    work_order = {"meta":
                      {
                       "status": 0,
                       "fetch": fetch,
                       "type": typus,
                       "method": method,
                       },
                  "file_list": {}
                  }
    work_order_filename = os.path.join(os.getcwd(),
        f"{order_name}-{datetime.now().isoformat().replace(':', '-')}.json")
    logger.info(f"attempting to write order file to {work_order_filename}")
    try:
        with open(work_order_filename, "w") as order_file:
            json.dump(work_order, order_file, indent=4)

        return work_order_filename
    except OSError as e:
        logger.info(f"Encountered OSError {e}")


def FetchWorkOrderSolr(work_order_file: str,
                       solr_url: str,
                       query="*",
                       total_rows=50000,
                       chunk_size=10000,
                       spcht_object=None,
                       save_folder="./",
                       **kwargs):
    # ! some checks for the cli usage
    if not os.path.exists(work_order_file):
        print("Work order does not exists")
        return False
    if not isinstance(spcht_object, Spcht):
        print("Provided Spcht Object is not a genuine Spcht Object")
        return False
    if not isinstance(total_rows, int) or not isinstance(chunk_size, int):
        print("The *Number* of rows and chunk_size must be an integer number")
    n = math.floor(int(total_rows) / int(chunk_size)) + 1
    # Work Order things:
    work_order = load_from_json(work_order_file)
    # ! Check meta status informations
    if work_order['meta']['status'] > 0:
        logging.error("Status of work order file is not 0, file is beyond first step and cannot be processed by Solr order")
        return False

    try:
        if work_order['meta']['fetch'] != "solr":
            logging.error("Provided work order does not use fetch method solr")
            return False
        work_order['meta']['max_chunks'] = n
        work_order['meta']['chunk_size'] = chunk_size
        work_order['meta']['total_rows'] = total_rows
        work_order['meta']['spcht_user'] = spcht_object is not None
        work_order['meta']['full_download'] = False
        with open(work_order_file, "w") as order_file:
            json.dump(work_order, order_file, indent=4)

    except KeyError as key:
        logging.error(f"Expected Key {key} is not around in the work order file")
        print("Work Order error, aborting", file=sys.stderr)

    parameters = {'q': query, 'rows': total_rows, 'wt': "json", "cursorMark": "*", "sort": "id asc"}
    # you can specify a Spcht with loaded descriptor to filter field list
    if isinstance(spcht_object, Spcht):
        parameters['fl'] = ""
        for each in spcht_object.get_node_fields():
            parameters['fl'] += f"{each} "
        parameters['fl'] = parameters['fl'][:-1]
        logger.info(f"Using filtered field list: {parameters['fl']}")

    base_path = os.path.join(os.getcwd(), save_folder)
    start_time = time.time()
    logger.info(f"Starting solrdump-like process - Time Zero: {start_time}")
    logger.info(f"Solr Source is {solr_url}")
    logger.info(f"Calculated {n} chunks of a total of {total_rows} entries with a chunk size of {chunk_size}")
    logger.info(f"Start Loading Remote chunks - {delta_now(start_time)}")
    UpdateWorkOrder(work_order_file, insert=("meta", "solr_start", datetime.now().isoformat()))

    try:
        for i in range(0, n):
            logger.info(f"Solr Download - New Chunk started: [{i + 1}/{n}] - {delta_now(start_time)} ms")
            if i + 1 != n:
                parameters['rows'] = chunk_size
            else:  # the rest in the last chunk
                parameters['rows'] = int(int(total_rows) % int(chunk_size))
            if i == 0:  # only first run, no sense in clogging the log files with duplicated stuff
                logger.info(f"\tUsing request URL: {solr_url}/{parameters}")
            # ! call to solr for data
            data = test_json(load_remote_content(solr_url, parameters))
            if data is not None:
                file_path = f"{os.path.basename(work_order_file)}_{hash(start_time)}_{i}-{n}.json"
                filename = os.path.join(base_path, file_path)
                extracted_data = solr_handle_return(data)
                with open(filename, "w") as dumpfile:
                    json.dump(extracted_data, dumpfile)
                file_spec = {"file": os.path.relpath(filename), "status": 1}
                UpdateWorkOrder(work_order_file, insert=("file_list", i, file_spec))

                if data.get("nextCursorMark", "*") != "*" and data['nextCursorMark'] != parameters['cursorMark']:
                    parameters['cursorMark'] = data['nextCursorMark']
                else:
                    logger.info(
                        f"{delta_now(start_time)}\tNo further CursorMark was received, therefore there are less results than expected rows. Aborting cycles")
                    break
            else:
                logger.info(f"Error in chunk {i + 1} of {n}, no actual data was received, aborting process")
                return False
        logger.info(f"Download finished, FullDownload successfull")
        UpdateWorkOrder(work_order_file, update=("meta", "full_download", True), insert=("meta", "solr_finish", datetime.now().isoformat()))
    except KeyboardInterrupt:
        print(f"Process was interrupted by user interaction")
        UpdateWorkOrder(work_order_file, insert=("meta", "completed_chunks", n))
        logger.info(f"Process was interrupted by user interaction")
        return False
    except OSError as e:
        logger.info(f"Encountered OSError {e}")
        return False

    print(f"Overall Solr fetch executiontime was {delta_now(start_time, 3)} seconds")
    logger.info(f"Overall Executiontime was {delta_now(start_time, 3)} seconds")
    return True


def FullfillProcessingOrder(work_order_file: str, graph: str, spcht_object: Spcht, **kwargs):
    """
    Processes all raw data files specified in the work order file list
    :param str work_order_file: filename of a work order file
    :param str graph: graph the data gets mapped to, technically a subject in the <subject> <predicate> <object> chain
    :param Spcht spcht_object: ready loaded Spcht object
    :return: True if everything worked, False if something is not working
    :rtype: boolean
    """
    # ! checks cause this gets more or less directly called via cli
    if not os.path.exists(work_order_file):
        print("Work order does not exists")
        return False
    if not isinstance(graph, str):
        print("Graph/Subject mst be a string")
        return False
    if not isinstance(spcht_object, Spcht):
        print("Provided Spcht Object is not a genuine Spcht Object")
        return False
    if spcht_object.descriptor_file is None:
        print("Spcht object must be succesfully loaded")
        return False
    try:
        # when traversing a list/iterable we cannot change the iterable while doing so
        # but for proper use i need to periodically check if something has changed, as the program
        # does not change the number of keys or the keys itself this should work well enough, although
        # i question my decision to actually use files of any kind as transaction log
        work_order0 = load_from_json(work_order_file)
        # ! work file specific parameter check
        if work_order0['meta']['status'] < 1:
            logging.error("Given order file is below status 0, probably lacks data anyway, cannot proceed")
            return False
        if work_order0['meta']['status'] > 1:
            logging.error("Given order file is above status 1, is already fully processed, cannot proceed")
            return False
        work_order = work_order0
        logger.info(f"Starting processing on files of work order '{os.path.basename(work_order_file)}', detected {len(work_order['file_list'])} Files")
        print(f"Start of Spcht Processing - {os.getpid()}")
        _ = 0
        for key in work_order0['file_list']:
            _ += 1
            if work_order['file_list'][key]['status'] == 1:  # Status 0 - Downloaded, not processed
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 2),
                                             insert=('file_list', key, 'processing_start', datetime.now().isoformat()))
                mapping_data = load_from_json(work_order['file_list'][key]['file'])
                quadros = []
                elements = 0
                for entry in mapping_data:
                    elements += 1
                    quader = spcht_object.processData(entry, graph)
                    quadros += quader
                logger.info(f"Finished file {_} of {len(work_order['file_list'])}, {len(quadros)} triples")
                rdf_dump = f"{work_order['file_list'][key]['file'][:-4]}_rdf.ttl"
                with open(rdf_dump, "w") as rdf_file:
                    rdf_file.write(Spcht.process2RDF(quadros))
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 3),
                                             insert=[('file_list', key, 'rdf_file', rdf_dump),
                                                     ('file_list', key, 'processing_finish', datetime.now().isoformat()),
                                                     ('file_list', key, 'elements', elements),
                                                     ('file_list', key, 'triples', len(quadros))
                                                     ])
        logger.info(f"Finished processing {len(work_order['file_list'])} files and creating turtle files")
        print(f"End of Spcht Processing - {os.getpid()}")
        return True
    except KeyError as key:
        logger.error(f"The supplied work order doesnt appear to have the needed data, '{key}' was missing")
    except Exception as e:
        logger.error(f"Unknown type of exception: '{e}'")


def FullfillISqlOrder(work_order_file: str,
                      isql_path: str,
                      user: str,
                      password: str,
                      named_graph: str,
                      isql_port=1111,
                      virt_folder="/tmp/",
                      **kwargs):  # ! random kwarg is so i can enter more stuff than necessary that can be ignored
    """
    This utilizes the virtuoso bulk loader enginer to insert the previously processed data into the
    virtuoso triplestore. For that it copies the files with the triples into a folder that virtuoso
    accepts for this kind of input, those folders are usually defined in the virtuoso.ini. it then
    manually calls the isql interface to put the file into the bulk loader scheduler, and, if done
    so deleting the copied file. For now the script has no real way of knowing if the operation actually
    succeeds. Only the execution time might be a hint, but that might vary depending on system load
    and overall resources.
    :param str work_order_file: filename of the work order that is to be fullfilled, gets overwritten often
    :param dict work_order: initial work order loaded from file
    :param str isql_path: path to the virtuoso isql-v/isql executable
    :param str user: name of a virtuoso user with enough rights to insert
    :param str password: clear text password of the user from above
    :param str named_graph: named graph the data is to be inserted into
    :param int isql_port: port of the virtuoso sql database, usually 1111
    :param str virt_folder: folder that virtuoso accepts as input for files, must have write
    :return: True if everything went "great"
    :rtype: Bool
    """
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['status'] < 4:
            logging.error("Order hast a status below 4 and might be not fully procssed or fetch, aborting")
            return False
        if work_order0['meta']['status'] > 5:
            logging.error("This work orders status indicates that its already done, aborting.")
            return False
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 3:
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 4),
                                             insert=('file_list', key, 'insert_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                f_path = shutil.copy(f_path, virt_folder)
                command = f"EXEC=ld_add('{f_path}', '{named_graph}');"
                zero_time = time.time()
                subprocess.call([isql_path, str(isql_port), user, password, "VERBOSE=OFF", command, "EXEC=rdf_loader_run();", "EXEC=checkpoint;"])
                logger.info(f"Executed ld_add command via isql, execution time was {delta_now(zero_time)} (cannot tell if call was successfull, times below 10 ms are suspicious)")
                # ? apparently i cannot really tell if the isql stuff actually works
                if os.path.exists(f_path):
                    os.remove(f_path)
                # reloading work order in case something has changed since then
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 5), insert=('file_list', key, 'insert_finish', datetime.now().isoformat()))
        logger.info(f"Successfully called {len(work_order['file_list'])} times the bulk loader")
    except KeyError as foreign_key:
        logger.error(f"Missing key in work order: '{foreign_key}'")
        return False
    except PermissionError as folder:
        logger.error(f"Cannot access folder {folder} to copy turtle into.")
        return False
    except FileNotFoundError as file:
        logger.error(f"Cannot find file {file}")
        return False
    return True


def FullfillSparqlInsertOrder(work_order_file: str,
                              sparql_endpoint: str,
                              user: str,
                              password: str,
                              named_graph: str,
                              **kwargs):
    # WITH GRAPH_IRI INSERT { bla } WHERE {};
    SPARQL_CHUNK = 50
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['status'] < 4:
            logging.error("Order hast a status below 4 and might be not fully procssed or fetch, aborting")
            return False
        if work_order0['meta']['status'] > 5:
            logging.error("This work orders status indicates that its already done, aborting.")
            return False
        if work_order0['meta']['method'] != "sparql":
            raise SpchtErrors.WorkOrderError(f"Method in work order file is {work_order0['meta']['method']} but must be 'sparql' for this method")
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 3:
                work_order = UpdateWorkOrder(work_order_file,
                     update=('file_list', key, 'status', 4),
                     insert=('file_list', key, 'insert_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                this_graph = rdflib.Graph()
                this_graph.parse(f_path, format="turtle")
                triples = ""
                rounds = 0
                for sub, pred, obj in this_graph:
                    rounds += 1
                    if obj is rdflib.term.URIRef:
                        triples += f"<{sub}> <{pred}> <{obj}> . \n"
                    else:
                        triples += f"<{sub}> <{pred}> \"{obj}\" . \n"
                    # ! TODO: can optimize here, grouped queries
                    if rounds > SPARQL_CHUNK:
                        query = f"""WITH <{named_graph}> INSERT {{ {triples}}}"""
                        # * i have the sneaking suspicion that i defined the named graph twice
                        sparqlQuery(query,
                                    sparql_endpoint,
                                    auth=user,
                                    pwd=password,
                                    named_graph=named_graph
                                    )
                        triples = ""
                        rounds = 0
                # END OF FOR LOOP
                if rounds > 0 and triples != "":
                    query = f"""WITH <{named_graph}> INSERT {{ {triples}}}"""
                    sparqlQuery(query,
                                sparql_endpoint,
                                auth=user,
                                pwd=password,
                                named_graph=named_graph
                                )
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 5), insert=('file_list', key, 'insert_finish', datetime.now().isoformat()))
    except KeyError as foreign_key:
        logger.error(f"Missing key in work order: '{foreign_key}'")
    except FileNotFoundError as file:
        logger.error(f"Cannot find file {file}")
    except xml.parsers.expat.ExpatError as e:
        logger.error(f"Parsing of triple file failed: {e}")