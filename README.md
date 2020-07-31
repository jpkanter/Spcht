# Fork for EFRE Linked Open Data ElasticSearch Toolchain

The [original](https://github.com/slub/efre-lod-elasticsearch-tools) toolchain of the **SLUB** was to complex for my needs, further i found its documentation
in the parts that interested me the most more than lacking. Especially the total absence of any 
comments had proven tiresome

## Content

## virt_connect.py & local_tools.py

Different functions to provide utility for the other stuff. Nothing more than splitting different things in different files.

### Functions

- is_dictkey & is_dict

  absolutely unncessary functions that are just shorthands for checks to get a true/false distinction. I am quite sure there is already an in-build function that does the same but i don't know it. Might be re-factored later.

- connect2SQL

- sparlqlQueryViaSQL

- QueryWrapper

  Part of the "do SparlQL Queries via the SQL Interface". Basic functionality should work but the behavior is not necessarily constant. I would rather not use this.

- sparqlQuery

  Simple Wrapper for the Queries to any given SparQL Endpoint, Supports the use of httpAUTH with optional Parameters `auth` and `pw`

### In Development, not working as intended for now, goal is a cli style interface that can be used in conjunction with a cron job

## solr2virtuoso_bridge.py

The main piece of work here, developed to do all the heavy lifting. It introduces a setting/descriptor format to actually map corresponding data fields from the apache solr database to sparql queries. The functions in the code do not actually require a solr as input source, if you have any other way to retrieve pure _jsoned_ dictionaries with a simple file structure it should also work. Or at least should be possible to easily modify the code to use such a source.

## SpchtDiscriptorFormat.py

Main class file for the spcht descriptor format. Further instructions and how to use it are in the [SPCHT.md](SPCHT.md) file



## Requirements

* python3-rdflib 
* python3-elasticsearch
* python3-dev
* unixodbc-dev

## Development Notes

Apart from very German capitalization of random words i would also like to lose a word about the program and plug-ins i used for this, while the master can work with everything i would not consider myself as such.

I used [Intellij Pycharm](https://www.jetbrains.com/pycharm/)  with the following plug-ins:

* Rainbow Brackets - makes it easier to find the right entry point
* GitToolBox - for people that just forget most of the functionality git offers
* Comments Highlighter - Port of the Vs Code Plug-in _Better Comments_, makes comments a bit more colorful
* CodeGlance - provides a neat minimap to the code
* a bunch of standard plug-ins that come with Pycharm when you just install it

for writing markdown files i used [Typora](https://typora.io/).

