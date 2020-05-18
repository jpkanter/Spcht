# Fork of EFRE Linked Open Data ElasticSearch Toolchain

The [original](https://github.com/slub/efre-lod-elasticsearch-tools) toolchain of the **SLUB** was to complex for my needs, further i found its documentation
in the parts that interested me the most more than lacking. Especially the total absence of any 
comments had proven tiresome

## Content

### finc2rdf.py

Takes a json formated Apache Solr Database output and formats it to a json-ld formated rdf file.

### ldj2rdf.py

Converts, as far as i see it, input from `finc2rdf.py` and converts it to a proper rdf format


## Requirements

* python3-rdflib 
* python3-elasticsearch
* python3-dev
* unixodbc-dev
