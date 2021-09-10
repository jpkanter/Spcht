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
import shutil
import subprocess
import sys
import re
import os
import pytz
import requests
import json
import urllib3
import hashlib
import SpchtUtility
import WorkOrder
from datetime import datetime
from SpchtDescriptorFormat import Spcht
from local_tools import sparqlQuery

import folio2triplestore_config as secret

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

append = "?limit=1000"

endpoints = {
    "library": "/location-units/libraries",
    "campus": "/location-units/campuses",
    "institution": "/location-units/institutions",
    "service": "/service-points",
    "locations": "/locations"
}


folio_header = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Okapi-Tenant": secret.XOkapiTenant,
    "X-Okapi-Token": secret.XOkapiToken
}


def grab(a_list, dict_attr, dict_value):
    for each in a_list:
        if dict_attr in each and each[dict_attr] == dict_value:
            return each
    return None


def find(big_dictionary: dict, searched_value: str):
    """
    Returns the sub dictionary that contains the searched string as key one level below
    :param dict big_dictionary:
    :param str searched_value:
    :return:
    :rtype:
    """
    for some_key, value in big_dictionary.items():
        if isinstance(value, (str, int, float, complex)):
            if value == searched_value:
                return big_dictionary
        if isinstance(value, dict):
            deeper = find(value, searched_value)
            if deeper:
                return copy.deepcopy(value)
    return {}


def create_hash(data: dict, variant):
    # definitely one of my more naive methods
    if variant == "loc":
        try:
            hasheable = data['id'] + data['name'] + data['code'] + data['discoveryDisplayName'] \
                        + data['institutionId'] + data['campusId'] + data['libraryId'] + data['primaryServicePoint'] \
                        + secret.subject + secret.named_graph
            sha_1 = hashlib.sha1()
            sha_1.update(hasheable.encode())
            return sha_1.hexdigest()
        except KeyError:
            logging.info(f"Hashing of Location {data.get('name', 'unknown')} failed.")
            return ""
    elif variant == "opening":
        try:
            hasheable = ""
            for day in data:
                hasheable += day['weekdays']['day']
                hasheable += str(day['openingDay'])
            sha_1 = hashlib.sha1()
            sha_1.update(hasheable.encode())
            return sha_1.hexdigest()
        except KeyError:
            logging.info(f"Hashing of OpeningHour failed.")
            return ""
    else:
        sha_1 = hashlib.sha1()
        sha_1.update(str(data).encode())
        return sha_1.hexdigest()


def additional_remote_data(servicepoint_id: str) -> dict:
    global folio_header
    utc = pytz.UTC

    # ! first request
    request_url = secret.url + "/calendar/periods/" + servicepoint_id + "/period"
    r = requests.get(request_url, headers=folio_header)
    if r.status_code != 200:
        print(f"'{request_url}' could not retrieve data, status {r.status_code}")
        return {}
    try:
        step1_data = r.json()
    except json.JSONDecodeError:
        print("Returned Json could not be handled, mostly because it wasnt json, aborting")
        return {}
    # check if given opening hours block is valid today
    step2_uuid = None
    for period in step1_data['openingPeriods']:
        start = datetime.fromisoformat(period['startDate'])
        ende = datetime.fromisoformat(period['endDate'])
        now = utc.localize(datetime.now())  # now is usually a naive datetime and folio dates are not
        if start <= now <= ende:
            step2_uuid = period['id']
            break
    if not step2_uuid:
        print(f"No suiteable and valid opening hour found for '{servicepoint_id}'")
        return {}
    # ! second request
    request_url = secret.url + "/calendar/periods/" + servicepoint_id + "/period/" + step2_uuid
    r = requests.get(request_url, headers=folio_header)
    if r.status_code != 200:
        print(f"'{servicepoint_id}' + '{step2_uuid}' could not retrieve data, status {r.status_code}")
        return {}
    try:
        step2_data = r.json()
        # refining data for future use, i dont like manipulating the data even more here
        # adds the day identifier to each start&end time cause Spcht doesnt support backward lookups
        for days in step2_data['openingDays']:
            for hours in days['openingDay']['openingHour']:
                hours['day'] = days['weekdays']['day']
    except json.JSONDecodeError:
        print("Second returned Json could not be handled, mostly because it wasnt json, aborting")
        return {}
    return step2_data['openingDays']


def create_single_location(location: dict):
    inst = part1_folio_workings(endpoints['institution'] + "/" + location['institutionId'])
    lib = part1_folio_workings(endpoints['library'] + "/" + location['libraryId'])
    data_hash = create_hash(location, "loc")
    one_node = {
        "inst_code": inst['code'],
        "inst_name": inst['name'],
        "inst_id": inst['id'],
        "lib_code": lib['code'],
        "lib_name": lib['name'],
        "lib_id": lib['id'],
        "loc_name": location['name'],
        "loc_code": location['code'],
        "loc_displayName": location['discoveryDisplayName'],
        "loc_main_service_id": location['primaryServicePoint']
    }
    opening_hours = additional_remote_data(location['primaryServicePoint'])
    if opening_hours:
        one_node['openingHours'] = opening_hours
        open_hash = create_hash(opening_hours, "opening")
    else:
        open_hash = ""
    one_node.update(location['details'])
    return one_node, data_hash, open_hash


def check_location_changes(hashfile_contet: dict):
    hashes = {'loc': {}, 'opening': {}, 'raw': {}}
    for location, old_hash in hashfile_contet['loc'].items():
        current_location = part1_folio_workings(endpoints['locations'] + "/" + location)
        new_hash = create_hash(current_location, "loc")
        if new_hash == old_hash:
            continue
        else:
            data, data_hash, open_hash = create_single_location(current_location)
    return False


def check_opening_changes(hashfile_content: dict):
    verdict = []
    for servicepoint, old_hash in hashfile_content['opening'].items():
        opening = additional_remote_data(servicepoint)
        new_hash = create_hash(opening, "opening")
        if new_hash == old_hash:
            continue
        else:
            old_and_new = copy.deepcopy(find(hashfile_content['raw'], servicepoint))
            old_and_new['openingHours'] = opening
            verdict.append(old_and_new)
    return verdict


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


def part1_folio_workings(endpoint, key="an endpoint"):
    try:
        url = secret.url + endpoint + append
        r = requests.get(url, headers=folio_header)
        if r.status_code != 200:
            logging.critical(f"Status Code was not 200, {r.status_code} instead")
            exit(1)
        try:
            data = json.loads(r.text)
            logging.info(f"{key} retrieved ")
            return data
        except urllib3.exceptions.NewConnectionError:
            logging.error(f"Connection could be establish")
        except json.JSONDecodeError as e:
            logging.warning(f"JSON decode Error: {e}")
    except SystemExit as e:
        logging.info(f"SystemExit as planned, code: {e.code}")
        exit(e.code)
    except KeyboardInterrupt:
        print("Process interrupted, aborting")
        logging.warning("Process was manually aborted")
        raise KeyboardInterrupt()
    except Exception as e:
        logging.critical(f"Surprise error [{e.__class__.__name__}] {e}")
        exit(1)
    return {}


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
            "method": "sparql",
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
    for key, endpoint in endpoints.items():
        temp_data = part1_folio_workings(endpoint, key)
        if temp_data:
            dumping_dict.update(temp_data)
    # ! part 2 - packing data
    raw_info = dumping_dict
    hashes = {'loc': {}, 'opening': {}, 'raw': {}}
    if raw_info:
        extracted_dicts = []
        for each in raw_info['locations']:
            if re.search(secret.name, each['code']):
                hashes['loc'][each['id']] = create_hash(each, "loc")
                inst = grab(raw_info['locinsts'], "id", each['institutionId'])
                lib = grab(raw_info['loclibs'], "id", each['libraryId'])
                one_node = {
                    "inst_code": inst['code'],
                    "inst_name": inst['name'],
                    "inst_id": inst['id'],
                    "lib_code": lib['code'],
                    "lib_name": lib['name'],
                    "lib_id": lib['id'],
                    "loc_name": each['name'],
                    "loc_code": each['code'],
                    "loc_displayName": each['discoveryDisplayName'],
                    "loc_main_service_id": each['primaryServicePoint']
                }
                opening_hours = additional_remote_data(each['primaryServicePoint'])
                if opening_hours:
                    one_node['openingHours'] = opening_hours
                    hashes['opening'][each['primaryServicePoint']] = create_hash(opening_hours, "opening")
                one_node.update(each['details'])
                small_node = copy.copy(one_node)
                del small_node['openingHours']
                hashes['raw'][each['id']] = small_node
                extracted_dicts.append(one_node)
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
