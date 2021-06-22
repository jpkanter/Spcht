# coding: utf-8

# Copyright 2021 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of some open source application.
#
# Some open source application is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# Some open source application is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

"""
I have read that its the pythonic way to introduce your own set of errors and exceptions to be more
specific about what has happened, i am a bit late to the party in that regard, only adding this many
months after i first started working on this projects, this makes the whole code unfortunatly to a
jumpled mess of standard exceptions and my own that i later created
"""


class WorkOrderInconsitencyError(TypeError):
    """
    Work order makes no sense in a logical sense
    """
    pass


class WorkOrderError(TypeError):
    """
    Generic error with the given work order
    """
    pass


class WorkOrderTypeError(TypeError):
    """
    For incorrect file types in work order parameters
    """
    pass


class ParameterError(KeyError):
    """
    The given parameter lead to an outcome that did not work
    """
    pass


class OperationalError(TypeError):
    """
    Something that stops the overall operation from proceeding
    """
    pass


class RequestError(ConnectionError):
    """
    For requests that might fail for this or that reason within the bellows of the script
    """
    pass

