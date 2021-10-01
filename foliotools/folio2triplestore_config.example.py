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

url = "<url to folio"
folio_spcht = "./foliotools/folio.spcht.json"  # file path to the Spcht File working on the extracted data
anti_folio_spcht = "./foliotools/folioNegative.spcht.json"  # used to generate the triples that get deleted in case of absence
anti_opening_spcht = "./foliotools/folioNegativeOpening.spcht.json"  # spcht file that results objects for old links to opening Hours
delta_opening_spcht = "./foliotools/folioDeltaOpening.spcht.json"
openingRDF = "https://schema.org/openingHoursSpecification" # an annoying deviation from the pure Spcht form, this defines the predicate of the opening hour specification
name = r"entrance$"  # ReGex String that finds the location that contains the entrance
subject = "<subject the main graph is mapped upon, something like /organisation/>"
named_graph = "<named graph inside the quad store to save upon>"  # graph in the quadstore the data resides on
main_file = "./foliotools/folio2triple.save.json" # arbitary file to save data on
hash_file = "folio_change_hashes.json"  # a json file where the hashes are saved
turtle_file = "./foliotools/folio_temp_turtle.ttl"  # a file where the processed data can be stored
workorder_file = "./foliotools/folio_order.json"  # work order file that is used for processing
virtuoso_folder = "/tmp/"  # folder from where virtuoso can read
triple_user = "USERNAME"  # user for the login in the isql or sparql interface
triple_password = "PASSWORD"  # plaintext password for the sparql or isql interface login
isql_path = "[VIRTUOSO]/bin/isql-v"  # path where the isql-v executable lies
isql_port = 1111  # port of the isql interface
sparql_url = "https://path/to/auth/sparql/endpoint"  # url of a sparql endpoint that can write/delete
XOkapiTenant = "tentant name of the folio instance"
XOkapiToken = "access token"
interval_opening = 60*60*6  # time in seconds when the opening hour is to be checked
interval_location = 60*60*24*2  # time in seconds when to check for changes in known locations
interval_all = 60*60*24*7  # time in seconds when to check for new locations
processing = "sparql" # kind of processing the work order uses, can be either 'isql' or 'sparql'
log_file = "./folio_update.log" # file where the logs are saved

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
    "X-Okapi-Tenant": XOkapiTenant,
    "X-Okapi-Token": XOkapiToken
}

if __name__ == "__main__":
    print("Folio Secrets was executed directly, not possible. Nothing to execute.")
    exit(1)
