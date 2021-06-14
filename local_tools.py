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


import math
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


def load_from_json(file_path):
    # TODO: give me actually helpful insights about the json here, especially where its wrong, validation and all
    try:
        with open(file_path, mode='r') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Couldnt open file '{file_path}' cause it couldnt be found")
        return None
    except ValueError as e:
        logger.error(f"Couldnt open supposed json file due an error while parsing: '{e}'")
        return None
    except Exception as error:
        logger.error(f"A general exception occured while tyring to open the supposed json file '{file_path}' - {error.args}")
        return None


def UpdateWorkOrder(file_path: str, **kwargs) -> dict:
    """
    Updates a work order file and does some sanity checks around the whole thing, sanity checks
    involve:

    * checking if the new status is lower than the old one
    * overwritting file_paths for the original json or turtle

    :param str file_path: file path to a valid work-order.json
    :param tuple kwargs: 'insert' and/or 'update' as tuple, last value is the value for the nested dictionary keys when using update, when using insert n-1 key is the new key and n key the value
    :return dict: returns a work order dictionary
    """
    # ! i activly decided against writting a file class for work order
    work_order = load_from_json(file_path)
    if work_order is not None:
        if "update" in kwargs:
            if len(kwargs['update']) < 2:
                raise SpchtErrors.ParameterError("Not enough parameters")
            old_value = UpdateNestedDictionaryKey(work_order, *kwargs['update'])
            if old_value is None:
                raise SpchtErrors.ParameterError("Couldnt update key")
            if kwargs['update'][len(kwargs['update'])-2] == "status":
                if old_value > kwargs['update'][len(kwargs['update'])-1]:
                    raise SpchtErrors.WorkOrderInconsitencyError("New status higher than old one")
        if "insert" in kwargs:
            if len(kwargs['insert']) < 3:
                raise SpchtErrors.ParameterError("Not enough parameters")
            overwritten = AddNestedDictionaryKey(work_order, *kwargs['insert'])
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
                # * therefore i change the original object here which is precisly what i want
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
                print(f"My Key is {args[_]}")
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


def CreateInsertWorkOrder(solr, query="*", total_rows=500000, chunk_size=50000, loaded_spcht=None, order_name="work_order", sub_folder="",*args):
    logger.info("Starting Process of creating a new work order")
    parameters = {'q': query, 'rows': total_rows, 'wt': "json", "cursorMark": "*", "sort": "id asc"}
    # you can specify a Spcht with loaded descriptor to filter field list
    if order_name == "":
        order_name = "work_order"
    if isinstance(loaded_spcht, Spcht):
        parameters['fl'] = ""
        for each in loaded_spcht.get_node_fields():
            parameters['fl'] += f"{each} "
        parameters['fl'] = parameters['fl'][:-1]
        logger.info(f"Using filtered field list: {parameters['fl']}")
    start_time = time.time()
    logger.info(f"Starting solrdump-like process - Time Zero: {start_time}")
    n = math.floor(int(total_rows) / int(chunk_size)) + 1
    work_order = {"meta":
                      {"downloaded": datetime.now().isoformat(),
                       "type": "insert",
                       "method": "isql",
                       "max_chunks": n,
                       "chunk_size": chunk_size,
                       "total_rows": total_rows,
                       "spcht_used": loaded_spcht is not None,
                       },
                  "file_list": {}
                  }

    logger.info(f"Solr Source is {solr}")
    logger.info(f"Calculated {n} chunks of a total of {total_rows} entries with a chunk size of {chunk_size}")
    logger.info(f"Start Loading Remote chunks - {delta_now(start_time)}")
    base_path = os.path.join(os.getcwd(), sub_folder)
    success = True
    work_order_filename = None
    try:
        for i in range(0, n):
            logger.info(f"New Chunk started: [{i + 1}/{n}] - {delta_now(start_time)} ms")
            if i + 1 != n:
                parameters['rows'] = chunk_size
            else:  # the rest in the last chunk
                parameters['rows'] = int(int(total_rows) % int(chunk_size))
            if i == 0:  # only first run, no sense in clogging the log files with duplicated stuff
                logger.info(f"\tUsing request URL: {solr}/{parameters}")
            # ! call to solr for data
            data = test_json(load_remote_content(solr, parameters))
            if data is not None:
                file_path = f"{order_name}_{hash(start_time)}_{i}-{n}.json"
                filename = os.path.join(base_path, file_path)
                extracted_data = solr_handle_return(data)
                with open(filename, "w") as dumpfile:
                    json.dump(extracted_data, dumpfile)
                work_order["file_list"][i] = {"file": filename, "status": 1}

                if data.get("nextCursorMark", "*") != "*" and data['nextCursorMark'] != parameters['cursorMark']:
                    parameters['cursorMark'] = data['nextCursorMark']
                else:
                    logger.info(
                        f"{delta_now(start_time)}\tNo further CursorMark was received, therefore there are less results than expected rows. Aborting cycles")
                    break
            else:
                logger.info(f"Error in chunk {i+1} of {n}, no actual data was received, aborting process")
                success = False
                break
        logger.info(f"Download finished, FullDownload={success}")
        work_order["meta"]["full_download"] = success
        work_order_filename = os.path.join(base_path, f"{order_name}-{datetime.now().isoformat().replace(':', '-')}.json")
        logger.info(f"attempting to write order file to {work_order_filename}")
        with open(work_order_filename, "w") as order_file:
            json.dump(work_order, order_file, indent=4)

    except KeyboardInterrupt:
        print(f"Process was interrupted by user interaction")
        logger.info(f"Process was interrupted by user interaction")
    except OSError as e:
        logger.info(f"Encountered OSError {e}")
    finally:
        print(f"Overall Executiontime was {delta_now(start_time, 3)} seconds")
        logger.info(f"Overall Executiontime was {delta_now(start_time, 3)} seconds")
    if work_order_filename is not None:
        return work_order_filename
    else:
        return None  # unnecessary verbose


def UseWorkOrder(filename, deep_check = False, **kwargs):
    work_order = load_from_json(filename)
    if work_order is not None:
        try:
            if work_order['meta']['type'] == "insert":
                logger.info(f"Sorted order '{os.path.basename(filename)}' as type 'insert'")
                FullfillProcessingOrder(filename, work_order, **kwargs)
                if work_order['meta']['method'] == "isql":
                    logger.info(f"Turtle Files created, commencing to Virtuoso insert")
                    work_order = load_from_json(filename)
                    FullfillISqlOrder(filename, work_order, **kwargs)

        except KeyError as key:
            logger.error(f"The supplied json file doesnt appear to have the needed data, '{key}' was missing")


def FullfillProcessingOrder(filename: str, graph: str, spcht_object: Spcht, **kwargs):
    try:
        # when traversing a list/iterable we cannot change the iterable while doing so
        # but for proper use i need to periodically check if something has changed, as the program
        # does not change the number of keys or the keys itself this should work well enough, although
        # i question my decision to actually use files of any kind as transaction log
        work_order0 = load_from_json(filename)
        work_order = work_order0
        logger.info(f"Starting processing on files of work order '{os.path.basename(filename)}', detected {len(work_order['file_list'])} Files")
        _ = 0
        for key in work_order0['file_list']:
            _ += 1
            if work_order['file_list'][key]['status'] == 1:  # Status 0 - Downloaded, not processed
                work_order = UpdateWorkOrder(filename,
                                             update=('file_list', key, 'status', 2),
                                             insert=('file_list', key, 'processing_date', datetime.now().isoformat()))
                mapping_data = load_from_json(work_order['file_list'][key]['file'])
                quadros = []
                for entry in mapping_data:
                    quader = spcht_object.processData(entry, graph)
                    quadros += quader
                logger.info(f"Finished file {_} of {len(work_order['file_list'])}, {len(quadros)} triples")
                rdf_dump = f"{work_order['file_list'][key]['file'][:-4]}_rdf.ttl"
                with open(rdf_dump, "w") as rdf_file:
                    rdf_file.write(Spcht.process2RDF(quadros))
                work_order = UpdateWorkOrder(filename,
                                update=('file_list', key, 'status', 3),
                                insert=('file_list', key, 'rdf_file', rdf_dump))
        logger.info(f"Finished processing {len(work_order['file_list'])} files and creating turtle files")

    except KeyError as key:
        logger.error(f"The supplied work order doesnt appear to have the needed data, '{key}' was missing")
    except Exception as e:
        logger.error(f"Unknown type of exception: '{e}'")


def FullfillISqlOrder(filename: str, isql_path: str, user: str, password: str, named_graph: str, isql_port=1111, virt_folder="/tmp/", **kwargs):
    """
    This utilizes the virtuoso bulk loader enginer to insert the previously processed data into the
    virtuoso triplestore. For that it copies the files with the triples into a folder that virtuoso
    accepts for this kind of input, those folders are usually defined in the virtuoso.ini. it then
    manually calls the isql interface to put the file into the bulk loader scheduler, and, if done
    so deleting the copied file. For now the script has no real way of knowing if the operation actually
    succeeds. Only the execution time might be a hint, but that might vary depending on system load
    and overall resources.
    :param str filename: filename of the work order that is to be fullfilled, gets overwritten often
    :param dict work_order: initial work order loaded from file
    :param str isql_path: path to the virtuoso isql-v/isql executable
    :param str user: name of a virtuoso user with enough rights to insert
    :param str password: clear text password of the user from above
    :param str named_graph: named graph the data is to be inserted into
    :param int isql_port: port of the virtuoso sql database, usually 1111
    :param str virt_folder: folder that virtuoso accepts as input for files, must have write
    :return: nothing
    :rtype: None
    """
    try:
        work_order0 = load_from_json(filename)
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 3:
                work_order = UpdateWorkOrder(filename,
                                             update=('file_list', key, 'status', 4),
                                             insert=('file_list', key, 'insert_date', datetime.now().isoformat()))
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
                work_order = UpdateWorkOrder(filename, update=('file_list', key, 'status', 5))
        logger.info(f"Successfully called {len(work_order['file_list'])} times the bulk loader")
    except KeyError as foreign_key:
        logger.error(f"Missing key in work order: '{foreign_key}'")
    except PermissionError as folder:
        logger.error(f"Cannot access folder {folder} to copy turtle into.")
    except FileNotFoundError as file:
        logger.error(f"Cannot find file {file}")


def FullfillSparqlInsertOrder(work_order_file: str, sparql_endpoint: str, user: str, password: str, named_graph: str, **kwargs):
    # WITH GRAPH_IRI INSERT { bla } WHERE {};
    SPARQL_CHUNK = 50
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['method'] != "sparql":
            raise SpchtErrors.WorkOrderError(f"Method in work order file is {work_order0['meta']['method']} but must be 'sparql' for this method")
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 3:
                work_order = UpdateWorkOrder(work_order_file,
                     update=('file_list', key, 'status', 4),
                     insert=('file_list', key, 'insert_date', datetime.now().isoformat()))
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
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 5))
    except KeyError as foreign_key:
        logger.error(f"Missing key in work order: '{foreign_key}'")
    except FileNotFoundError as file:
        logger.error(f"Cannot find file {file}")
    except xml.parsers.expat.ExpatError as e:
        logger.error(f"Parsing of triple file failed: {e}")