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
import errno
import json
import logging
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml
from datetime import timedelta, datetime

import rdflib

import SpchtErrors
from SpchtDescriptorFormat import Spcht
from SpchtConstants import WORK_ORDER_STATUS
import SpchtDescriptorFormat

from local_tools import load_from_json, sparqlQuery, delta_now, test_json, \
    load_remote_content, solr_handle_return

logger = logging.getLogger(__name__)


def UpdateWorkOrder(file_path: str, force=False, **kwargs: tuple or list) -> dict:
    """
    kwarg Modes:
    * update - updates a key, needs at least 2 indizes
    * insert - inserts a key, needs at least 3 indizes
    * delete - deletes a key, needs at least 1 index
    Updates a work order file and does some sanity checks around the whole thing, sanity checks
    involve:

    * checking if the new status is lower than the old one
    * overwritting file_paths for the original json or turtle

    :param str file_path: file path to a valid work-order.json
    :param bool force: ignores checks like a new status being lower than the old one
    :param tuple or list kwargs: 'insert' and/or 'update' and/or 'delete' as tuple, last value is the value for the nested dictionary keys when using update, when using insert n-1 key is the new key and n key the value
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
                # * sanity check
                if update[len(update) - 2] == "status" and not force:
                    if old_value > update[len(update) - 1]:
                        raise SpchtErrors.WorkOrderInconsitencyError("New status higher than old one")
        if "insert" in kwargs:
            protected_entries = ("file", "rdf_file")
            if isinstance(kwargs['insert'], tuple):
                kwargs['insert'] = [kwargs['insert']]
            for insert in kwargs['insert']:
                if len(insert) < 3:
                    raise SpchtErrors.ParameterError("Not enough parameters")
                overwritten = AddNestedDictionaryKey(work_order, *insert)
                # * sanity check for certain fields
                field_type = insert[len(insert) - 1]
                if overwritten and field_type in protected_entries and not force:
                    raise SpchtErrors.WorkOrderInconsitencyError("Cannot overwrite any one file path")
                    # ? file entries are linked to somewhere, we dont want to overwrite those
        if "delete" in kwargs:
            if isinstance(kwargs['delete'], tuple):
                kwargs['delete'] = [kwargs['delete']]
            for deletion in kwargs['delete']:
                DeleteNestedDictionaryKey(work_order, *deletion)
        with open(file_path, "w") as work_order_file:
            json.dump(work_order, work_order_file, indent=4)
        return work_order

    else:
        raise SpchtErrors.WorkOrderError


def UpdateNestedDictionaryKey(dictionary: dict, *args) -> None or any:
    """
    Changes the content of a dictionary key in any depth that is specified, if the 'path' does not exist
    nothing will happen. The last argument will be the new value.
    :param dict dictionary:
    :param str args:
    :return: Boolean operator wether this was succesfull
    """
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
    """
    Adds an arbitary key with the value of the last argument to a dictionary, will not create the pathway to that
    parameter, if the previos keys do not exist nothing will happen
    :param dict dictionary:
    :param str args:
    :return: Boolean operator wether this was succesfull
    """
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
                value[key][args[_]] = args[_ + 1]
                break
            else:
                value = value.get(key)
                if value is None:
                    raise SpchtErrors.ParameterError(key)
        return overwritten
    except KeyError as key:
        raise SpchtErrors.ParameterError(key)


def DeleteNestedDictionaryKey(dictionary: dict, *args) -> bool:
    """
    deletes the specified key in the directory that might be in any depth, does nothing if the key does not exist
    :param dict dictionary:
    :param str args:
    :return: Boolean operator wether this was succesfull
    """
    try:
        keys = len(args)
        _ = 0
        value = dictionary
        for key in args:
            _ += 1
            if _ >= keys:
                if value.pop(key, None) is not None:  # pop returns the popped value which should be truthy
                    return True
                else:
                    return False
            else:
                value = value.get(key)
                if value is None:
                    raise SpchtErrors.ParameterError(key)
    except KeyError as key:
        raise SpchtErrors.ParameterError(key)


def CheckForParameters(expectations: tuple, **kwargs):
    """
    Checks if all if the expected parameters are present in the parameters of this function and returns those that are not
    :param tuple expectations:
    :type expectations:
    :param kwargs:
    :return: a list of missing parameters
    :rtype: list
    """
    missing = []
    for argument in expectations:
        if argument not in kwargs:
            missing.append(argument)
    return missing
    # ? a list with len > 0 is unfortunately truthy so that i have to violate proper protocol a bit here


def CheckWorkOrder(work_order_file: str):
    """
    Crawls all available data in a work order files and writes a summary to stdout, also creates some statistic
    about how long things needed to process and what the current status of the file is.
    :param str work_order_file: file path to a work order file
    :return: Nothing, only displays to console
    """
    global WORK_ORDER_STATUS
    print(work_order_file)
    work_order = load_from_json(work_order_file)
    if work_order is None:
        return False

    # ? surely this could have been a dictionary but it isn't
    time_infos = ("processing", "insert", "deletion", "solr")
    try:
        extremes = {"min_processing": None, "max_processing": None,
                    "min_insert": None, "max_insert": None,
                    "min_all": None, "max_all": None,
                    "min_solr": None, "max_solr": None,
                    "min_deletion": None, "max_deletion": None}
        linear_delta = timedelta(
            seconds=0)  # the linear time needed to execute everything, due parallel processing this can be longer than the actual time that was needed
        if 'solr_start' in work_order['meta']:
            extremes['min_all'] = datetime.fromisoformat(work_order['meta']['solr_start'])
            extremes['min_solr'] = datetime.fromisoformat(work_order['meta']['solr_start'])
        if 'solr_stop' in work_order['meta']:
            extremes['max_all'] = datetime.fromisoformat(work_order['meta']['solr_finish'])
            extremes['max_solr'] = datetime.fromisoformat(work_order['meta']['solr_finish'])
        if 'solr_start' in work_order['meta'] and 'solr_stop' in work_order['meta']:
            linear_delta += extremes['max_solr'] - extremes['min_solr']
        counts = {'rdf_files': 0, 'files': 0, 'un_processing': 0, 'un_insert': 0,
                  'un_intermediate': 0}  # occasions of something
        counters = {"elements": 0, "triples": 0}  # adding counts of individual fields
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
                if f'{method}_start' in work_order['file_list'][key] and f'{method}_finish' in work_order['file_list'][key]:
                    linear_delta += extremes[f'max_{method}'] - extremes[f'min_{method}']
            for prop in counters.keys():
                if prop in work_order['file_list'][key]:
                    if isinstance(work_order['file_list'][key][prop], int):
                        counters[prop] += work_order['file_list'][key][prop]
            if 'rdf_file' in work_order['file_list'][key]:
                counts['rdf_files'] += 1
            if 'file' in work_order['file_list'][key]:
                counts['files'] += 1
            status = work_order['file_list'][key]['status']
            if status == 3 or status == 2:
                counts['un_processing'] += 1
            if status == 5 or status == 4:
                counts['un_intermediate'] += 1
            if status == 7 or status == 6:
                counts['un_insert'] += 1
        print("+++++++++++++++++++WORK ORDER INFO++++++++++++++++++")
        print(f"Current status:           {WORK_ORDER_STATUS[work_order['meta']['status']]}")
        if counts['un_processing'] > 0:
            print(f"Unfinished processing:    {counts['un_processing']}")
        if counts['un_insert'] > 0:
            print(f"Unfinished inserts:       {counts['un_insert']}")
        if counts['un_intermediate'] > 0:
            print(f"Unfinished intermediate:  {counts['un_intermediate']}")
        print(f"Data retrieval:           {work_order['meta']['fetch']}")
        if work_order['meta'].get("chunk_size") and work_order['meta'].get("total_rows"):
            print(
                f"DL Parameters:            {work_order['meta']['total_rows']} @ {work_order['meta']['chunk_size']} chunks")
        print(f"Processing type:          {work_order['meta']['type']}")
        if 'processing' in work_order['meta']:
            print(f"Multiprocessing, threads: {work_order['meta']['processing']}")
        if counters['elements'] > 0:
            print(f"Processed elements:       {counters['elements']}")
        if counters['triples'] > 0:
            print(f"Resulting triples:        {counters['triples']}")
        print(f"Insert method:            {work_order['meta']['method']}")
        if counts['files'] > 0:
            print(f"Downloaded files:         {counts['files']}")
        if counts['rdf_files'] > 0:
            print(f"Processed files:          {counts['rdf_files']}")
        if extremes['min_all'] is not None and extremes['max_all'] is not None:
            delta = extremes['max_all'] - extremes['min_all']
            delta2 = None
            for averice in time_infos:
                if extremes[f'min_{averice}'] is not None and extremes[f'max_{averice}'] is not None:
                    if delta2 is None:
                        delta2 = extremes[f'max_{averice}'] - extremes[f'min_{averice}']
                    else:  # ? this insulates against some weird edge case i dont even know, why i am doing this?
                        delta2 += extremes[f'max_{averice}'] - extremes[f'min_{averice}']
            print(f"Total execution time:     {delta}")
            if delta2:
                print(f"Relative execution time:  {delta2}")
            print(f"Linear execution time:    {linear_delta}")
            print(f"From:                     {extremes['min_all']}")
            print(f"To:                       {extremes['max_all']}")
        if extremes['min_solr'] is not None and extremes['max_solr'] is not None:
            delta = extremes['max_solr'] - extremes['min_solr']
            print(f"Download time:            {delta}")
            print(f"From:                     {extremes['min_solr']}")
            print(f"To:                       {extremes['max_solr']}")
        if extremes['min_deletion'] is not None and extremes['max_deletion'] is not None:
            delta = extremes['max_deletion'] - extremes['min_deletion']
            print(f"Deletion time:            {delta}")
            print(f"From:                     {extremes['min_deletion']}")
            print(f"To:                       {extremes['max_deletion']}")
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


def UseWorkOrder(work_order_file, **kwargs) -> list or int:
    """
    :param filename str: file path of the work order
    :param deep_check boolean: if true checks the file list for inconsistencies
    :param repair_mode boolean: if true resets all 'inbetween' status to the next null status
    :return: missing parameters for that step or True
    """
    # ? from CheckWorkOrder
    # ? ("Freshly created", "fetch started", "fetch completed", "processing started", "processing completed", "inserting started", "insert completed/finished", "fullfilled")
    # ? Status, first index is 0
    boiler_print = ", check log files for details"
    if 'work_order_file' not in kwargs:  # ? for manual use cause the checks were build for cli
        kwargs['work_order_file'] = work_order_file
    if 'spcht_descriptor' not in kwargs and 'spcht_object' in kwargs:
        kwargs['spcht_descriptor'] = "dummy, dont need this anymore"
    if 'spcht_descriptor' in kwargs and 'spcht_object' not in kwargs:
        specht = Spcht(kwargs['spcht_descriptor'])
        kwargs['spcht_object'] = specht
    work_order = load_from_json(work_order_file)
    if work_order is not None:
        try:
            if work_order['meta']['status'] == 1:  # fetching started
                logger.debug(f"Order {work_order_file}: Status 1 detected, reseting")
                # fetch process is not recoverable, need to reset to zero state and start anew
                HardResetWorkOrder(work_order_file)
            if work_order['meta']['status'] == 0 or work_order['meta']['status'] == 1:  # freshly created
                logger.debug(f"Order {work_order_file}: Status 0 detected")
                if work_order['meta']['fetch'] == "solr":
                    # ! checks
                    if work_order['meta']['type'] == "update":
                        logger.debug(f"Order {work_order_file}: Status 0 sorted into update download/insert")
                        expected = (
                            "work_order_file", "solr_url", "query", "total_rows", "chunk_size", "spcht_descriptor",
                            "save_folder", "max_age")
                    else:
                        logger.debug(f"Order {work_order_file}: Status 0 sorted into normal insert")
                        expected = (
                            "work_order_file", "solr_url", "query", "total_rows", "chunk_size", "spcht_descriptor",
                            "save_folder")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing:
                        logger.info(f"WorkOrder File '{work_order_file}' couldnt not be processed because parameters {str(missing)} were missing.")
                        return missing
                    # ! process
                    UpdateWorkOrder(work_order_file, update=("meta", "status", 1))
                    if FetchWorkOrderSolr(**kwargs):
                        logger.debug(f"Order {work_order_file}: Solr fetching finished successful")
                        UpdateWorkOrder(work_order_file, update=("meta", "status", 2))
                        return 2
                    else:
                        msg = "Solr fetching failed, process now in 'inbetween' status"
                        logging.error(msg)
                        print(f"{msg}{boiler_print}")
                        return 1
            if work_order['meta']['status'] == 3:  # processing started
                logger.debug(f"Order {work_order_file}: Status 3 detected")
                print(f"Pickuping the order in an 'inbetween' status - {WORK_ORDER_STATUS[work_order['meta']['status']]}")
                if not SoftResetWorkOrder(work_order_file):
                    msg = f"Reseting work order to state {WORK_ORDER_STATUS[work_order['meta']['status']] - 1} failed"
                    print(msg)
                    logger.critical(f"UseWorkOrder > {msg}")
                    return 3
            if work_order['meta']['status'] == 2 or work_order['meta']['status'] == 3:  # fetching completed
                logger.debug(f"Order {work_order_file}: Status 2 detected")
                # ! checks
                expected = ("work_order_file", "spcht_descriptor", "subject")
                missing = CheckForParameters(expected, **kwargs)
                if missing:
                    return missing
                # ! process
                logger.info(f"Sorted order '{os.path.basename(work_order_file)}' as method 'insert'")
                UpdateWorkOrder(work_order_file, update=("meta", "status", 3))
                if 'processes' in kwargs:
                    ProcessOrderMultiCore(**kwargs)
                else:
                    FulfillProcessingOrder(**kwargs)
                # ! TODO: need checkup function here
                UpdateWorkOrder(work_order_file, update=("meta", "status", 4))
                logger.info(f"Turtle Files created, commencing to next step")
                return 4
            if work_order['meta']['status'] == 5:  # intermediate processing started
                logger.debug(f"Order {work_order_file}: Status 5 detected")
                print(f"Pickuping the order in an 'inbetween' status - {WORK_ORDER_STATUS[work_order['meta']['status']]}")
                if not SoftResetWorkOrder(work_order_file):
                    msg = f"Reseting work order to state {WORK_ORDER_STATUS[work_order['meta']['status']] - 1} failed"
                    print(msg)
                    logger.critical(f"UseWorkOrder > {msg}")
                    return 3
            if work_order['meta']['status'] == 4 or work_order['meta']['status'] == 5:  # processing done
                logger.debug(f"Order {work_order_file}: Status 4 detected")
                if work_order['meta']['type'] == "insert":
                    UpdateWorkOrder(work_order_file, update=("meta", "status", 6))
                    return UseWorkOrder(**kwargs)  # jumps to the next step, a bit dirty this solution
                if work_order['meta']['type'] == "update":
                    # ? isql emulates sparql queries in the interface
                    if work_order['meta']['method'] == "sparql":
                        # ! checks
                        expected = ("work_order_file", "named_graph", "sparql_endpoint", "user", "password")
                        missing = CheckForParameters(expected, **kwargs)
                        if missing:
                            return missing
                        logger.info(f"Scanned order '{os.path.basename(work_order_file)}' as type 'update', deletion process..")
                        UpdateWorkOrder(work_order_file, update=("meta", "status", 5))
                        # ! process
                        if IntermediateStepSparqlDelete(**kwargs):
                            UpdateWorkOrder(work_order_file, update=("meta", "status", 6))
                            return 6
                        else:
                            msg = "Intermediate deletion step failed"
                            logging.error(msg)
                            print(f"{msg}{boiler_print}")
                            return 5
                    elif work_order['meta']['method'] == "isql":
                        # ! checks
                        expected = ("work_order_file", "named_graph", "isql_path", "user", "password")
                        missing = CheckForParameters(expected, **kwargs)
                        if missing:
                            return missing
                        logger.info(f"Scanned order '{os.path.basename(work_order_file)}' as type 'update', deletion process..")
                        UpdateWorkOrder(work_order_file, update=("meta", "status", 5))
                        # ! process
                        if IntermediateStepISQLDelete(**kwargs):
                            UpdateWorkOrder(work_order_file, update=("meta", "status", 6))
                            return 6
                        else:
                            msg = "Intermediate deletion step failed"
                            logging.error(msg)
                            print(f"{msg}{boiler_print}")
                            return 5
                    else:
                        logger.critical(
                            f"Unknown method '{work_order['meta']['method']}' in work order file {work_order_file}")
            if work_order['meta']['status'] == 7:  # inserting started
                logger.debug(f"Order {work_order_file}: Status 7 detected")
                print(f"Pickuping the order in an 'inbetween' status - {WORK_ORDER_STATUS[work_order['meta']['status']]}")
                if not SoftResetWorkOrder(work_order_file):
                    msg = f"Reseting work order to state {WORK_ORDER_STATUS[work_order['meta']['status']] - 1} failed"
                    print(msg)
                    logger.critical(f"UseWorkOrder > {msg}")
                    return 3
            if work_order['meta']['status'] == 6 or work_order['meta']['status'] == 7:  # intermediate processing done
                logger.debug(f"Order {work_order_file}: Status 6 detected")
                if work_order['meta']['method'] == "isql":
                    logger.debug(f"Order {work_order_file}: Status 6 sorted into isql insert")
                    # ! checks
                    expected = ("work_order_file", "named_graph", "isql_path", "user", "password", "virt_folder")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing:
                        return missing
                    # ! process
                    logger.info(f"Sorted order '{os.path.basename(work_order_file)}' with method 'isql'")
                    UpdateWorkOrder(work_order_file, update=("meta", "status", 7))
                    if FulfillISqlInsertOrder(**kwargs):
                        UpdateWorkOrder(work_order_file, update=("meta", "status", 8))
                        return 8
                    else:
                        msg = "ISQL insert failed"
                        logging.error(msg)
                        print(f"{msg}{boiler_print}")
                        return 7
                elif work_order['meta']['method'] == "sparql":
                    logger.debug(f"Order {work_order_file}: Status 6 sorted into sparql insert")
                    # ! checks
                    expected = ("work_order_file", "named_graph", "sparql_endpoint", "user", "password")
                    missing = CheckForParameters(expected, **kwargs)
                    if missing:
                        return missing
                    # ! process
                    logger.info(f"Sorted order '{os.path.basename(work_order_file)}' with method 'sparql'")
                    UpdateWorkOrder(work_order_file, update=("meta", "status", 7))
                    if FulfillSparqlInsertOrder(**kwargs):
                        UpdateWorkOrder(work_order_file, update=("meta", "status", 8))
                        return 8
                    else:
                        msg = "Sparql based insert operation failed"
                        logger.critical(msg)
                        print(f"{msg}{boiler_print}")
                        return 7
            if work_order['meta']['status'] == 8:  # inserting completed
                logger.debug(f"Order {work_order_file}: Status 8 detected")
                if CleanUpWorkOrder(work_order_file, **kwargs):
                    UpdateWorkOrder(work_order_file, update=("meta", "status", 9))
                    return 9
                else:
                    return 8  # ! this is not all that helpful, like you "cast" this on status 8 and get back status 8, wow
            if work_order['meta']['status'] == 9:  # fulfilled, cleanup done
                logger.debug(f"Order {work_order_file}: Status 9 detected - nothing to do")
                # * do nothing, order finished
                return 9

        except KeyError as key:
            logger.critical(f"The supplied json file doesnt appear to have the needed data, '{key}' was missing")
        except TypeError as e:
            fnc = "UseWorkOrder"
            if e == "'NoneType' object is not subscriptable":  # feels brittle
                msg = "Could not properly load work order file"
                print(msg)
                logging.critical(f"{fnc} > {msg}")
            else:
                msg = f"{e.__class__.__name__}: {e}"
                logging.critical(f"{fnc} > {msg}")
                print(msg)
            return False


def ProcessOrderMultiCore(work_order_file: str, **kwargs):
    """
    Spawns multiple instances of FulfillProcessingOrder to utilize multiple cores when processing data
    :param str work_order_file:
    :type work_order_file:
    :param kwargs:
    :rtype: returns nothing ever
    """
    if 'processes' not in kwargs:
        raise SpchtErrors.WorkOrderInconsitencyError(
            "Cannot call multi core process without defined 'processes' parameter")
    if not isinstance(kwargs['processes'], int):
        raise SpchtErrors.WorkOrderTypeError("Processes must be defined as integer")
    logger.info(
        "Started MultiProcess function, duplicated entries might appear in the log files for each instance of the processing procedure")
    processes = []
    #  mod_kwargs = {}
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
        # del mod_kwargs
        # mod_kwargs = copy.copy(kwargs)
        # mod_kwargs['spcht_object'] = Spcht(kwargs['spcht_object'].descriptor_file)
        time.sleep(
            1)  # ! this all is file based, this is the sledgehammer way of avoiding problems with race conditions
        p = multiprocessing.Process(target=FulfillProcessingOrder, args=(work_order_file,), kwargs=kwargs)
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
        return False


def FetchWorkOrderSolr(work_order_file: str,
                       solr_url: str,
                       query="*:*",
                       total_rows=50000,
                       chunk_size=10000,
                       spcht_object=None,
                       save_folder="./",
                       force=False,
                       **kwargs):
    """
    Utilizes the solr api interface to download data in bulk, uses cursors to continue further into the data
    :param str work_order_file: filename of a work order file
    :param str solr_url: url to an apache solr endpoint, for example: http://<fqdn>/solr/biblio/select
    :param str query: query for the solr '*:*' fetches everything
    :param int total_rows: total amount of featcheable rows, if rows > available rows it will gracefully exit after expending the database
    :param int chunk_size: size per chunk and file in entries
    :param Spcht spcht_object: ready loaded Spcht object, optional, used to limit amount of fetched data
    :param str save_folder: folder where temporary files are saved
    :param bool force: if true, will ignore security checks like order status
    :param kwargs:
    :return: True if everything went well, False if something happened
    :rtype: bool
    """
    # ! some checks for the cli usage
    if not os.path.exists(work_order_file):
        print("Work order does not exists")
        return False
    if not isinstance(spcht_object, Spcht):
        print("Provided Spcht Object is not a genuine Spcht Object")
        return False
    if not isinstance(total_rows, int) or not isinstance(chunk_size, int):
        print("The *Number* of rows and chunk_size must be an integer number")
        return False
    n = math.floor(int(total_rows) / int(chunk_size)) + 1
    # Work Order things:
    work_order = load_from_json(work_order_file)
    # ! Check meta status informations
    if work_order['meta']['status'] > 1 and not force:
        logging.error(
            "Status of work order file is not 1, file is beyond first step and cannot be processed by Solr order")
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

    if 'max_age' in kwargs:  # this means you could technically run a normal insert with max_age
        past_time = datetime.now() - timedelta(minutes=kwargs['max_age'])
        logging.info(
            f"maximum age parameter detected in solr fetch, limiting age of entries to everything younger than {past_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        searchtime = "last_indexed:[" + past_time.strftime("%Y-%m-%dT%H:%M:%SZ") + " TO *]"
        parameters['q'] = f"{parameters['q']} {searchtime}"

    base_path = os.path.join(os.getcwd(), save_folder)
    start_time = time.time()
    logger.info(f"Starting solrdump-like process - Time Zero: {start_time}")
    logger.info(f"Solr Source is {solr_url}")
    #  logger.info(f"Solr query is {parameters['q']}")
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
                file_path = f"{os.path.basename(work_order_file)}_{hash(start_time)}_{i+1}-{n}.json"
                filename = os.path.join(base_path, file_path)
                try:
                    extracted_data = solr_handle_return(data)
                except SpchtErrors.ParsingError as e:
                    logging.error(f"Error while parsing solr return: {e}")
                    return False
                with open(filename, "w") as dumpfile:
                    json.dump(extracted_data, dumpfile)
                file_spec = {"file": os.path.relpath(filename), "status": 2}
                # ? to bring file status in line with order status, files start with 2, logically file_status 1 would be
                # ? 'currently downloading' but this is a closed process so there will be never a partial file with
                # ? status 1
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
        UpdateWorkOrder(work_order_file, update=("meta", "full_download", True),
                        insert=("meta", "solr_finish", datetime.now().isoformat()))
    #  except KeyboardInterrupt:
    #    print(f"Process was interrupted by user interaction")
    #    UpdateWorkOrder(work_order_file, insert=("meta", "completed_chunks", n))
    #    logger.info(f"Process was interrupted by user interaction")
    #    raise KeyboardInterrupt  # necessary cause otherwise the process will be looped when used in main.py
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "FetchWorkOrderSolr"
            print(msg)
            logging.error(f"{fnc} > {msg}")
        return False
    except OSError as e:
        if e.errno == errno.ENOSPC:  # ! i am quite sure that i could not even write log files in this case
            logging.critical("Device Disc reached its limits")
            print("Disc space full", file=sys.stderr)
            exit(9)
        else:
            logger.info(f"Encountered OSError {e.errno}")
            return False

    print(f"Overall Solr fetch executiontime was {delta_now(start_time, 3)} seconds")
    logger.info(f"Overall Executiontime was {delta_now(start_time, 3)} seconds")
    return True


def FulfillProcessingOrder(work_order_file: str, subject: str, spcht_object: Spcht, force=False, **kwargs):
    """
    Processes all raw data files specified in the work order file list
    :param str work_order_file: filename of a work order file
    :param str subject: a part of the subject without identifier  in the <subject> <predicate> <object> chain
    :param Spcht spcht_object: ready loaded Spcht object
    :param bool force: if true, will ignore security checks like order status
    :return: True if everything worked, False if something is not working
    :rtype: boolean
    """
    # * there was some mental discussion whether i use fulfill or fulfil (murican vs british), i opted for the american
    # * way despite my education being british english because programming english is burger english
    # ! checks cause this gets more or less directly called via cli
    if not os.path.exists(work_order_file):
        print("Work order does not exists")
        return False
    if not isinstance(subject, str):
        print("Subject mst be a string")
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
        if work_order0['meta']['status'] < 1 and not force:
            logging.error("Given order file is below status 0, probably lacks data anyway, cannot proceed")
            return False
        if work_order0['meta']['status'] > 3 and not force:
            logging.error("Given order file is above status 3, is already fully processed, cannot proceed")
            return False
        work_order = work_order0
        logger.info(
            f"Starting processing on files of work order '{os.path.basename(work_order_file)}', detected {len(work_order['file_list'])} Files")
        print(f"Start of Spcht Processing - {os.getpid()}")
        _ = 0
        for key in work_order0['file_list']:
            _ += 1
            if work_order['file_list'][key]['status'] == 2:  # Status 2 - Downloaded, not processed
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 3),
                                             insert=('file_list', key, 'processing_start', datetime.now().isoformat()))
                mapping_data = load_from_json(work_order['file_list'][key]['file'])
                quadros = []
                elements = 0
                for entry in mapping_data:
                    try:
                        quader = spcht_object.process_data(entry, subject)
                        elements += 1
                        quadros += quader
                    except SpchtErrors.MandatoryError:
                        logger.info(
                            f"Mandatory field was not found in entry {elements} of file {work_order['file_list'][key]['file']}")

                logger.info(f"Finished file {_} of {len(work_order['file_list'])}, {len(quadros)} triples")
                rdf_dump = f"{work_order['file_list'][key]['file'][:-4]}_rdf.ttl"
                with open(rdf_dump, "w") as rdf_file:
                    rdf_file.write(SpchtDescriptorFormat.SpchtUtility.process2RDF(quadros))  # ? avoiding circular imports
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 4),
                                             insert=[('file_list', key, 'rdf_file', rdf_dump),
                                                     (
                                                     'file_list', key, 'processing_finish', datetime.now().isoformat()),
                                                     ('file_list', key, 'elements', elements),
                                                     ('file_list', key, 'triples', len(quadros))
                                                     ])
        logger.info(f"Finished processing {len(work_order['file_list'])} files and creating turtle files")
        print(f"End of Spcht Processing - {os.getpid()}")
        return True
    except KeyError as key:
        logger.critical(f"The supplied work order doesnt appear to have the needed data, '{key}' was missing")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "FulFillProcessingOrder"
            print(msg)
            logging.error(f"{fnc} > {msg}")
        return False
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Unknown type of exception: '{e}'")
        return False


def IntermediateStepSparqlDelete(work_order_file: str, sparql_endpoint: str, user: str, password: str, named_graph: str,
                                 force=False, **kwargs):
    """
    Deletes all data that has the same subject as any data found in the processed turtle files, uses the sparql interfaced directly
    :param str work_order_file: file path to a work order file
    :param str sparql_endpoint: endpoint for an authenticated sparql interface, the one of virtuoso is /sparql-auth
    :param str user: user for the sparql interface
    :param str password: plain text password for the sparql interface, deleting things is an elevated process
    :param str named_graph: fourth part of the triple where the data resides and will be removed
    :param bool force: if true, will ignore security checks like status
    :param kwargs: additional parameters that all will be ignored but allow the function of the work order principle
    :return: True if everything went well and False if something happened
    :rtype: bool
    """
    # f"WITH <named_graph> DELETE { <subject> ?p ?o } WHERE { <subject> ?p ?o }
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['status'] != 5 and not force:
            logging.error("Order has to be on status 5 when using IntermediateStepSparqlDelete")
            return False
        if work_order0['meta']['type'] != "update":
            logging.error(
                f"Insert type must be 'update' for IntermediateStepSparqlDelete, but is '{work_order0['meta']['type']}'")
            return False
            #  raise SpchtErrors.WorkOrderError(f"Insert type must be 'update' for IntermediateStepSparqlDelete, but is '{work_order0['meta']['type']}'")
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 4:
                logging.info(
                    f"Deleting old entries that match new entries of {work_order['file_list'][key]['rdf_file']}")
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 5),
                                             insert=('file_list', key, 'deletion_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                that_graph = rdflib.Graph()
                that_graph.parse(f_path, format="turtle")
                for evelyn in that_graph.subjects():  # the every word plays continue
                    triples = f"<{evelyn}> ?p ?o. "
                    query = f"WITH <{named_graph}> DELETE {{ {triples} }} WHERE {{ {triples} }}"
                    # * this poses as a major bottleneck as the separate http requests take most of the time for this
                    # * process, i looked into it and apparently there is no easy way to delete a lot of lines with
                    # * sparql cause its technically a read-only language and this whole update/delete shebang seems
                    # * to be an afterthought, you could chain where clauses but that apparent processing time for
                    # * that scales with U^x which seems to be not very desirable
                    status, discard = sparqlQuery(query,
                                                  sparql_endpoint,
                                                  auth=user,
                                                  pwd=password,
                                                  named_graph=named_graph)
                    if not status:
                        return False
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 6),
                                             insert=('file_list', key, 'deletion_finish', datetime.now().isoformat()))
        return True
    # ? boilerplate code from sparql insert
    except KeyError as foreign_key:
        logger.critical(f"Missing key in work order: '{foreign_key}'")
        return False
    except FileNotFoundError as file:
        logger.critical(f"Cannot find file {file}")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "IntermediateSparqlDelete"
            print(msg)
            logging.error(f"{fnc} > {msg}")
        return False


def IntermediateStepISQLDelete(work_order_file: str, isql_path: str, user: str, password: str, named_graph: str,
                               isql_port=1111, force=False, **kwargs):
    """
    Deletes all data that has the same subject as any data found in the processed turtle files. Actually uses sparql
    to fulfill its function but uses those via the isql interface of virtuoso, needs appropriate rights.
    :param str work_order_file: file path to a work order file
    :param str isql_path: path to the isql interface of virtuoso
    :param str user: user for the isql interface
    :param str password: plain text password for the isql interface, deleting things is an elevated process
    :param str named_graph: fourth part of the triple where the data resides and will be removed
    :param int isql_port: port on which the database server for the isql
    :param bool force: if true, will ignore security checks like status
    :param kwargs: additional parameters that all will be ignored but allow the function of the work order principle
    :return: True if everything went well and False if something happened
    :rtype: bool
    """
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['status'] != 5 and not force:
            logging.error("Order has to be on status 5 when using IntermediateStepSparqlDelete")
            return False
        if work_order0['meta']['type'] != "update":
            logging.error(f"Insert type must be 'update' for IntermediateStepSparqlDelete, but is '{work_order0['meta']['type']}'")
            return False
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 4:
                logging.info(f"Deleting old entries that match new entries of {work_order['file_list'][key]['rdf_file']}")
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 5),
                                             insert=('file_list', key, 'deletion_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                that_graph = rdflib.Graph()
                that_graph.parse(f_path, format="turtle")
                for evelyn in that_graph.subjects():  # the every word plays continue
                    triples = f"<{evelyn}> ?p ?o. "
                    query = f"WITH <{named_graph}> DELETE WHERE {{ {triples} }}"
                    # ? when using this you can actually delete without specifying after the DELETE clause, weird
                    subprocess.run([isql_path, str(isql_port), user, password, "VERBOSE=OFF", f"EXEC=sparql {query};"], capture_output=True, check=True)
                    # ? i dont capture any output for subprocess.run cause all that i am interested in is exit code
                    # ? non-zero which will be captures by the thrown exception
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 6),
                                             insert=('file_list', key, 'deletion_finish', datetime.now().isoformat()))
        return True
    # ? boilerplate code from sparql insert
    except KeyError as foreign_key:
        logger.critical(f"Missing key in work order: '{foreign_key}'")
        return False
    except FileNotFoundError as file:
        logger.critical(f"Cannot find file {file}")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Error while running isql interface, exited with non-zero exit-code {e.returncode}\n"
                     f"Message from the program: {e.stderr.decode('ascii').strip()}")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "IntermediateStepISQLDelete"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        return False


def FulfillSparqlInsertOrder(work_order_file: str,
                             sparql_endpoint: str,
                             user: str,
                             password: str,
                             named_graph: str,
                             force=False,
                             **kwargs):
    """
    Inserts read data from the processed turtle files in the triplestore, this should work regardless of what kind of
    triplestore you are utilising.
    :param str work_order_file: file path to a work order file
    :param str sparql_endpoint: endpoint for an authenticated sparql interface, the one of virtuoso is /sparql-auth
    :param str user: user for the sparql interface
    :param str password: plain text password for the sparql interface, inserting things is an elevated process
    :param str named_graph: fourth part of the triple where the data resides and will be removed
    :param bool force: if true, will ignore security checks like status
    :param kwargs: arbitary, additional parameters that all will be ignored
    :return: True if everything went well and False if something happened
    :rtype: bool
    """
    # WITH GRAPH_IRI INSERT { bla } WHERE {};
    SPARQL_CHUNK = 50
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0['meta']['status'] < 4 and not force:
            logger.error("Order hast a status below 4 and might be not fully procssed or fetch, aborting")
            return False
        if work_order0['meta']['status'] > 8 and not force:
            logger.error("This work orders status indicates that its already done, aborting.")
            return False
        if work_order0['meta']['method'] != "sparql":
            raise SpchtErrors.WorkOrderError(
                f"Method in work order file is {work_order0['meta']['method']} but must be 'sparql' for this method")
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 4 or work_order['file_list'][key]['status'] == 6:
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 7),
                                             insert=('file_list', key, 'insert_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                this_graph = rdflib.Graph()
                this_graph.parse(f_path, format="turtle")
                triples = ""
                rounds = 0
                for sub, pred, obj in this_graph:
                    rounds += 1
                    if isinstance(obj, rdflib.term.URIRef):
                        triples += f"<{sub.toPython()}> <{pred.toPython()}> <{obj.toPython()}> . \n"
                    else:
                        if obj.language:
                            annotation = "@" + obj.language
                        elif obj.datatype:
                            annotation = "^^" + obj.datatype
                        else:
                            annotation = ""
                        triples += f"<{sub.toPython()}> <{pred.toPython()}> \"{obj.toPython()}\"{annotation} . \n"
                    # ! TODO: can optimize here, grouped queries
                    if rounds > SPARQL_CHUNK:
                        query = f"""WITH <{named_graph}> INSERT {{ {triples} }}"""
                        # * i have the sneaking suspicion that i defined the named graph twice
                        status, discard = sparqlQuery(query,
                                                      sparql_endpoint,
                                                      auth=user,
                                                      pwd=password,
                                                      named_graph=named_graph)
                        if not status:
                            return False
                        triples = ""
                        rounds = 0
                # END OF FOR LOOP
                if rounds > 0 and triples != "":
                    query = f"""WITH <{named_graph}> INSERT {{ {triples}}}"""
                    status, discard = sparqlQuery(query,
                                                  sparql_endpoint,
                                                  auth=user,
                                                  pwd=password,
                                                  named_graph=named_graph)
                    if not status:
                        return False
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 8),
                                             insert=('file_list', key, 'insert_finish', datetime.now().isoformat()))
        return True
    except KeyError as foreign_key:
        logger.critical(f"Missing key in work order: '{foreign_key}'")
        return False
    except FileNotFoundError as file:
        logger.critical(f"Cannot find file {file}")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "FulFillSparqlInsertOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        return False
    except xml.parsers.expat.ExpatError as e:
        logger.error(f"Parsing of triple file failed: {e}")
        return False


def FulfillISqlInsertOrder(work_order_file: str,
                           isql_path: str,
                           user: str,
                           password: str,
                           named_graph: str,
                           isql_port=1111,
                           virt_folder="/tmp/",
                           force=False,
                           **kwargs):  # ! random kwarg is so i can enter more stuff than necessary that can be ignored
    """
    This utilizes the virtuoso bulk loader enginer to insert the previously processed data into the
    virtuoso triplestore. For that it copies the files with the triples into a folder that virtuoso
    accepts for this kind of input, those folders are usually defined in the virtuoso.ini. it then
    manually calls the isql interface to put the file into the bulk loader scheduler, and, if done
    so deleting the copied file. For now the script has no real way of knowing if the operation actually
    succeeds. Only the execution time might be a hint, but that might vary depending on system load
    and overall resources.
    :param str work_order_file: filename of the work order that is to be fulfilled, gets overwritten often
    :param dict work_order: initial work order loaded from file
    :param str isql_path: path to the virtuoso isql-v/isql executable
    :param str user: name of a virtuoso user with enough rights to insert
    :param str password: clear text password of the user from above
    :param str named_graph: named graph the data is to be inserted into
    :param int isql_port: port of the virtuoso sql database, usually 1111
    :param str virt_folder: folder that virtuoso accepts as input for files, must have write
    :param bool force: if true, will ignore security checks like status
    :return: True if everything went "great"
    :rtype: Bool
    """
    try:
        work_order0 = load_from_json(work_order_file)
        if work_order0 is None:
            return False
        if work_order0['meta']['status'] < 4 and not force:
            logger.error("Order hast a status below 4 and might be not fully procssed or fetch, aborting")
            return False
        if work_order0['meta']['status'] > 8 and not force:
            logger.error("This work orders status indicates that its already done, aborting.")
            return False
        work_order = work_order0
        for key in work_order0['file_list']:
            if work_order['file_list'][key]['status'] == 4 or work_order['file_list'][key]['status'] == 6:
                work_order = UpdateWorkOrder(work_order_file,
                                             update=('file_list', key, 'status', 7),
                                             insert=('file_list', key, 'insert_start', datetime.now().isoformat()))
                f_path = work_order['file_list'][key]['rdf_file']
                f_path = shutil.copy(f_path, virt_folder)
                command = f"EXEC=ld_add('{f_path}', '{named_graph}');"
                zero_time = time.time()
                subprocess.run([isql_path, str(isql_port), user, password, "VERBOSE=OFF", command,
                                "EXEC=rdf_loader_run();","EXEC=checkpoint;"],
                               capture_output=True, check=True)
                # ? see IntermediateISQLDelete for decision process about this
                logger.debug(f"Executed ld_add command via isql, execution time was {delta_now(zero_time)}")
                # ? apparently i cannot really tell if the isql stuff actually works
                if os.path.exists(f_path):
                    os.remove(f_path)
                # reloading work order in case something has changed since then
                work_order = UpdateWorkOrder(work_order_file, update=('file_list', key, 'status', 8),
                                             insert=('file_list', key, 'insert_finish', datetime.now().isoformat()))
        logger.info(f"Successfully called {len(work_order['file_list'])} times the bulk loader")
        return True
    except KeyError as foreign_key:
        logger.critical(f"Missing key in work order: '{foreign_key}'")
        return False
    except PermissionError as folder:
        logger.critical(f"Cannot access folder {folder} to copy turtle into.")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "FulFillSqlInsertOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Error while running isql interface, exited with non-zero exit-code {e.returncode}\n"
                     f"Message from the program: {e.stderr.decode('ascii').strip()}")
        return False
    except FileNotFoundError as file:
        logger.critical(f"Cannot find file {file}")
        return False


def CleanUpWorkOrder(work_order_filename: str, force=False, files=('file', 'rdf_file'), **kwargs):
    """
    Removes all files referenced in the work order file from the filesystem if the processing state
    necessary is reached
    :param str work_order_filename: file path to a work order file
    :param bool force: If set to true disregards meta status checks and deletes everything it touches
    :param files: dictionary keys in the 'file_list' part that get deleted
    :return: True if everything went smoothly, False if not.
    """
    if force:
        logger.info("Force mode detected, will delete everything regardless of status")
    try:
        work_order_0 = load_from_json(work_order_filename)
        # ? Work Order Status 8 - Inserting done, this achieves Step 9 "Clean up done"
        if work_order_0['meta']['status'] < 7 and not force:
            logger.error("Status of order indicates fulfillment, aborting.")
            return False
        if work_order_0['meta']['status'] > 8 and not force:
            logger.error("Status of order indicates fulfillment, aborting.")
            return False
        _ = 0
        for key in work_order_0['file_list']:
            # * for each entry in the part list
            if work_order_0['file_list'][key]['status'] == 8 or force:
                wo_update = []  # i could just call update work order twice
                for fileattr in files:
                    # * slightly complicated method to allow for more files (for whatever reason)
                    one_file = work_order_0['file_list'][key].get(fileattr)

                    if one_file:
                        try:
                            os.remove(one_file)
                            wo_update.append(('file_list', key, fileattr))
                        except OSError as e:
                            if e.errno == errno.ENOENT:
                                logger.info(
                                    f"Removing of '{fileattr}' failed cause the referenced file '{one_file}' ALREADY GONE")
                            elif e.errno == errno.EPERM or e.errno == errno.EACCES:
                                logger.info(
                                    f"Removing of '{fileattr}' failed cause ACCESS to the referenced file '{one_file}' is not possible")
                            elif e.errno == errno.EISDIR:
                                logger.info(
                                    f"Removing of '{fileattr}' failed cause the referenced file '{one_file}' is a DIRECTORY")
                            else:
                                logger.error(
                                    f"Generic, unexpected error while deleting '{fileattr}', filename '{one_file}'")
                if len(wo_update) > 0:
                    UpdateWorkOrder(work_order_filename, delete=wo_update, update=('file_list', key, 'status', 9))
                else:
                    logger.error(
                        f"On Cleaup of {work_order_filename}:{key} nothing could be deleted, status remained on 8")
                # funny, in the end i do nothing with the work order cause the action was to handle the work order, not
                # doing things. Twisted sense of humour
        return True
        # ? it might be an idea to actually update the meta data status as well but i did in all the other functions so
        # ? that that value is explicitly handled by another function

    except KeyError as key:
        print(f"Key missing {key}")
        logger.critical(f"Missing key in work order: '{key}'")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "CleanUpWorkOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        return False


def HardResetWorkOrder(work_order_file: str, **kwargs):
    """
    Resets the work order to the last stable status according to the meta>status position, deletes files and entries
    relative to that. Like deleting processed files and the timings of that processing
    :param str work_order_file: file path to a work order file
    :param kwargs:
    :return: True if everything was successful
    :rtype: bool
    """
    work_order = load_from_json(work_order_file)
    try:
        status = work_order['meta']['status']  # prevents me from writing this a thousand time over..and its cleaner
        if status == 1:  # downloads are basically unrecoverable cause we dont know how much is missing
            CleanUpWorkOrder(work_order_file, force=True, files=('rdf_file', 'file'))
            UpdateWorkOrder(work_order_file,
                            update=[('file_list', {}), ('meta', 'status', 0)],
                            delete=[('meta', 'solr_start'), ('meta', 'solr_finish'), ('meta', 'full_download'),
                                    ('meta', 'spcht_user')],
                            force=True)  # sets to empty list
            # what i dont like is that i have like X+1 file operations but in the grand scheme of things it probably
            # doesnt matter. There is some thinking of just doing all this in an sqlite database
            return True
        if status == 3:  # processing started
            CleanUpWorkOrder(work_order_file, force=True, files=('rdf_file'))
            UpdateWorkOrder(work_order_file, update=('meta', 'status', 2))
            fields = ('processing_start', 'processing_finish', 'elements', 'triples')
        elif status == 5:  # post-processing started
            UpdateWorkOrder(work_order_file, update=('meta', 'status', 4))
            fields = ('deletion_start', 'deletion_finish')
        elif status == 7:  # inserting started
            UpdateWorkOrder(work_order_file, update=('meta', 'status', 6))
            fields = ('insert_start', 'insert_finish')
        else:
            print("No resetable status, this defaults to a success")
            return True

        # * generic field purge
        if status == 3 or status == 5 or status == 7:
            work_order0 = load_from_json(work_order_file)  # reload after deleting things
            work_order = work_order0.copy()
            for each in work_order['file_list']:
                for that_field in fields:
                    work_order0['field_list'][each].pop(that_field, None)
            with open(work_order_file, "w") as open_file:
                json.dump(work_order, open_file, indent=4)
        return True
    except KeyError as key:
        print(f"Key missing {key}")
        logger.critical(f"Missing key in work order: '{key}'")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "HardResetWorkOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        else:
            print(f"Generic TypeError: {e}")
        return False
    except OSError:
        print(f"Generic OSError while reseting work order file")
        return False


def SoftResetWorkOrder(work_order_file: str, **kwargs):
    """
    Instead of reseting to the "big" status like HardResetWorkOrder this only goes through filelist and resets to the
    previous file wise state. This function is receipe for disaster if some other process is still working on the file
    this is probably the point where i should have utilized a file lock.
    the individual files
    :param str work_order_file: file path to a work order file
    :type work_order_file:
    :param kwargs:
    :return: True if everything went alright
    :rtype: bool
    """
    # ? i thought about how fine this function should be, what if somewhen in the future some weirdo fucks up a work
    # ? order that big time that there are like all status that are possible in one single file? But actually, that
    # ? should not happen under normal circumstances, you only advance if all sub-status are done for that meta
    # ? status, so why worry about something that someone probably jerry-rigged to death anyway, that person can write
    # ? their own function to fix those cases. This only fixes according to meta status and that's it
    # * as a side note: 'Jury-rigged' assembled quickly with the materials at hand
    # * 'Jerry-built' = cheaply or poorly built, comes from nautical term 'jury' = 'makeshift', 'temporary'
    # * a not-one amount of status is status, statuses would be also correct
    # english is fascinating me every waking hour, such an inconsistent language
    work_order = load_from_json(work_order_file)
    try:
        status = work_order['meta']['status']
        list_of_updates = []
        list_of_deletes = []
        if status == 1:  # fetch state cannot be repaired in a meaningful way:
            return HardResetWorkOrder(work_order_file,
                                      **kwargs)  # ? i dont know why i even bother to push the kwargs with it
        elif status == 3:  # processing started, resets unfinished processes
            for each in work_order['file_list']:
                if work_order['file_list'][each]['status'] == 3:
                    # of all the deletes only processing_start makes sense, but i skirt around some freak case here
                    # so i rather do it properly, the time lost _should_ never matter for 3 dict operations
                    list_of_deletes.append(('file_list', each, 'processing_start'))
                    list_of_deletes.append(('file_list', each,
                                            'processing_finish'))  # why should it be finished but status 3? anyway, away with that
                    list_of_deletes.append(('file_list', each, 'elements'))
                    list_of_deletes.append(('file_list', each, 'triples'))
                    list_of_updates.append(('file_list', each, 'status', 2))
        elif status == 5:  # intermediate, post-processing was started but not finished
            for each in work_order['file_list']:
                if work_order['file_list'][each]['status'] == 5:
                    list_of_deletes.append(('file_list', each, 'deletion_start'))
                    list_of_deletes.append(('file_list', each, 'deletion_finish'))
                    list_of_updates.append(('file_list', each, 'status', 4))
        elif status == 7:
            for each in work_order['file_list']:
                if work_order['file_list'][each]['status'] == 7:
                    list_of_deletes.append(('file_list', each, 'insert_start'))
                    list_of_deletes.append(('file_list', each, 'insert_finish'))
                    list_of_updates.append(('file_list', each, 'status', 6))
        else:
            logger.info("Cannot soft reset anything.")
            return True
        UpdateWorkOrder(work_order_file, update=list_of_updates, delete=list_of_deletes, force=True)

        return True

    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "SoftResetWorkOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        else:
            logger.error(f"SoftResetWorkOrder: Generic TypeError occured {e}")
            print(f"Generic TypeError: {e}")
        return False
    except Exception as e:
        logger.critical(f"unexpected, uncaught exception happend, {e.__class__.__name__}: '{e}'")
        print(e)  # this text lies, technically it was of course caught, otherwise there would be no log of it
        return


def PurgeWorkOrder(work_order_file: str, **kwargs):
    """
    Simply resets an existing work order to status 0 by rewriting it
    :param str work_order_file: file path to a work order file
    :param kwargs: varios parameters taht all get ignored. Just there for compatiblity reasons
    :return: True if file writing succeeded
    :rtype: Bool
    """
    old_work_order = load_from_json(work_order_file)
    try:
        meta = old_work_order['meta']
        return CreateWorkOrder(work_order_file, meta['fetch'], meta['type'], meta['method'])
    except KeyError as key:
        print(f"Key missing {key}")
        return False
    except TypeError as e:
        if e == "'NoneType' object is not subscriptable":  # feels brittle
            msg = "Could not properly load work order file"
            fnc = "PureWorkOrder"
            print(msg)
            logger.critical(f"{fnc} > {msg}")
        return False
