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
import re
import codecs
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Spcht_i18n:
    """
    Rather simple implementation for basic i18m usage, there are other plugins for this but the scope i actually need
    is rather tiny so i wrote this instead of adding another dependency

    Simple Example
    ```json
    {
        "title": {
            "en": "title",
            "de": "Title"
        },
        "abort": {
            "en": "abort",
            "de": "abbruch"
        }
    }
    ```
    """

    def __init__(self, file_path, language="en"):
        self.__language = language
        self.__default_language = "en"
        self.__repository = {}
        self.__load_package(file_path)

    def __repr__(self):
        return f"SPCHT_i18n [{self.__language}] {len(self.__repository)}"

    def __contains__(self, item):
        if item in self.__repository:
            return True
        else:
            return False

    def __len__(self):
        return len(self.__repository)

    def __getitem__(self, item):
        if item in self.__repository:
            return self.__repository[item]
        else:
            return item

    def __load_package(self, file_path):
        try:
            with open(file_path, "r") as language_file:
                language_dictionary = json.load(language_file)
        except json.JSONDecodeError as decoder:
            logger.warning(f"Could not load json because error: {decoder}")
            return False
        except FileNotFoundError:
            logger.warning(f"Could not locate given language file")
            return False

        if not isinstance(language_dictionary, dict):
            return False

        for key, value in language_dictionary.items():
            if not isinstance(value, dict):
                continue
            if self.__language in value:
                self.__repository[key] = value[self.__language]
            elif self.__default_language in value:
                self.__repository[key] = value[self.__default_language]

    @staticmethod
    def export_csv(language_file: str, csv_file: str, separator=";"):
        """
        Exports an already loaded dictionary to a csv file
        :param str language_file: the current, working language file
        :param str csv_file: a yet to be created csv file path
        :param str separator: seperator symbol used in writing the csv file
        :return: True if everything went alright, False and a log file entry if something went wrong
        :rtype: bool
        """
        # yes, there is a library for csv writing, i acknowledge that
        try:
            with open(language_file, "r") as languages:
                pure_data = json.load(languages)
        except FileNotFoundError:
            logger.error(f"Could not find language file '{language_file}' for export to csv")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"While trying to export, reading in the language file {language_file} failed with a json error {e}")
            return False
        try:
            with open(csv_file, "w") as csv:
                languages = defaultdict(int)
                for each in pure_data.values():
                    for key in each:
                        languages[key] += 1
                print(str(dict(languages)))
                fixed_order = set(languages.keys())
                csv.write(f"{separator}{';'.join(fixed_order)}\n")
                for key, item in pure_data.items():
                    csv.write(f"{key}")
                    for lang in fixed_order:
                        csv.write(f"{separator}{item.get(lang, '')}")
                    csv.write("\n")
        except FileExistsError as e:
            logger.error(f"File already exists, cannot overwrite '{csv_file}' - {e}")
            return False
        return True

    @staticmethod
    def import_csv(csv_file: str, language_file: str, seperator=";"):
        try:
            with codecs.open(csv_file, "r", encoding="utf-8") as csv:
                all_lines = csv.readlines()
        except FileNotFoundError:
            logger.error(f"Cannot find designated file {csv_file}")
            return False
        lang = {_: re.sub(r"(\n$)|(\r$)|(\n\r$)", "", x) for _, x in enumerate(all_lines[0].split(seperator)) if _ > 0}
        print(lang)
        translation = defaultdict(dict)
        # every element except the first as a dictionary
        for _, line in enumerate(all_lines):
            if _ == 0:  # this construct seems like something i could do better
                continue
            data = line.split(seperator)
            for i, each in enumerate(data):
                if i == 0:
                    continue
                translation[data[0]][lang[i]] = re.sub(r"(\n$)|(\r$)|(\n\r$)", "", each)
        try:
            with codecs.open(language_file, "w", encoding='utf-8') as languages:
                json.dump(translation, languages, indent=3, ensure_ascii=False)
                print(f"Entries: {len(translation)}")
        except FileExistsError:
            logger.warning(f"File {language_file} already exists and cannot be overwritten")