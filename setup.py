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

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open("README.md", "r") as readme:
    long_desc = readme.read()
    setup(
        name="solr2virtuoso-bridge",
        version="0.8",
        description="Utility package that provides the spcht library and a cli tool to convert flat data to linked data",
        author="JP Kanter",
        author_email="kanter@ub.uni-leipzig.de",
        long_description=long_desc,
        long_description_content_type="text/markdown",
        url="https://github.com/jpkanter/solr2triplestore-tool",
        license="",
        python_requires=">=3.6",
        zip_safe=False,
        py_modules=['local_tools', 'main', 'SpchtDescriptorFormat', 'SpchtErrors', 'WorkOrder', 'SpchtUtility'],
        data_files=[('config', ['default.spcht.json', 'config.example.json', "argparse.json", "SpchtSchema.json"]),
                    ('maps', ['translation_maps/documents.json', 'translation_maps/languages.json', 'translation_maps/role_graphs.json', 'translation_maps/roles.json'])],
        classifiers=[
                "Programming Language :: Python :: 3",
                "Environment :: Console",
                "License :: GPLv3",
                "Operating System :: OS Independent",
            ],
        install_requires=[
            "rdflib>=4.2.2",
            "pyodbc",
            "requests",
            "pymarc>=4.0.0",
            "python-dateutil",
            "jsonschema>=3.2.0"
        ],
        extras_require={"dev": [
            "termcolor"
        ]}
    )

