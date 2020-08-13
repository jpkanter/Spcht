import time

import pymarc
import requests
import json
import sys

from termcolor import colored

from local_tools import is_dictkey, is_dict,list_has_elements
from pymarc.exceptions import RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid, \
    RecordDirectoryInvalid, NoFieldsFound

# some texts given out by display_error
ERRFILE = {
    "file": "Kann entfernte Datei nicht öffnen, Fehler: {}",
    "json": "Kann JSON String nicht interpretieren",
    "key": "Der Eintrag {} kann nicht in der Einstellungsdatei gefunden werden",
    "typeerror": "TypeError in der Ausführung von {}",
    "unex_struct": "Die Struktur des Dokuments ist unerwartet"
}

# describes structure of the json response from solr Version 7.3.1 holding the ubl data
STRUCTURE = {
    "header": "responseHeader",
    "body": "response",
    "content": "docs"
}


def display_error(message, error_name=None):
    if error_name is None:
        if is_dictkey(ERRFILE, message):  # if there is a short handle for the error simply use that one
            print(ERRFILE[message], file=sys.stderr)
        else:
            if isinstance(error_name, str):
                print(error_name.format(message), file=sys.stderr)
            else:
                print(message, file=sys.stderr)
    else:
        if is_dictkey(ERRFILE, error_name):
            print(ERRFILE[error_name].format(message) + "\n", file=sys.stderr)
        else:
            print(message, file=sys.stderr)


def load_remote_content(url, params, response_type=0, mode="GET"):
    # starts a GET request to the specified solr server with the provided list of parameters
    # response types: 0 = just the content, 1 = just the header, 2 = the entire GET-RESPONSE
    try:
        if mode != "POST":
            resp = requests.get(url, params=params)
        else:
            resp = requests.post(url, data=params)
        if response_type == 0 or response_type > 2:  # this seems ugly
            return resp.text
        elif response_type == 1:
            return resp.headers
        elif response_type == 2:
            return resp
    except requests.exceptions.RequestException as e:
        display_error(e, "file")


def test_json(json_str):
    #  i am almost sure that there is already a build in function that does something very similar, embarrassing
    try:
        data = json.loads(json_str)
        return data
    except ValueError:
        display_error("json")
        return False


def traverse_json_response(data):
    # just looks for the header information in a solr GET response
    # technically i probably could just do data.get['response']
    for (key, value) in data.items():
        if key == STRUCTURE['body']:
            return value
    return False  # inexperience with Python #45: is it okay to return a value OR just boolean False?


def slice_header_json(data):
    # cuts the header from the json response according to the provided structure (which is probably constant anyway)
    # returns list of dictionaries
    if is_dict(data.get(STRUCTURE['body'])):
        if is_dictkey(data.get(STRUCTURE['body']), STRUCTURE['content']):
            return data.get(STRUCTURE['body']).get(STRUCTURE['content'])
    display_error("unex_struct")

    # either some ifs or a try block, same difference


def marc21_fixRecord(record="", record_id=0, validation=False, replace_method='decimal'):
    # imported from the original finc2rdf.py
    # its needed cause the marc21_fullrecord entry contains some information not in the other solr entries
    # record id is only needed for the error text so its somewhat transparent where stuff went haywire
    # i think what it does is replacing some characters in the response of solr, the "replace_method" variable
    # was a clue.
    replace_methods = {
        'decimal': (('#29;', '#30;', '#31;'), ("\x1D", "\x1E", "\x1F")),
        'unicode': (('\u001d', '\u001e', '\u001f'), ("\x1D", "\x1E", "\x1F")),
        'hex': (('\x1D', '\x1E', '\x1F'), ("\x1D", "\x1E", "\x1F"))
    }
    marcFullRecordFixed = record
    # replaces all three kinds of faults in the choosen method (decimal, unicode or hex)
    # this method is written broader than necessary, reuseable?
    for i in range(0, 3):
        marcFullRecordFixed = marcFullRecordFixed.replace(replace_methods.get(replace_method)[0][i],
                                                          replace_methods.get(replace_method)[1][i])
    if validation:
        try:
            reader = pymarc.MARCReader(marcFullRecordFixed.encode('utf8'), utf8_handling='replace')
            marcrecord = next(reader) # what does this?
        except (
                RecordLengthInvalid, RecordLeaderInvalid, BaseAddressNotFound, BaseAddressInvalid,
                RecordDirectoryInvalid,
                NoFieldsFound, UnicodeDecodeError) as e:
            display_error("record id {0}:".format(record_id) + str(e))
            with open('invalid_records.txt', 'a') as error:
                error.write(marcFullRecordFixed)
                error.close()
            return False
    return marcFullRecordFixed


def marcleader2report(leader, output=sys.stdout):
    # outputs human readable information about a marc leader
    # text source: https://www.loc.gov/marc/bibliographic/bdleader.html
    marc_leader_text = {
        "05": {"label": "Record status",
               "a": "Increase in encoding level",
               "c": "Corrected or revised",
               "d": "Deleted",
               "n": "New",
               "p": "Increase in encoding level from prepublication"
               },
        "06": {"label": "Type of record",
               "a": "Language material",
               "c": "Notated music",
               "d": "Manuscript notated music",
               "e": "Cartographic material",
               "f": "Manuscript cartographic material",
               "g": "Projected medium",
               "i": "Non-musical sound recording",
               "j": "Musical sound recourding",
               "k": "Two-dimensional non-projectable graphic",
               "m": "Computer file",
               "o": "Kit",
               "p": "Mixed Materials",
               "r": "Three-dimensional or naturally occurring object",
               "t": "Manuscript language material"
               },
        "07": {"label": "Bibliographic level",
               "a": "Monographic component part",
               "b": "Serial component part",
               "c": "Collection",
               "d": "Subunit",
               "i": "Integrating resource",
               "m": "Monograph/Item",
               "s": "Serial"
               },
        "08": {"label": "Type of control",
               " ": "No specified type",
               "a": "archival"
               },
        "09": {"label": "Character coding scheme",
               " ": "MARC-8",
               "a": "UCS/Unicode"
               },
        "18": {"label": "Descriptive cataloging form",
               " ": "Non-ISBD",
               "a": "AACR 2",
               "c": "ISBD punctuation omitted",
               "i": "ISBD punctuation included",
               "n": "Non-ISBD punctuation omitted",
               "u": "Unknown"
               }
    }

    for i in range(23):
        if i < 4 or (12 <= i <= 15):
            continue
        if i == 5:  # special case one, length is on the fields 0-4
            print("Record length: " + leader[0:5])
            continue
        if i == 16:
            print("Leader & directory length " + leader[12:16])
        if is_dictkey(marc_leader_text, f'{i:02d}'):
            print(marc_leader_text.get(f'{i:02d}').get('label') + ": " + marc_leader_text.get(f'{i:02d}').get(leader[i], "unknown"), file=output)


def normalize_marcdict(a_so_called_dictionary):
    # all this trouble cause for some reasons pymarc insists on being awful
    # to explain it a bit further, this is the direct outout of .as_dict() for an example file
    # {'leader': '02546cam a2200841   4500', 'fields': [{'001': '0-023500557'}, ...
    # the leader is okay, but why are the fields a list of single dictionaries? i really dont get it
    the_long_unnecessary_list = a_so_called_dictionary.get('fields', None)
    an_actual_dictionary = {}
    if the_long_unnecessary_list is not None:
        for mini_dict in the_long_unnecessary_list:
            key = next(iter(mini_dict)) # Python 3.7 feature
            an_actual_dictionary[key] = mini_dict[key]
        return an_actual_dictionary
    return False


def marc2list(marc_full_record, validation=True, replace_method='decimal'):
    clean_marc = marc21_fixRecord(marc_full_record, validation=validation, replace_method=replace_method)
    if isinstance(clean_marc, str):  # would be boolean if something bad had happen
        reader = pymarc.MARCReader(clean_marc.encode('utf-8'))
        marc_list = []
        for record in reader:
            tempdict = {}
            record_dict = normalize_marcdict(record.as_dict()) # for some reason i cannot access all fields,
            # also funny, i could probably use this to traverse the entire thing ,but better save than sorry i guess
            # sticking to the standard in case pymarc changes in a way or another
            for i in range(1000):
                if record[f'{i:03d}'] is not None:
                    tempdict[i] = {}
                    for item in record[f'{i:03d}']:
                        # marc items are tuples, for title its basically 'a': 'Word', 'b': 'more Words'
                        tempdict[i][item[0]] = item[1]
                        if is_dictkey(tempdict[i], "concat"):
                            tempdict[i]['concat'] += " " + item[1]
                        else:
                            tempdict[i]['concat'] = item[1]
                    if not list_has_elements(record[f'{i:03d}']):
                        tempdict[i] = record_dict.get(f'{i:03d}')
                        # normal len doesnt work cause no method, flat element
            marc_list.append(tempdict)
        if 0 < len(marc_list) < 2:
            return marc_list[0]
        elif len(marc_list) > 1:
            return marc_list
        else:
            return None
    else:
        return False
    # i am astonished how diverse the return statement can be, False if something went wrong, None if nothing gets
    # returned but everything else went fine, although, i am not sure if that even triggers and under what circumstances
