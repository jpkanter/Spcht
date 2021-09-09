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
from datetime import datetime
from SpchtDescriptorFormat import Spcht

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


def additional_remote_data(location_id: str) -> dict:
    global folio_header
    utc = pytz.UTC

    # ! first request
    request_url = secret.url + "/calendar/periods/" + location_id + "/period"
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
        print(f"No suiteable and valid opening hour found for '{location_id}'")
        return {}
    # ! second request
    request_url = secret.url + "/calendar/periods/" + location_id + "/period/" + step2_uuid
    r = requests.get(request_url, headers=folio_header)
    if r.status_code != 200:
        print(f"'{location_id}' + '{step2_uuid}' could not retrieve data, status {r.status_code}")
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


def check_opening_changes(hashfile_content: dict):
    verdict = []
    for servicepoint, old_hash in hashfile_content['opening'].items():
        opening = additional_remote_data(servicepoint)
        new_hash = create_hash(opening, "opening")
        if new_hash == old_hash:
            continue
        else:
            verdict.append(find(hashfile_content['raw'], servicepoint))
    return verdict


def full_update():
    # ! part 1 - download of raw data
    dumping_dict = {}
    for key, endpoint in endpoints.items():
        try:
            url = secret.url + endpoint + append
            r = requests.get(url, headers=folio_header)
            if r.status_code != 200:
                logging.critical(f"Status Code was not 200, {r.status_code} instead")
                exit(1)
            try:
                data = json.loads(r.text)
                dumping_dict.update(data)
                logging.info(f"{key} retrieved ")
            except urllib3.exceptions.NewConnectionError:
                logging.error(f"Connection could be establish")
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode Error: {e}")
                continue
        except SystemExit as e:
            logging.info(f"SystemExit as planned, code: {e.code}")
            exit(e.code)
        except KeyboardInterrupt:
            print("Process interrupted, aborting")
            logging.warning("Process was manually aborted")
            exit(1)
        except Exception as e:
            logging.critical(f"Surprise error [{e.__class__.__name__}] {e}")
            exit(1)
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
    duck = Spcht(secret.foliospcht)
    triples = []
    for each_entry in extracted_dicts:
        triples += duck.process_data(each_entry, secret.subject)
    temp_file_name = secret.turtle_file
    with open(temp_file_name, "w") as rdf_file:
        rdf_file.write(SpchtUtility.process2RDF(triples))  # ? avoiding circular imports
    exit(0)
    f_path = shutil.copy(temp_file_name, secret.virtuoso_folder)
    command = f"EXEC=ld_add('{f_path}', '{secret.named_graph}');"
    subprocess.run(
        [secret.isql_path, str(secret.isql_port), secret.isql_user, secret.isql_password, "VERBOSE=OFF", command,
         "EXEC=rdf_loader_run();", "EXEC=checkpoint;"],
        capture_output=True, check=True)
    if os.path.exists(f_path):
        os.remove(f_path)


if __name__ == "__main__":
    full_update()
