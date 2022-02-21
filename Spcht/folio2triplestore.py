#!/usr/bin/env python
# coding: utf-8

# Copyright 2022 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of the Spcht.
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
# along with Spcht.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>
import logging
import sys
import re
import copy
import os
import argparse
import json
from datetime import datetime, timedelta
import traceback

# import internal modules
from Spcht.Core import SpchtUtility
from Spcht.Core import WorkOrder

from Spcht.Core.SpchtCore import Spcht, SpchtTriple, SpchtThird
from Spcht.Utils.local_tools import sizeof_fmt
from Spcht.foliotools.foliotools import part1_folio_workings, grab, create_single_location, check_location_changes, \
    check_opening_changes, create_location_node, sparql_delete_node_plus1

import Spcht.foliotools.folio2triplestore_config as secret

logging.basicConfig(filename=secret.log_file, format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.INFO)
#logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

append = "?limit=1000"
__version__ = 0.7


def crawl_location(location_hashes, opening_hashes, location_objects, opening_objects):
    global append
    locations = part1_folio_workings(secret.endpoints['locations'], "location", append)
    found_locations = {}
    for each in locations['locations']:
        if re.search(secret.name, each['code']):
            found_locations[each['id']] = copy.deepcopy(each)
    new_locations = {}
    for key, each in found_locations.items():
        if key not in location_hashes:
            one_loc, loc_hash, open_hash = create_single_location(each)
            location_hashes.update({key: loc_hash})
            opening_hashes.update(open_hash)
            new_locations[key] = one_loc
    if not new_locations:
        return []
    logging.info(f"Found {len(new_locations)} new locations")
    triples, anti_triple, anti_opening = part3_spcht_workings(new_locations, secret.folio_spcht,
                                                              secret.anti_folio_spcht,
                                                              secret.anti_opening_spcht)
    opening_objects.update({k: v[0] for k, v in anti_opening.items()})
    location_objects.update(anti_triple)
    if part4_work_order(triples):
        return [location for location in new_locations.keys()]
    else:
        return None


def location_update(location_hashes, opening_hashes, location_objects, opening_objects):
    changed = check_location_changes(location_hashes)
    if not changed:
        logging.info("Check completed without any found changes, hibernating...")
        return []
    changedLocs = {k: v['location'] for k, v in changed.items() if 'location' in v}

    location_hashes.update({k: v['location_hash'] for k, v in changed.items() if 'location_hash' in v})
    for dic in changed.values():
        if 'opening_hash' in dic:
            opening_hashes.update(dic['opening_hash'])
    # * opening_hashes.update({dic['opening_hash'] for dic in changed.values()})
    # ? double dictionary comprehension, the way 'create_node' works is that it has to transport the id of  the
    # ? opening hour somehow, this it does by nesting the key one layer deeper, so that the result of 'create_one_node'
    # ? that is used in location changes gives us {location}, str_hash, {uuid_str: str_hash}
    # ? to get the actual opening hour uuid we therefore have to go two layers deep, in this case there should always
    # ? be only one key for opening_hour hashes but this method would even work with more, no clue how 'expensive'
    # ? this is but it should not matter a lot

    for hash_key in changed:
        for node in location_objects[hash_key]:
            sparql_delete_node_plus1(secret.named_graph, node, secret.sparql_url, secret.triple_user, secret.triple_password)
            sparql_delete_node_plus1(secret.named_graph, "?s", secret.sparql_url, secret.triple_user, secret.triple_password, sobject=node)
        if not changed[hash_key]:  #delete disappeard entries
            del location_objects[hash_key]
            del location_hashes[hash_key]
    triples, anti_triple, anti_opening = part3_spcht_workings(changedLocs, secret.folio_spcht, secret.anti_folio_spcht, secret.anti_opening_spcht)
    opening_objects.update({k: v[0] for k, v in anti_opening.items()})
    location_objects.update(anti_triple)
    if part4_work_order(triples):
        return [hash_key for hash_key in changedLocs.keys()]
    else:
        return None


def opening_update(opening_hashes: dict, opening_object: dict):
    changed = check_opening_changes(opening_hashes)
    if not changed:
        logging.info("Check completed without any found changes, hibernating...")
        return {}
    # delete old entries, create anew
    changedOpenings = {k: v['hours'] for k, v in changed.items()}
    heron = Spcht(secret.delta_opening_spcht)
    all_triples = []
    for key, value in changedOpenings.items():
        triples = heron.process_data(value, "https://dUckGoOse")
        other_triples = []
        for third in triples:
            if re.match(r"^https://dUckGoOse", third.subject.content):
                continue
            other_triples.append(
                SpchtTriple(
                    SpchtThird(opening_object[key][:-1][1:], uri=True),
                    SpchtThird(secret.openingRDF, uri=True),
                    third.subject
                )
            )
            all_triples.append(third)
            all_triples += other_triples
    opening_hashes.update({k: v['hash'] for k, v in changed.items()})

    # ! discard processing
    for key in changed.keys():
        sobject = opening_object[key]
        status, discard = sparql_delete_node_plus1(secret.named_graph,
                                                   sobject,
                                                   secret.sparql_url,
                                                   secret.triple_user,
                                                   secret.triple_password,
                                                   "<https://schema.org/openingHoursSpecification>"
                                                   )

    if part4_work_order(all_triples):
        return [key for key in changed.keys()]
    else:
        return None  # failed inserts


def part3_spcht_workings(extracted_dicts: dict, main_spcht: str, anti_spcht=None, anti_spcht2=None):
    # * this can definitely be called janky as heck
    duck = Spcht(main_spcht)
    duck.name = "Duck"
    goose = None
    swane = None
    if anti_spcht:
        goose = Spcht(anti_spcht)
        goose.name = "Goose"
    if anti_spcht2:
        swane = Spcht(anti_spcht2)
        swane.name = "Swane"
    triples = []
    anti_triples = {}
    anti_triples2 = {}
    for key, each_entry in extracted_dicts.items():
        triples += duck.process_data(each_entry, secret.subject)
        if goose:
            anti_triples[key] = SpchtTriple.extract_subjects(goose.process_data(each_entry, "https://x.y"))
        if swane:
            anti_triples2[each_entry['loc_main_service_id']] = SpchtTriple.extract_subjects(swane.process_data(each_entry, "https://z.a"))
    return triples, anti_triples, anti_triples2


def part4_work_order(triples: list):
    with open(secret.turtle_file, "w") as rdf_file:
        rdf_file.write(SpchtUtility.process2RDF(triples))
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
    # TODO: we have here a usecase for workorder fileIO, like not writing a file at all would be useful wouldnt it?
    with open(secret.workorder_file, "w") as work_order_file:
        json.dump(work_order, work_order_file)
    res = WorkOrder.FulfillSparqlInsertOrder(secret.workorder_file, secret.sparql_url, secret.triple_user,
                                             secret.triple_password, secret.named_graph)
    logging.info(f"WorkOrder Fullfilment, now status: {res}")
    return res


def full_update():
    # create new main_file
    # ? general structure:
    init_now = datetime.now().isoformat()
    main_file = {
        "meta": {
            "last_opening": init_now,
            "last_location": init_now,
            "last_crawl": init_now,
            "last_call": init_now,
            "log_file": secret.log_file,
            "first_call": init_now,
            "counter": 0,
            "avg_cal_intervall": ""
        },
        "hashes": {
            "location": {},
            "opening": {}
        },
        "triples": {
            "location": {},
            "opening": {}
        }
    }
    # ? end of structure
    # ! part 1 - download of raw data
    raw_info = {}
    for key, endpoint in secret.endpoints.items():
        temp_data = part1_folio_workings(endpoint, key, append)
        if temp_data:
            raw_info.update(temp_data)
    # ! part 2 - packing data
    if raw_info:
        extracted_dicts = {}
        for each in raw_info['locations']:
            if re.search(secret.name, each['code']):
                inst = grab(raw_info['locinsts'], "id", each['institutionId'])
                lib = grab(raw_info['loclibs'], "id", each['libraryId'])
                one_node, location_hash, opening_hash = create_location_node(each, inst, lib)
                extracted_dicts[each['id']] = one_node
                main_file['hashes']['location'][each['id']] = location_hash
                main_file['hashes']['opening'].update(opening_hash)
    else:
        logging.warning("No data to work on")
        print("Loading failed, cannot create what is needed")
        exit(0)
    # ! part 3 - SpchtWorkings
    triples, anti_triple, anti_opening = part3_spcht_workings(extracted_dicts, secret.folio_spcht, secret.anti_folio_spcht, secret.anti_opening_spcht)
    main_file['triples']['location'] = anti_triple
    main_file['triples']['opening'] = {k: v[0] for k, v in anti_opening.items()}
    part4_work_order(triples)
    with open(secret.main_file, "w") as big_file:
        json.dump(main_file, big_file, indent=3)


if __name__ == "__main__":
    # * Argparse Init
    parser = argparse.ArgumentParser(
        description="Folio2Triplestore Tool - Converts Folio Data into triples",
        usage="folio2triplestore.py [--info][--opening][--location][--crawl]",
        epilog="All Settings are to be done in './foliotools/folio2triplestore_config.py'",
        prefix_chars="-")
    parser.add_argument("-i", "--info", action="store_true", help="Shows info about the current file if it exists")
    parser.add_argument("-c", "--crawl", action="store_true", help="Crawls for new locations regardless of time since last crawl")
    parser.add_argument("-l", "--location", action="store_true", help="Checks all known location for updates, ignores cooldown")
    parser.add_argument("-o", "--opening", action="store_true", help="Checks all opening hours for changes, ignores cooldown")
    args = parser.parse_args()

    # This seems like the most inelegant way to trigger the processes by multiple, exclusive conditions
    do_crawl = False
    do_location = False
    do_opening = False
    no_arguments = False
    if len(sys.argv) == 1:
        no_arguments = True
    if args.info:
        pass
    if args.crawl:
        do_crawl = True
    if args.location:
        do_location = True
    if args.opening:
        do_opening = True

    try:
        with open(secret.main_file, "r") as big_file:
            try:
                main_file = json.load(big_file)
                main_file_bck = copy.deepcopy(main_file)
            except json.JSONDecodeError:
                logging.error("'big_file' could not be read, apparently json interpreting failed. Start anew?")
                exit(1)
        ahuit = datetime.now()
        insert_failure = False
        time_switch = {
            'opening':  datetime.fromisoformat(main_file['meta']['last_opening']),
            'location':  datetime.fromisoformat(main_file['meta']['last_location']),
            'crawl':  datetime.fromisoformat(main_file['meta']['last_crawl']),
            'last_call': datetime.fromisoformat(main_file['meta']['last_call'])
        }
        # * Time Switch
        if no_arguments:  # when no argument are given use the normal timer events to trigger
            if (ahuit - time_switch['crawl']).total_seconds() > secret.interval_all:
                do_crawl = True
            if (ahuit - time_switch['opening']).total_seconds() > secret.interval_opening:
                do_opening = True
            if (ahuit - time_switch['location']).total_seconds() > secret.interval_location:
                do_location = True

        if args.info:
            print(f"Folio2Triplestore Tool Version {__version__}")
            print(f"    Locations:             {len(main_file['hashes']['location'])}")
            print(f"    Last call:             {main_file['meta']['last_call']}")
            print(f"    Total calls:           {main_file['meta']['counter']}")
            print(f"    Avg. time btw. calls:  {main_file['meta']['avg_cal_intervall_human']}")
            print(f"    Log file size:         {sizeof_fmt(os.stat(secret.log_file).st_size)}")
        if len(sys.argv) == 2 and args.info:
            exit(0)  # no changes written if only info was called

        if do_crawl:
            logging.info(f"Crawling for Locations triggered - now: '{ahuit.isoformat()}', last call: '{main_file['meta']['last_crawl']}'")
            main_file['meta']['last_crawl'] = ahuit.isoformat()
            crawl_return = crawl_location(main_file['hashes']['location'],
                                            main_file['hashes']['opening'],
                                            main_file['triples']['location'],
                                            main_file['triples']['opening'])
            if crawl_return:
                logging.info("New Locations inserted:" + str(crawl_return))
            elif crawl_return is None:
                insert_failure = True
        if do_location:
            logging.info(f"Location update triggered - now: '{ahuit.isoformat()}', last call: '{main_file['meta']['last_location']}'")
            main_file['meta']['last_location'] = ahuit.isoformat()
            update_return = location_update(main_file['hashes']['location'],
                                            main_file['hashes']['opening'],
                                            main_file['triples']['location'],
                                            main_file['triples']['opening'] )
            if update_return:
                logging.info("Updated locations:" + str(update_return))
            elif update_return is None:
                insert_failure = True
        if do_opening:
            logging.info(f"Opening update triggered - now: '{ahuit.isoformat()}', last call: '{main_file['meta']['last_opening']}'")
            main_file['meta']['last_opening'] = ahuit.isoformat()
            update_return = opening_update(main_file['hashes']['opening'], main_file['triples']['opening'])
            if update_return:
                logging.info("Updated opening hours")
                main_file['hashes']['opening'] = update_return

        if insert_failure:
            # ? due my stupidity the update/crawl functions update referenced dics, the most easy solution for me is to
            # ? just replace the change with the former state
            main_file = copy.deepcopy(main_file_bck)

        try:  # this is a try block cause i fear it might fail for stupid reasons and i dont want the entire procedure
            # crash because of that screwing around with deltatimes
            if main_file['meta']['avg_cal_intervall']:
                old_delta = timedelta(seconds=int(main_file['meta']['avg_cal_intervall']))
                relative_delta = ahuit - time_switch['last_call']
                # nd = new_delta # it was just to long to write 4 times in one line
                nd = (old_delta + relative_delta) / 2  # ! hail to datetime library for doing the heavy lifting
            else:
                nd = ahuit - time_switch['last_call']
            main_file['meta']['avg_cal_intervall_human'] = \
                f"{str(nd.days):0>3}d-{str(nd.seconds//3600):0>2}h:{str((nd.seconds//60)%60):0>2}m:{str((nd.seconds%60)%60):0>2}s"
            main_file['meta']['avg_cal_intervall'] = (nd.days * 60 * 60 * 24) + nd.seconds
        except Exception as e:
            logging.debug(f"Updating of average call intervall failed somehow: {e.__class__.__name__}: {e}")
            traceback.print_exc()
        logging.debug(f"Call finished, last call was: {main_file['meta']['last_call']}, average time between calls is now: {main_file['meta']['avg_cal_intervall_human']}")
        print("Call to folio2triplestore finished, times updated")  # print so at least something shows up in the console if manually called
        main_file['meta']['last_call'] = ahuit.isoformat()
        main_file['meta']['counter'] += 1

        with open(secret.main_file, "w") as big_file:
            json.dump(main_file, big_file, indent=3)

    except FileNotFoundError:
        full_update()
        exit(0)
    except Exception as e:
        logging.critical(f"MAIN::Unexpected exception {e.__class__.__name__} occured, message '{e}'")
        traceback.print_exc()
        exit(9)
