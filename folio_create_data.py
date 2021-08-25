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

import json
from datetime import datetime
import pytz
import re
import requests

try:
    import folio_secrets
    SECRET = True
except ModuleNotFoundError:
    SECRET = False


def grab(a_list, dict_attr, dict_value):
    for each in a_list:
        if dict_attr in each and each[dict_attr] == dict_value:
            return each
    return None


def additional_remote_data(location_id: str) -> dict:
    global SECRET
    if not SECRET:  # needs remote connection details to access anything, and internet, and access..
        return {}
    utc = pytz.UTC

    folio_header = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Okapi-Tenant": folio_secrets.XOkapiTenant,
        "X-Okapi-Token": folio_secrets.XOkapiToken
    }
    # ! first request
    request_url = folio_secrets.folio_url + "/calendar/periods/" + location_id + "/period"
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
    request_url = folio_secrets.folio_url + "/calendar/periods/" + location_id + "/period/" + step2_uuid
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


if __name__ == "__main__":
    try:
        raw_info = None
        with open("folio_dump.json", "r") as folio_dump:
            raw_info = json.load(folio_dump)
        if raw_info:
            extracted_dicts = []
            for each in raw_info['locations']:
                if re.search(r"entrance$", each['code']):
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
                    one_node.update(each['details'])
                    extracted_dicts.append(one_node)

            with open("folio_extract.json", "w") as folio_extract:
                json.dump(extracted_dicts, folio_extract, indent=2)
        else:
            print("Loading failed, cannot create what is needed")

    except Exception as e:
        print(f"THIS throws Exception {e.__class__.__name__}: '{e}'")
        exit(1)  # what sense is it to catch exceptions to then just print them?

