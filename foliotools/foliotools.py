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

import hashlib
import json
import logging
import copy
import pytz
import requests
import urllib3
from datetime import datetime

import foliotools.folio2triplestore_config as secret

logger = logging.getLogger(__name__)


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
    utc = pytz.UTC

    # ! first request
    request_url = secret.url + "/calendar/periods/" + servicepoint_id + "/period"
    r = requests.get(request_url, headers=secret.folio_header)
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
    r = requests.get(request_url, headers=secret.folio_header)
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
    inst = part1_folio_workings(secret.endpoints['institution'] + "/" + location['institutionId'])
    lib = part1_folio_workings(secret.endpoints['library'] + "/" + location['libraryId'])
    return create_location_node(location, inst, lib)


def check_location_changes(hashfile_contet: dict):
    hashes = {'loc': {}, 'opening': {}, 'raw': {}}
    for location, old_hash in hashfile_contet['loc'].items():
        current_location = part1_folio_workings(secret.endpoints['locations'] + "/" + location)
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


def part1_folio_workings(endpoint, key="an endpoint", append=""):
    try:
        url = secret.url + endpoint + append
        r = requests.get(url, headers=secret.folio_header)
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


def create_location_node(location: dict, inst: dict, lib: dict):
    """

    :param dict location: location data
    :param dict inst: institution data
    :param dict lib: library data
    :return: a quadro tuple of the node, location_hash, open_hash and raw_data
    :rtype: tuple(dict, str, dict, dict)
    """
    location_hash = create_hash(location, "loc")
    open_hash = dict()
    raw_data = dict()
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
        open_hash[location['primaryServicePoint']] = create_hash(opening_hours, "opening")
    one_node.update(location['details'])
    small_node = copy.copy(one_node)
    del small_node['openingHours']
    raw_data[location['id']] = small_node
    return one_node, location_hash, open_hash, raw_data

