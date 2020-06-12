# Fork of EFRE Linked Open Data ElasticSearch Toolchain

The [original](https://github.com/slub/efre-lod-elasticsearch-tools) toolchain of the **SLUB** was to complex for my needs, further i found its documentation
in the parts that interested me the most more than lacking. Especially the total absence of any 
comments had proven tiresome

## Content

## virt_connect.py & local_tools.py

Different functions to provide utility for the other stuff. Nothing more than spliting different things in different files.

### Functions

* is_dictkey & is_dict

  absolutly unncessary functions that are just shorthands for checks to get a true/false distinction. I am quite sure there is already an inbuild function that does the same but i dont know it. Might be refactored later.

* connect2SQL

* sparlqlQueryViaSQL

* QueryWrapper

  Part of the "do SparlQL Queries via the SQL Interface". Basic functionality should work but the behaviour is not necessarily constant. I would rather not use this.

* sparqlQuery

  Simple Wrapper for the Queries to any given SparQL Endpoint, Supports the use of httpAUTH with optional Parameters `auth` and `pw`

## solr2virtuoso_bridge.py

The actual cli core program. 

### In Development, not working as intended for now, goal is a cli style interface that can be used in conjunction with a cron job

### finc2rdf.py

Takes a json formated Apache Solr Database output and formats it to a json-ld formated rdf file.

### ldj2rdf.py

Converts, as far as i see it, input from `finc2rdf.py` and converts it to a proper rdf format


## Requirements

* python3-rdflib 
* python3-elasticsearch
* python3-dev
* unixodbc-dev
