#!/usr/bin/env python
# connects to virtuoso and manipulates data there
import json
import sys

import pyodbc
import requests

from requests.auth import HTTPDigestAuth

# local files
from local_tools import is_dict, is_dictkey


#  ======SQL Part of the "program"======
#  as it turns out you can connect to a virtuoso via sparql in two ways: either you go directly to the webhook, usually
#  located at $server/sparql or you connect via odbc to the build-in SQL Server and execute queries with an "sparql"
#  before the actual statement. This works kinda in python, i leave this function and some tools around it but never
#  tried them very extensively, but as a poured some now wasted hours in getting it to work i guess its better to leave
#  it here for those after me
SQLSPARQLPREFIX = "sparql "  # as i noted, its just some random magic words, just in case those are different somewhen


def connect2SQL(datasource, uid, pwd):
    #  SQL Suite
    #  DSN = data source name, the actual name you have chosen in the /etc/odbc file
    #  http://docs.openlinksw.com/virtuoso/execpythonscript/
    sql = pyodbc.connect('DSN='+datasource+';UID='+uid+';PWD='+pwd)
    return sql


def sparqlQueryViaSQL(sql_object, sparql_query):
    #  SQL Suite
    #  if the direct connection via http is'nt possible we can also go via the SQL Interface via ODBC
    global SQLSPARQLPREFIX
    cursor = sql_object.cursor()

    cursor.execute(SQLSPARQLPREFIX + sparql_query)
    tables = cursor.fetchall()
    #  for row in cursor.fetchall():
    #       print(row)
    return tables


def QueryWrapper(sparql_query):
    #  SQL Suite
    #  function that does some error handles cause odbc apparently throws literal errors if there is no result set
    try:
        response = sparqlQueryViaSQL(sparql_query)
        return response
    except pyodbc.ProgrammingError:
        return "No results.  Previous SQL was not a query."

    return True  # i cannot really thing about a use cases where this might happen


# ====== END OF SQL BASED HOOKS =======


def sparqlQuery(sparql_query, base_url, get_format="application/json", **kwargs):
    # sends a query to the sparql endpoint of a virtuoso and (per default) retrieves a json and returns the data
    params = {
        "default-graph": "",
        "should-sponge": "soft",
        "query": sparql_query,
        "debug": "on",
        "timeout": "",
        "format": get_format,
        "save": "display",
        "fname": ""
    }
    try:
        if is_dictkey(kwargs, "auth") and is_dictkey(kwargs, "pwd"):
            # response = requests.get(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), params=params)
            response = requests.post(base_url, auth=HTTPDigestAuth(kwargs.get("auth"), kwargs.get("pwd")), data=params)
        else:
            response = requests.get(base_url, params=params)
    except requests.exceptions.ConnectionError:
        sys.stderr.write("Connection to Sparql-Server failed\n\r")
        return False

    try:
        if response is not None:
            if get_format == "application/json":
                return json.loads(response.text)
            else:
                return response.text
        else:
            return False
    except json.decoder.JSONDecodeError:
        return response.text


def escape_sparql(string):
    # replaces all the weird things we dont want to be unescaped in a sparql query
    return string.replace('"', '\\"')

