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