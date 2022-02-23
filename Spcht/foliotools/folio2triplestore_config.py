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

import logging
import sys
import os
from pathlib import Path
from Spcht.Utils.local_tools import load_from_json
from Spcht.Core.SpchtErrors import OperationalError

logger = logging.getLogger(__name__)

# this is an afterthough, i am deeply sry, PEP hates me because of it but its the quickest way

conf_path = Path(os.getcwd())
if (raw_config := load_from_json(conf_path / "foliotools.config.json")) is None:
    logger.critical("Cannot load config file, aborting process. If you see this without using foliotools, all is well")
    raise OperationalError("Cannot foliotools config")  # i must say, using a .py file as config was a boneheaded idea
# key : default_value
FOLIO_DEF_CONF = {
    'url': None,
    'folio_spcht': None,  # file path to the Spcht File working on the extracted data
    'anti_folio_spcht': None,  # used to generate the triples that get deleted in case of absence
    'anti_opening_spcht': None,  # spcht file that results objects for old links to opening Hours
    'delta_opening_spcht': None,
    'name': r"entrance$",  # ReGex String that finds the location that contains the entrance
    'subject': None,
    'named_graph': None,  # graph in the quadstore the data resides on
    'main_file': "./folio2triple.save.json",   # a json file where the hashes are saved
    'hash_file': "./folio_change_hashes.json",
    'turtle_file': "./folio_temp_turtle.ttl",  # a file where the processed data can be stored
    'workorder_file': "folio_order.json",   # work order file that is used for processing
    'virtuoso_file': "/tmp/",  # folder from where virtuoso can read
    'triple_user': None,  # user for the login in the isql or sparql interface
    'triple_password': None,   # plaintext password for the sparql or isql interface login
    'isql_path': None,  # path where the isql-v executable lies
    'isql_port': 1111,   # port of the isql interface
    'sparql_url': None,   # url of a sparql endpoint that can write/delete
    'XOkapiTenant': None,
    'XOkapiToken': None,
    'interval_opening': 60*60*6,  # time in seconds when the opening hour is to be checked
    'interval_location': 60*60*24*1,  # time in seconds when to check for changes in known locations
    'interval_all': 60*60*24*7,  # time in seconds when to check for new locations
    'processing': "sparql",
    'openingRDF': "https://schema.org/openingHoursSpecification"
}
thismodule = sys.modules[__name__]  # ! dont try this at home kids
for key, default in FOLIO_DEF_CONF.items():
    if key not in raw_config or \
            (isinstance(raw_config[key], str) and raw_config[key].strip() == "") or \
            (isinstance(raw_config[key], int) and raw_config[key] == 0):
        if default is None:
            logger.critical(f"Mandatory Config Entry {key} could not be found")
            exit(2)
        setattr(thismodule, key, default)
    else:
        setattr(thismodule, key, raw_config[key])
# ! if you hear angry buzzing in your ear this is the PEP committee droning into you, they will probably crawl out
# ! of the screen and try to murder you. Happened to me when i wrote this..basically

# endpoints, should almost never change, period & one_period use substitutes for the position of the UUIDs
endpoints = {
    "library": "/location-units/libraries",
    "campus": "/location-units/campuses",
    "institution": "/location-units/institutions",
    "service": "/service-points",
    "locations": "/locations",
    "periods": "/calendar/periods/$servicepoint_id/period",
    "one_period": "/calendar/periods/$servicepoint_id/period/$period_id"
}

folio_header = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Okapi-Tenant": XOkapiTenant,  # ignore this..the works anyway
    "X-Okapi-Token": XOkapiToken
}

if __name__ == "__main__":
    print("Folio Secrets was executed directly, not possible. Nothing to execute.")
    exit(1)
