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
import copy
import logging
import sys
import re
import os
import json
import SpchtUtility
import WorkOrder

from SpchtDescriptorFormat import Spcht
from local_tools import sparqlQuery
from foliotools.foliotools import additional_remote_data, part1_folio_workings, grab, find, create_single_location, create_hash, check_location_changes, check_opening_changes, create_location_node

import foliotools.folio2triplestore_config as secret

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

append = "?limit=1000"


def location_update():
    if os.path.exists(secret.hash_file):
        try:
            with open(secret.hash_file, "r") as hash_file:
                data = json.load(hash_file)
        except json.JSONDecodeError as e:
            logging.warning("Hash File could not be decoded, json error: " + str(e))
            exit(1)
        except FileNotFoundError:
            logging.warning("Hash File coult not be 'found' despite previous check. Suspicious")
            exit(2)
        changed = check_location_changes(data)
        if not changed:
            logging.info("Check completed without any found changes, hibernating...")
            exit(0)


def opening_update():
    if os.path.exists(secret.hash_file):
        try:
            with open(secret.hash_file, "r") as hash_file:
                data = json.load(hash_file)
        except json.JSONDecodeError as e:
            logging.warning("Hash File could not be decoded, json error: " + str(e))
            exit(1)
        except FileNotFoundError:
            logging.warning("Hash File coult not be 'found' despite previous check. Suspicious")
            exit(2)
        changed = check_opening_changes(data)
        if not changed:
            logging.info("Check completed without any found changes, hibernating...")
            exit(0)
        # delete old entries, create anew
        heron = Spcht(secret.anti_opening_spcht)
        triples = []
        for negative in changed:
            triples += heron.process_data(negative, "https://matterless")
            data['opening'][negative['loc_main_service_id']] = create_hash(negative['openingHours'], "opening")

        for obj in triples:
            query = f"""DELETE 
                        {{ GRAPH <{secret.named_graph}>
                            {{ {obj.sobject} <https://schema.org/openingHoursSpecification> ?o }}
                        }}
                        WHERE {{ GRAPH <{secret.named_graph}>
                            {{ {obj.sobject} <https://schema.org/openingHoursSpecification> ?o }}
                            }};"""
            status, discard = sparqlQuery(query,
                                          secret.sparql_url,
                                          auth=secret.triple_user,
                                          pwd=secret.triple_password,
                                          named_graph=secret.named_graph)
        part3_spcht_workings(changed, secret.delta_opening_spcht)
        with open(secret.hash_file, "w") as hash_file:
            json.dump(data, hash_file, indent=3)
    else:
        full_update()


def part3_spcht_workings(extracted_dicts, spcht_descriptor_path):
    duck = Spcht(spcht_descriptor_path)
    triples = []
    for each_entry in extracted_dicts:
        triples += duck.process_data(each_entry, secret.subject)
    temp_file_name = secret.turtle_file
    with open(temp_file_name, "w") as rdf_file:
        rdf_file.write(SpchtUtility.process2RDF(triples))  # ? avoiding circular imports
    work_order = {
        "meta": {
            "status": 4,
            "fetch": "local",
            "type": "insert",
            "method": secret.processing,
            "full_download": True
        },
        "file_list": {
            "0": {
                "rdf_file": secret.turtle_file,
                "status": 4
            }
        }
    }
    # TODO: we have here a usecase for workorder fileIO
    with open(secret.workorder_file, "w") as work_order_file:
        json.dump(work_order, work_order_file)
    res = WorkOrder.FulfillSparqlInsertOrder(secret.workorder_file, secret.sparql_url, secret.triple_user,
                                             secret.triple_password, secret.named_graph)
    logging.info(f"WorkOrder Fullfilment, now status: {res}")
    return res


def full_update():
    # ! part 1 - download of raw data
    dumping_dict = {}
    for key, endpoint in secret.endpoints.items():
        temp_data = part1_folio_workings(endpoint, key, append)
        if temp_data:
            dumping_dict.update(temp_data)
    # ! part 2 - packing data
    raw_info = dumping_dict
    hashes = {'loc': {}, 'opening': {}, 'raw': {}}
    if raw_info:
        extracted_dicts = []
        for each in raw_info['locations']:
            if re.search(secret.name, each['code']):
                inst = grab(raw_info['locinsts'], "id", each['institutionId'])
                lib = grab(raw_info['loclibs'], "id", each['libraryId'])
                one_node, location_hash, opening_hash, raw_data = create_location_node(each, inst, lib)
                extracted_dicts.append(one_node)
                hashes['loc'][each['id']] = location_hash
                hashes['opening'].update(opening_hash)
                hashes['raw'].update(raw_data)

        with open(secret.hash_file, "w") as hashing_file:
            json.dump(hashes, hashing_file, indent=3)
    else:
        logging.warning("No data to work on")
        print("Loading failed, cannot create what is needed")
        exit(0)
    # ! part 3 - SpchtWorkings
    if not part3_spcht_workings(extracted_dicts, secret.foliospcht):
        os.remove(secret.hash_file)


if __name__ == "__main__":
    #full_update()
    opening_update()
    #location_update()
