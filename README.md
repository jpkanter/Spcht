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

### the Spcht descriptor format

> "We do not have enough obscure standards." - No-one ever

Technically this is a _json_ file describing the way the script is supposed to map the input to actual linked data. This was done to keep it adjustable and general so others might be able to use it. The name is in tradition of naming things after miss-written birds.

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

#### Node Mapping

##### Special Head Node

Outside of the `nodes` list is a special node that got the suffix`id_` instead of the actual names. It works exactly the same as the every other node but contains the id. It would be possible to build the SPCHT Format without the main node but its relevance is increased by the special position as its unique and should be treated with care.

Every other node is mapped in the aforementioned `node` List. Its supposed to be a list of dictionaries which in turn contain a note each. The process will abort if no information for a mandatory node can be found.

##### General Node Architecture

Each Node contains at least a `source`, `graph` and `type` field which define the surrounding note. It can also contain a `fallback`, `filter` or `match` field. Every fall back can contain another fall back. You can add any other *non-protected* field name you desire to make it more readable. The Example file usually sports a `name` dictionary entry despite it not being in use.

* `nodes` - this contains the description of all nodes. I renounced the idea of calling it *feathers*, a metaphor can only be stretched so far.
  
  * Values: a list of dictionaries.
* `name` - the name doesn't serve any purpose, you may display it while processing but its just there so you have a better overview, while this is superfluous for the program, human readability seems like something to wish for. While not used for any processing the error reporting engine of the format checker uses it to clarify the position of an error but doesn't need it desperately.
  
  * Values: `any string`
* `source` - source for the data field, if its a dictionary `field`is the key we are looking for. If the source is to be found in a corresponding MARC21 entry `field` describes the Entry Number ranging from 000 to 999. There is also a necessary `subfield` as most MARC21 entries do not lay on the root.
  
  * Values: `dict` and `marc`
* `graph` - the actual mapping to linked data. Before sending sparql queries the script will shorten all entries accordingly. If you have multiple entries of the same source they will be grouped. I decided that for this kind of configuration file it is best to leave as many information to the bare eye as possible.
  * Values: `a fully qualify graph descriptor string`
* `fallback` - if the current specified source isn't available you may describe an alternative. Currently only "_marc_" or "_dict_" are possible entries. You can use the same source with different fields to generate a fall-back order. _eg. if dict key "summer" isn't available the fall-back will also look into the dict but use the field "winter_ You may also just use `alternatives` for this if your source is **dict**.
  The sub-dictionary of `fallback` contains another dictionary descriptor. You may chain sub-dictionaries _ad infinitum_ (or the maximum dictionary depth of json)
    * Values: `a "node" dictionary {}`
* `required` - if everything fails, all fall backs are not to be found and all alternatives yield nothing and the `required` is set to mandatory the whole entry gets discarded, if some basic data could be gathered the list of errors gets a specific entry, otherwise there is only a counter of indescribable mapping errors being incremented by one. 
  * Values: `optional`, `mandatory`
* filter
* match
* type - per default each entry that is found is interpreted as if it would be a literal value. Due Mapping and the manual building of entries its entirely possible that some entries are actually another triple. in that case this has to be announced so that the sparql interpreter can take appropriate steps.
  * Values: `literal` *(Default*), `triple`
* other fields: the spcht descriptor format is meant to be a human readable configuration file, you can add any field you might like to make things more clear is not described to hold a function. For future extension it would be safest to stick to two particular dictionary-keys: `name` and `comment`
  
##### source: dict

The primary use case for this program was the mapping or conversion of content from the library *Apache Solr* to a *linked data format*. The main way *solr* outputs data is as a list of dictionaries. If you don't have a *solr* based database the program might be still of use. The data just has to exists as a dictionary in some kind of listed value unit. The **source:dict** format is the most basic of the bunch. In its default state it will just create a graph connection for the entry found, if there is a list of entries in the described dictionary key it will create as many graphs. It also offers some basic processing for more complex data. If the `field` key cannot be found it will use `alternatives`, a list of dictionary keys before it goes to the fall-back node.

It is possible to **map** the value of your dictionary key with the field `mapping`, it is supposed to contain a dictionary of entries. If there is a default mapping it will always return a value for each entry (if there is more than one), if no default is set it is possible to not get a graph at all. For more complex graph it is possible to use the special mapping dictionary key `$ref` to link to a local *json* file containing the mapping. You *can* mix a referenced mapping with additional entries. It is possible to default to the original value of the field with the special value `$inherit`

* `field` - the key in the dictionary the program looks for data
  
  * Values: `a string containing the dictionary key`
* `mapping` - a dictionary describing the *translation* of the content of the specified field. If no `mapping` is defined the face value will be returned.
  
  * Values: `a flat dictionary {"key": "value", ..}`
* `mapping_settings` - further settings or modifiers for the mapping, formerly it was all in the `mapping` parameter but that meant data and function were intermixed which could've resulted in problems further down the line, the additional complexity due an additional parameter is the price for that. `mapping` works completely without a corresponding `mapping_setting`, with the exception of the `$ref` option it does nothing on its own. The way `$ref` works is that mapping gets filled in preprocessing and then deleted
  * Values: a flat dictionary with a number of pre-defined keys, additional information gets ignored
    * `$ref` - Reference to a local file that gets filled into the `mapping`
    * `$type` - can either be `regex` or `rigid`. *Rigid* matches only exact keys including cases, *regex* matches according to rules. Might be cpu intensive.
    * `$defaut` - a default value that is set when there is no value present that matches a key/regex, can be set to `True` to copy the initial value
* `alternatives` - there is possibility that a specific data field isn't always available in your given database but you know there are other keys that might contain the desired data. `alternatives` is a list of different dictionary keys which will be tried in order of their appearance.
  
  * Values: `a list of strings [str, str, str]`
  
##### source: marc

As of now a *Marc21* data source is inherently part of the main dictionary source, mostly to be found in a special, very big key. It contains the entire original *Marc21*-entry as received from another network. Usually it needs additional interpreting to be useful. The current source contains some methods to extract informations from the provided *Marc21* file. In its essence it just transform the *MARC21* information into a dictionary that follows the *MARC21*-structure.  There are minor differences in between *Marc21*-Data sources that might have to be handled with care and maybe additional preprocessing. The work on this part is not even nearly done.

The following kinds of key are currently possible

* `field` - analogue to the way it works with **source:dict** this is a mandatory field for the `Marc21` Source, its usually limited to the numbers 1 to 999, the actual value is arbitrarily but non-numerical values will not make sense. The background script transforms the actual raw `Marc21` Data into a dictionary that will be accesses very similarly to the **source:dict** one.
  
  * Value: `a singular string (str)`
* `subfield` - every  **source:marc** requires *either* a `subfield` or a `subfields` entry. If both are present `subfield` takes the priority (for being first in the list of used parameters which in turn ignores the following parameter subfields). 
  *While it makes little sense to have both subfield and subfields it will not break the* SPCHT *format but when the format checker will throw a warning cause this is likely the result of an accident.*
  
  * Value: `a single string (str)`
* `subfields` - 
  
  * Value: `a list of strings [str, str, str]`
  
    *Note: a list of Strings means that even a singular element has to be wrapped in a list with length 1, example: `['b-field']`, you can, in theory, always use subfields instead of subfield with singular item lists. Although the example files have some use cases for subfield='none' where there is actually no subfields and just a value for the field itself, those wouldn't be accessible with subfields*
  
* subfields_mode - strict, default: flex

#### actual mapping:


* `field`, `subfield` - describes in which linear data field the corresponding data can be found. `subfield` is only really needed if you work with a MARC21 entry. _The leading 0 of the MARC21 entry gets omitted, `020` equals `20`._
  
  * Value: `a string`
  

  

  

  


#### a basic mapping to copy and paste

```json
{
  "id_source": "",
  "id_field": "",
  "nodes": [
    {
      "name": "your text here",
      "source": "",
      "graph": "",
      "field": "",
      "type": "optional"
    }
  ]
}
```
### in Development

With the two current types not every kind of information can be mapped properly. At least two additional node sets are planned to be realized:

#### MARC multivalued - marcmv

```json
{
    "name": "optional informations here",
    "source": "marcmv",
    "graph": "https://domain.tld/mapping/element/#1234",
    "type": "optional",
    "field": "245",
    "subfields": ["a", "c"],
    "separator": ",",
    "fallback": {}
}
```

It contains the `subfields` entry instead of a single `subfield` _(without the s)_

The parameter `separator` is optional, per default it will separated the subfields of the marc entry by one whitespace _(" ")_

#### Dictionary Map - dictmap

```json
{
    "name": "some descriptive stuff",
    "source": "dictmap",
    "graph": "https://domain.tld/mapping/element/#4321",
    "type": "optional",
    "field": "stuff2map",
    "mapping": {
        "default": "this is mandatory",
        "entry1": "other words",
        "entry2": "more words"
    }
    "fallback": {}
}
```

Some fields are not displaying exactly what we want so we need to translate the information to some other kind of info. The Descriptor provides a mapping for this entry, the field `mapping` has to be a dictionary and must always contain at least one entry: "default". The entry is matched as it, although a regex like matching system might be constructed later.

This source is similar to the normal _dict_ type but does not support the use of the `alternatives` field.

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

