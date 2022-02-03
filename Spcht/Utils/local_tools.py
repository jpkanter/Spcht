#!/usr/bin/env python
# coding: utf-8

# Copyright 2021 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of the Solr2Triplestore Tool.
#
# This program is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Solr2Triplestore Tool.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

import sys
import time
import json
import requests
import logging
from dateutil.relativedelta import relativedelta
from requests.auth import HTTPDigestAuth

# more or less only needed for debug stuff
try:
    from termcolor import colored
except ModuleNotFoundError:
    def colored(string: str) -> str:
        return string
# internal modules
import Spcht.Core.SpchtErrors as SpchtErrors

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
        raise SpchtErrors.ParsingError("no response header found")
    code = data.get('responseHeader').get('status')
    if code == 400:
        if 'error' in data:
            raise SpchtErrors.ParsingError(f"response 400 - {data.get('error').get('msg')}")
        else:
            raise SpchtErrors.ParsingError("response 400 BUT no error identifier!")

    if code != 0:  # currently unhandled errors
        if 'error' in data:
            raise SpchtErrors.ParsingError(f"response code {code} - {data.get('error').get('msg')}")
        else:
            raise SpchtErrors.ParsingError(f"response code {code}, unknown cause")

    if code == 0:
        if not 'response' in data:
            raise SpchtErrors.ParsingError("Code 0 (all okay), BUT no response")

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
        if response_type == 1:
            return resp.headers
        elif response_type == 2:
            return resp
        else:
            return resp.text
    except requests.exceptions.RequestException as e:
        print("Request not successful,", e, file=sys.stderr)


def block_sparkle_insert(graph, insert_list):
    sparkle = "INSERT IN GRAPH <{}> {{\n".format(graph)
    for entry in insert_list:
        sparkle += entry
    sparkle += "}"
    return sparkle


def sparqlQuery(sparql_query, base_url, get_format="application/json", **kwargs) -> tuple:
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
        params['default-graph-uri'] = kwargs['named_graph']
    try:
        if kwargs.get("auth", False) and kwargs.get("pwd", False):
            # response = requests.get(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), params=params)
            response = requests.post(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), data=params)
        else:
            response = requests.get(base_url, params=params)
    except requests.exceptions.ConnectionError:
        logger.error("Connection to Sparql-Server failed")
        return False, False

    try:
        if response is not None:
            if get_format == "application/json":
                return True, json.loads(response.text)
            else:
                return True, response.text
        else:
            return False, False
    except json.decoder.JSONDecodeError:
        return True, response.text


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
        logger.error(f"Got supplied an errernous json, started with '{str(json_str)[:100]}'")
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


def sizeof_fmt(num: int, suffix="B") -> str:
    """
    Human readeable size

    https://stackoverflow.com/a/1094933

    https://web.archive.org/web/20111010015624/http://blogmag.net/blog/read/38/Print_human_readable_file_size
    :param int num: size in bytes
    :param str suffix: suffix after size identifier, like GiB
    """
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def setDeepKey(dictionary, value, *keys):
    rolling_dict = dictionary
    for _, key in enumerate(keys):
        if _ < len(keys)-1:
            if key in rolling_dict and isinstance(rolling_dict[key], dict):
                rolling_dict = rolling_dict[key]
            else:
                return None
        else:
            rolling_dict[key] = value
    return dictionary


def convert_to_base_type(input: str, json_mode=False):
    """
    Totally dumb function that does nothing else as to try to convert a string to some basic type

    * 'False' | 'True' -> Bool
    * 123456789 -> int
    * 1.23456789 -> float
    * everything else -> str

    :param input:
    :type input: str
    :param json_mode: in json an all lowercase true/false is the boolean expression
    :type json_mode: bool
    :return:
    :rtype:
    """
    try:
        return int(input)
    except ValueError:
        pass
    try:
        return float(input)
    except ValueError:
        pass
    if json_mode:
        if input.strip() == "false":
            return False
        elif input.strip() == "true":
            return True
    else:
        if input.strip() == "False":
            return False
        elif input.strip() == "True":
            return True
    return input

