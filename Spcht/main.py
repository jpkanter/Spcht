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

#  connect to solr database, retrieves data in chunks and inserts those via sparql into virtuoso

# "global" variables for some things
import argparse
import json
import sys
import logging

import Spcht.Core.WorkOrder as WorkOrder
import Spcht.Utils.local_tools as local_tools
from Spcht.Utils.local_tools import load_from_json
from Spcht.Utils.main_arguments import arguments
from Spcht.Core.SpchtCore import Spcht

try:
    from termcolor import colored  # only needed for debug print
except ModuleNotFoundError:
    def colored(text, *args, **kwargs):
        return text  # throws args away returns non colored text

__VERSION__ = "0.8"

PARA = {}
# DEBUG file + line = [%(module)s:%(lineno)d]
logging.basicConfig(filename='spcht_process.log', format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.INFO)
# logging.basicConfig(filename='spcht_process.log', format='[%(asctime)s] %(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)  # Python 3.9


def load_config(file_path="config.json"):
    """
    Simple config file loader, will raise exceptions if files arent around, will input parameters
    in global var PARA
    :param file_path str: file path to a flat json containing a dictionary with key-value relations
    :return: True if everything went well, will raise exception otherwise
    """
    global PARA
    expected_settings = ("solr_url", "query", "total_rows", "chunk_size", "spcht_path", "save_folder",
                         "subject", "named_graph", "isql_path", "user", "password", "isql_port", "virt_folder",
                         "processes", "sparql_endpoint", "spcht_descriptor", "max_age")
    config_dict = load_from_json(file_path)
    if not config_dict:
        return False
        #raise SpchtErrors.OperationalError("Cannot load config file")
    for setting_name in config_dict:
        if setting_name in expected_settings and config_dict[setting_name] != "":
            PARA[setting_name] = config_dict[setting_name]
    return True


if __name__ == "__main__":
    logging.debug("Start of script")
    print(f"Solr2Triplestore Bridge Version {__VERSION__}. Execute with '-h' for full cli command list.")
    parser = argparse.ArgumentParser(
        description="Solr2Triplestore bridge. Converts 1-dimensional data from a apache solr to LOD and inserts it into a triplestore, optimized for OpenLink Virtuoso.",
        usage="main.py --FullOrder NAME FETCH TYPE METHOD [--config CONFIG]",
        epilog="Individual settings overwrite settings from the config file",
        prefix_chars="-")
    # ? extending the parser registry so we can actually add data types from json
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

    args = parser.parse_args()
    # ! +++ CONFIG FILE +++
    if args.config:
        cfg_status = load_config(args.config)
        if not cfg_status:
            print("Loading of config file went wrong")
        else:
            print("Config file loaded")

    simple_parameters = ["work_order_file", "solr_url", "query", "chunk_size", "total_rows", "spcht_descriptor", "save_folder",
                         "subject", "named_graph", "isql_path", "user", "password", "virt_folder", "sparql_endpoint", "force",
                         "debug"]
    default_parameters = ["chunk_size", "total_rows", "isql_port", "save_folder"]  # ? default would overwrite config file settings

    for arg in vars(args):
        if arg in simple_parameters and getattr(args, arg) is not None:
            if arg in default_parameters and getattr(args, arg) == arguments[arg]['default']:
                pass  # i was simply to lazy to write the "not" variant of this
            else:
                PARA[arg] = getattr(args, arg)

    if args.CreateOrder:
        par = args.CreateOrder
        order_name = WorkOrder.CreateWorkOrder(par[0], par[1], par[2], par[3])
        print(f"Created Order '{order_name}'")

    # ! FETCH OPERATION
    if args.FetchSolrOrder:
        par = args.FetchSolrOrder
        ara = Spcht(par[5])  # ? Ara like the bird, not a misspelled para as one might assume
        status = WorkOrder.FetchWorkOrderSolr(par[0], par[1], par[2], int(par[3]), int(par[4]), ara, par[5])
        if not status:
            print("Process failed, consult log file for further details")

    if args.FetchSolrOrderPara:
        expected = ("work_order_file", "solr_url", "query", "total_rows", "chunk_size", "spcht_descriptor", "save_folder")
        for each in expected:
            if each not in PARA:
                print("FetchSolrOrderPara - simple solr dump procedure")
                print("All parameters have to loaded either by config file or manually as parameter")
                for avery in expected:
                    print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                exit(1)
        big_ara = Spcht(PARA['spcht_descriptor'])
        status = WorkOrder.FetchWorkOrderSolr(PARA['work_order_file'], PARA['solr_url'], PARA['query'], PARA['total_rows'], PARA['chunk_size'], big_ara, PARA['save_folder'])
        if not status:
            print("Process failed, consult log file for further details")

    # ! PROCESSING OPERATION

    if args.SpchtProcessing:
        par = args.SpchtProcessing
        heron = Spcht(par[2])
        if not heron:
            print("Loading of Spcht failed, aborting")
            exit(1)
        status = WorkOrder.FulfillProcessingOrder(par[0], par[1], heron)
        if not status:
            print("Something went wrong, check log file for details")

    if args.SpchtProcessingPara:
        expected = ("work_order_file", "spcht_descriptor", "subject")
        for each in expected:
            if each not in PARA:
                print("SpchtProcessingPara - linear processed data")
                print("All parameters have to loaded either by config file or manually as parameter")
                for avery in expected:
                    print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                exit(1)
        crow = Spcht(PARA['spcht_descriptor'])
        status = WorkOrder.FulfillProcessingOrder(PARA['work_order_file'], PARA['subject'], crow)
        if not status:
            print("Something went wrong, check log file for details")

    if args.SpchtProcessingMulti:
        par = args.SpchtProcessingMulti
        dove = Spcht(par[2])
        if dove:
            print("Spcht loading failed")
            exit(1)
        WorkOrder.ProcessOrderMultiCore(par[0], graph=par[1], spcht_object=dove, processes=int(par[3]))
        # * multi does not give any process update, it just happens..or does not, it might print something to console

    if args.SpchtProcessingMultiPara:
        expected = ("work_order_file", "spcht_descriptor", "subject", "processes")
        for each in expected:
            if each not in PARA:
                print("SpchtProcessingMultiPara - parallel processed data")
                print("All parameters have to loaded either by config file or manually as parameter")
                for avery in expected:
                    print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                exit(1)
        eagle = Spcht(PARA['spcht_descriptor'])
        WorkOrder.ProcessOrderMultiCore(PARA['work_order_file'], graph=PARA['subject'], spcht_object=eagle, processes=PARA['processes'])

    # ! inserting operation

    if args.InsertISQLOrder:
        par = args.SpchtProcessingMulti
        print("Starting ISql Order")
        # ? as isql_port is defaulted this parameter can only be accessed by --isql_port and not in one line with the order
        status = WorkOrder.FulfillISqlInsertOrder(work_order_file=par[0], named_graph=par[1], isql_path=par[2],
                                                  user=par[3], password=par[4], virt_folder=par[5], isql_port=PARA['isql_port'])
        if status:
            print("ISQL Order finished, no errors returned")
        else:
            print("Something went wrong with the ISQL Order, check log files for details")

    if args.InsertISQLOrderPara:
        expected = ("work_order_file", "named_graph", "isql_path", "user", "password", "virt_folder")
        for each in expected:
            if each not in PARA:
                print("InsertISQLOrderPara - inserting of data via iSQL")
                print("All parameters have to loaded either by config file or manually as parameter")
                for avery in expected:
                    print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                exit(1)
        status = WorkOrder.FulfillISqlInsertOrder(work_order_file=PARA['work_order_file'], named_graph=PARA['named_graph'],
                                                  isql_path=PARA['isql_patch'], user=PARA['user'],
                                                  password=PARA['password'], virt_folder=PARA['virt_folder'], isql_port=PARA['isql_port'])
        if status:
            print("ISQL Order finished, no errors returned")
        else:
            print("Something went wrong with the ISQL Order, check log files for details")

    # ! automatic work order processing

    if args.HandleWorkOrder:
        if 'spcht_descriptor' in PARA:
            bussard = Spcht(PARA['spcht_descriptor'])
            PARA['spcht_object'] = bussard
        status = WorkOrder.UseWorkOrder(args.HandleWorkOrder[0], **PARA)
        if isinstance(status, list):
            print("Fulfillment of current Work order status needs further parameters:")
            for avery in status:
                print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
        elif isinstance(status, int):
            print(f"Work order advanced one step, new step is now {status}")
            WorkOrder.CheckWorkOrder(args.HandleWorkOrder[0])
        else:
            print(status)

    if args.ContinueWorkOrder:
        print("Continuing of an interrupted/paused order")
        try:
            for i in range(0, 6):
                res = WorkOrder.UseWorkOrder(args.ContinueWorkOrder, **PARA)
                old_res = -1
                if isinstance(res, int):
                    if i > 0:
                        old_res = res
                    if res == 9:
                        print("Operation finished successfully")
                        WorkOrder.CheckWorkOrder(args.ContinueWorkOrder)
                        exit(0)
                    if old_res == res:
                        print("Operation seems to be stuck on the same status, something is broken. Advising investigation")
                        WorkOrder.CheckWorkOrder(args.ContinueWorkOrder)
                        exit(2)
                    print(local_tools.WORK_ORDER_STATUS[res])
                elif isinstance(res, list):
                    print("Fulfillment of current Work order status needs further parameters:")
                    for avery in res:
                        print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                    break
                else:
                    print("Some really weird things happened, procedure reported an unexpeted status", file=sys.stderr)
        except KeyboardInterrupt:
            print("Process was aborted by user, use --ContinueWorkOrder WORK_ORDER_NAME to continue")
            exit(0)

    if args.FullOrder:
        # ? notice for needed parameters before creating work order
        dynamic_requirements = []
        par = args.FullOrder
        if par[1].lower() == "solr":
            dynamic_requirements.append("solr_url")
            dynamic_requirements.append("chunk_size")
            dynamic_requirements.append("query")
            dynamic_requirements.append("total_rows")
        else:
            print(par)
            print(colored("Only fetch method 'solr' is allowed", "red"))
            exit(1)
        # * Processing Type
        if par[2].lower() == "insert" or par[2].lower() == "update":
            dynamic_requirements.append("spcht_descriptor")
            dynamic_requirements.append("subject")
            if par[2].lower() == "update":
                dynamic_requirements.append("max_age")
        else:
            print(colored("Only processing types 'update' and 'insert' are allowed"))
        if par[2].lower() == "update":
            dynamic_requirements.append("sparql_endpoint")
            dynamic_requirements.append("user")
            dynamic_requirements.append("password")
            dynamic_requirements.append("named_graph")
        # * Insert Method
        if par[3].lower() == 'sparql':
            dynamic_requirements.append("sparql_endpoint")
            dynamic_requirements.append("user")
            dynamic_requirements.append("password")
            dynamic_requirements.append("named_graph")
        elif par[3].lower() == 'isql':
            dynamic_requirements.append("isql_path")
            dynamic_requirements.append("user")
            dynamic_requirements.append("password")
            dynamic_requirements.append("named_graph")
            dynamic_requirements.append("virt_folder")
        else:
            print(colored("Only insert methods 'sparql' and 'isql' are allowed"))
        # * delete duplicates
        dynamic_requirements = list(set(dynamic_requirements))
        for each in dynamic_requirements:
            if each not in PARA:
                print("FullOrder - full process from start to finish")
                print("Based on the described work order properties the following parameters are needed")
                print("All parameters have to loaded either by config file or manually as --parameter")
                print(f"Parameter {each} was missing")
                print(colored(PARA, "yellow"))
                print(colored(dynamic_requirements, "blue"))
                for avery in dynamic_requirements:
                    print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                exit(1)

        seagull = Spcht(PARA['spcht_descriptor'])
        print(seagull)
        if not seagull:
            print("Spcht loading failed")
            exit(1)
        PARA['spcht_object'] = seagull
        try:
            old_res = 0
            work_order = WorkOrder.CreateWorkOrder(par[0], par[1], par[2], par[3])
            print("Starting new FullOrder, this might take a long while, see log and worker file for progress")
            print(f"Work order file: '{work_order}'")
            for i in range(0, 6):
                if i > 0:
                    old_res = res
                res = WorkOrder.UseWorkOrder(work_order, **PARA)
                if isinstance(res, list):  # means a list was returned that specifies needed parameters
                    print(colored("This should not have been happened, inform creator of this tool", "red"))
                    # this should not have had happen cause we already checked for all parameters
                    print("Fulfillment of current Work order status needs further parameters:")
                    for avery in res:
                        print(f"\t{colored(avery, attrs=['bold'])} - {colored(arguments[avery]['help'], 'green')}")
                    break
                elif not isinstance(res, list) and not isinstance(res, int):
                    print("Process encountered a critical, unexpected situation, aborting", file=sys.stderr)
                    exit(0)
                if res == 9:
                    print("Operation finished successfully")
                    WorkOrder.CheckWorkOrder(args.ContinueWorkOrder)
                    exit(0)
                if old_res == res:
                    print("Operation seems to be stuck on the same status, something is broken. Advising investigation")
                    WorkOrder.CheckWorkOrder(work_order)
                    exit(2)
                print(local_tools.WORK_ORDER_STATUS[res])
        except KeyboardInterrupt:
            print("Process was aborted by user, use --ContinueWorkOrder WORK_ORDER_NAME to continue")
            exit(0)

    # ? Utility Things

    if args.CheckWorkOrder:
        status = WorkOrder.CheckWorkOrder(args.CheckWorkOrder[0])
        if not status:
            print("Given work order file path seems to be wrong")

    if args.CleanUp:
        if WorkOrder.CleanUpWorkOrder(args.CleanUp, **PARA):
            print("Clean up sequence finished successfully")
        else:
            print("Clean up sequence encountered an error and might be not fully finished")

    if args.environment:
        print(colored("Available data through config and direct parameters", attrs=["bold"]))
        for keys in PARA:
            if keys == "password":
                print(f"\t{keys:<12}\t{'*'*12}")
            else:
                print(f"\t{keys:<12}\t{PARA[keys]}")

    if args.CheckFields:
        debugmode = False
        if args.debug:  # 3 lines..there must be a more elegant way to do this right?
            debugmode = True
        print(f"Loading Spcht Descriptor File {args.CheckFields}")
        try:
            rolf = Spcht(args.CheckFields, debug=debugmode)
            print(rolf.get_node_fields())
        except FileNotFoundError:
            print("Designated file could not be found")

    if args.CompileSpcht:
        debugmode = False
        if args.debug:
            debugmode = True
        sperber = Spcht(args.CompileSpcht[0], debug=debugmode)
        sperber.export_full_descriptor(args.CompileSpcht[1])
        print(colored("Succesfully compiled spcht, file:", "cyan"), args.CompileSpcht[1])

    if args.CheckSpcht:
        debugmode = False
        if args.debug:
            debugmode = True
        try:
            with open(args.CheckSpcht, "r") as file:
                testdict = json.load(file)
        except json.decoder.JSONDecodeError as e:
            print(f"JSON Error: {str(e)}", file=sys.stderr)
            exit(2)
        except FileNotFoundError as e:
            print(f"File not Found: {str(e)}", file=sys.stderr)
            exit(1)
        taube = Spcht(debug=debugmode)
        if taube.load_descriptor_file(args.CheckSpcht):
            print("Spcht Discriptor could be succesfully loaded, everything should be okay")
            exit(0)
        else:
            print("There was an Error loading the Spcht Descriptor")

    # +++ SPCHT Compile

