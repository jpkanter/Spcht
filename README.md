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

### finc2rdf.py

Takes a json formated Apache Solr Database output and formats it to a json-ld formated rdf file.

### ldj2rdf.py

Converts, as far as i see it, input from `finc2rdf.py` and converts it to a proper rdf format

## solr2virtuoso_bridge.py

The main piece of work here, developed to do all the heavy lifting. It introduces a setting/descriptor format to actually map corresponding data fields from the apache solr database to sparql queries. The functions in the code do not actually require a solr as input source, if you have any other way to retrieve pure _jsoned_ dictionaries with a simple file structure it should also work. Or at least should be possible to easily modify the code to use such a source.

### the salmon descriptor format

> "We do not have enough obscure standards." - No-one ever

Technically this is a _json_ file describing the way the script is supposed to map the input to actual linked data. This was done to keep it adjustable and general so others might be able to use it. There is no specific reason for the name except that i had salmon for lunch.

Lets get started with an example:

```json
{
    "id_source": "dict",
    "id_field": "id",
    "id_fallback": {
        "source": "marc",
        "field": "001",
        "subfield": "none"
    },
    "nodes": [
        {
            "name": "ISBN",
            "source": "dict",
            "graph": "http://purl.org/ontology/bibo/isbn",
            "field": "isbn",
            "type": "optional",
            "fallback": {
                "source": "marc",
                "field": "020",
                "subfield": "a"
            }
        },
        {...},
        {...},
         ...
    ]
}
```

The basic structure is a core entry for the graph and a list of dictionaries. Each dictionary contains the mapping for one data field that _can_ result in more than one graph-node.

#### actual mapping:

* Fields labeled with a prefix `id_` to be found in the head information respectively the root contain the basic informations about the graph we are trying to construct. It behaves in many ways the same as the node-dictionaries including the fall-back excluding only the need for a graph
* `nodes` - this contains the description of all nodes. I renounced the idea of calling it *fish-bones*, a metaphor can only be stretched so far.
* `name` - the name doesn't serve any purpose, you may display it while processing but its just there so you have a better overview, while this is superfluous for the program human readability seems like something to wish for
  * Values: `anything`
* `source` - source for the data field, if its a dictionary `field`is the key we are looking for. If the source is to be found in a corresponding MARC21 entry `field` describes the Entry Number ranging from 000 to 999. There is also a necessary `subfield` as most MARC21 entries do not lay on the root.
  * Values: `dict` and `marc`
* `graph` - the actual mapping to linked data. Before sending sparql queries the script will shorten all entries accordingly. If you have multiple entries of the same source they will be grouped. I decided that for this kind of configuration file it is best to leave as many information to the bare eye as possible.
  * Values: `a fully qualify graph descriptor string`
* `field`, `subfield` - describes in which linear data field the corresponding data can be found. `subfield` is only really needed if you work with a MARC21 entry. _The leading 0 of the MARC21 entry gets omitted, `020` equals `20`._
  * Value: `a string`
* `alternatives` - there is possibility that a specific data field isn't always available in your given database but you know there are other keys that might contain the desired data. `alternatives` is a list of different dictionary keys which will be tried in order of their appearance.
  * Values: `a list of strings [str, str, str]`
* `fallback` - if the current specified source isn't available you may describe an alternative. Currently only "_marc_" or "_dict_" are possible entries. You can use the same source with different fields to generate a fall-back order. _eg. if dict key "summer" isn't available the fall-back will also look into the dict but use the field "winter_ You may also just use `alternatives` for this.
  The sub-dictionary of `fallback` contains another dictionary descriptor. You may chain sub-dictionaries _ad infinitum_ (or the maximum dictionary depth of json)
  * Values: `an entry dictionary {}`
* `type` - if everything fails, all fall backs are not to be found and all alternatives yield nothing and the `type` is set to mandatory the whole entry gets discarded, if some basic data could be gathered the list of errors gets a specific entry, otherwise there is only a counter of indescribable mapping errors being incremented by one. 
  * Values: `optional`, `mandatory`
* other fields: the salmon descriptor format is meant to be a human readable configuration file, you can add any field you might like to make things more clear is not described to hold a function. For future extension it would be safest to stick to two particular dictionary-keys: `name` and `comment`
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

