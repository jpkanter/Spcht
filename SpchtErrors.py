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

"""
I have read that its the pythonic way to introduce your own set of errors and exceptions to be more
specific about what has happened, i am a bit late to the party in that regard, only adding this many
months after i first started working on this projects, this makes the whole code unfortunatly to a
jumpled mess of standard exceptions and my own that i later created
"""


class WorkOrderInconsitencyError(Exception):
    def __repr__(self):
        return "A change is inconsistent with the logic of a work order, like updating a status to a lower level than the previos one"


class WorkOrderError(Exception):
    def __repr__(self):
        return "Generic error with the given work order"


class WorkOrderTypeError(Exception):
    def __repr__(self):
        return "For incorrect file types in work order parameters"


class ParameterError(Exception):
    def __repr__(self):
        return "The given parameter lead to an outcome that did not work"


class OperationalError(Exception):
    def __repr__(self):
        return "Something that stops the overall operation from proceeding"


class RequestError(ConnectionError):
    def __repr__(self):
        return "For requests that might fail for this or that reason within the bellows of the script"


class ParsingError(Exception):
    def __repr__(self):
        return "an Exception that occurs when trying to interpret or parse some kind of data"


class Unexpected(Exception):
    def __repr__(self):
        return "an exception that should have not been happened but was prepared in case seomthing weird happened"


class MandatoryError(Exception):
    def __repr__(self):
        return "a field that was classified as mandatory was not present, therefore failing the entire chain"

