# the Spcht descriptor format

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
            "required": "optional",
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

Goal of the whole format was to provide a somewhat easy way for a librarian to map specific data from a database into a linked data format and create something that is accessible via a triplestore. There are other projects like **Meta Facture** that solve a similar problem in the same context. Especially *metafacture* is based on a XML which is somewhat unwieldy. Furthermore its too deep for what is to be accomplished with SPCHT. SPCHT only sees itself as a format that provides the raw formated result data, not the logic to actually insert it into a triplestore. It was created as a the solution for a set task and has some boundaries where the set task was to specific for that task. I made the cut to separate the SPCHT Format that might be used elsewhere from the *solr2virtuoso* Bridge project that was very singular in its vision.

As of now this goal is not totally achieved and further steps have to be taken.

## The general Process



#### Node Mapping

##### Special Head Node

Outside of the `nodes` list is a special node that got the suffix`id_` instead of the actual names. It works exactly the same as the every other node but contains the id. It would be possible to build the SPCHT Format without the main node but its relevance is increased by the special position as its unique and should be treated with care.

Every other node is mapped in the aforementioned `node` List. Its supposed to be a list of dictionaries which in turn contain a note each. The process will abort if no information for a mandatory node can be found.

##### General Node Architecture

Each Node contains at least a `source`, `graph` and `type` field which define the surrounding note. It can also contain a `fallback`, `filter` or `match` field. Every fall back can contain another fall back. You can add any other *non-protected* field name you desire to make it more readable. The Example file usually sports a `name` dictionary entry despite it not being in use.

* `nodes` - this contains the description of all nodes. I renounced the idea of calling it *feathers*, a metaphor can only be stretched so far.
  
  * Values: a list of dictionaries.
* `name` - the name doesn't serve any purpose, you may display it while processing but its just there so you have a better overview, while this is superfluous for the program, human readability seems like something to wish for. While not used for any processing the error reporting engine of the format checker uses it to clarify the position of an error but doesn't need it desperately.
  *Note*: the name is also used in the [Spcht Checker Gui](https://github.com/jpkanter/spcht_checker_gui) as display name, its still strictly unnecessary but adds visual cues
  * Values: `any string`
* `source` - source for the data field, if its a dictionary `field`is the key we are looking for. If the source is to be found in a corresponding MARC21 entry `field` describes the Entry Number ranging from 000 to 999. There is also a necessary `subfield` as most MARC21 entries do not lay on the root.
  
  * Values: `dict` and `marc`
* `graph` - the actual mapping to linked data. Before sending sparql queries the script will shorten all entries accordingly. If you have multiple entries of the same source they will be grouped. I decided that for this kind of configuration file it is best to leave as many information to the bare eye as possible. You can define a new graph for a fall back if there ever arises the need to do it in one node. If you don't do so the fall back node will inherit the his `graph` from the parent node. (*if you have a very exotic 4 staged node and redefine the graph in the second fall back, the third will use the graph of its parent which is the second fall back, not the root node. I honestly see not a use case for this but the functionality was easily enough to obtain. **Note: you can change the graph but not the type of that node in fall backs, which limits future use cases***)
  * Values: `a fully qualify graph descriptor string`
* `fallback` - if the current specified source isn't available you may describe an alternative. Currently only "_marc_" or "_dict_" are possible entries. You can use the same source with different fields to generate a fall-back order. _eg. if dict key "summer" isn't available the fall-back will also look into the dict but use the field "winter_ You may also just use `alternatives` for this if your source is **dict**.
  The sub-dictionary of `fallback` contains another dictionary descriptor. You may chain sub-dictionaries _ad infinitum_ (or the maximum dictionary depth of json or maximum depth of recursion in python)
    * Values: `a "node" dictionary {}`
* `required` - if everything fails, all fall backs are not to be found and all alternatives yield nothing and the `required` is set to mandatory the whole entry gets discarded, if some basic data could be gathered the list of errors gets a specific entry, otherwise there is only a counter of indescribable mapping errors being incremented by one. 
  * Values: `optional`, `mandatory`
* `type` - per default each entry that is found is interpreted as if it would be a literal value. Due Mapping and the manual building of entries its entirely possible that some entries are actually another triple. in that case this has to be announced so that the sparql interpreter can take appropriate steps.
  **Do notice that type applies to all fall backs and alternatives, any match will be handled as either triple or literal, the parameter has to be specified in the top level of the node**
  * Values: `literal` *(Default*), `triple`
* `cut` - removes a part of the final value after mapping and filtering has taken place but before anything gets pre- or appended to the resulting value
  * Values: `str` of any Regex Valid term, properly escaped, Example: `(\\(DE-588\\))`, removes "(DE-588)" of `(DE-588)132140349` and returns just `132140349`
* `match` - this uses a regex match to filter out the content of an entry, the field value is matched against the value of the `match` entry, if it does not get at least one match the value gets ignored and no triple is created
  * Values: `str` of any Regex-valid term, properly escape, Example: `(\\(DE-588\\))[0-9]*` matches Value `(DE-588)132140349`
* `prepend` & `append`: both add literal text to the beginning and the end of any give value. This is the last step that gets applied to any given value regardless of source
  * Values: any `str` 
* `saveas` - **WIP** this function saves the final value of the specified field or key into a list. That value is **without** the content of `prepend` and `append` but **with** the filter provided by `match` and `cut`.  The List can later be retrieved with the function `getSaveAs`. This list *can* contain duplicates depending on the processed content. Exact duplicated values can be filtered out with `CleanSaveAs`
  * Value: a string that specified the dictionary key for the name of the list
* other fields: the spcht descriptor format is meant to be a human readable configuration file, you can add any field you might like to make things more clear is not described to hold a function. For future extension it would be safest to stick to two particular dictionary-keys: `name` and `comment`
  *Note:* the aformentioned Spcht Gui program also uses the comment section as part of its displayed attributes, it matches every entry that starts with "comment*" which makes multiple comments possible.
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
* `graph_field` - While the graph is normally constant and defined by the `graph` field it can also be relative to the value of another field. If you set `graph_field` you also **must** set either `graph_map_ref` or `graph_map`. It will **always default** to the graph specified by `graph`.  If both the value of `graph_field` and `field` are a list, both list have to be the same length and each element will be paired with the same position on the other list. 
  *This key-type was created in response to a specific database field that contained a paired list of contributers and the type of contribution that person added, its written universally to be reused and to stay within doctrine*
  **Note:** due the strict nature of `graph_field` and `field` in pair an also defined `alternatives` will be ignored
  * Value: `a string`
* `graph_map` - this works analogue as `mapping`
  * Value: `a flat dictionary of strings {"key": "value", ..}`
* `graph_map_ref` - Unlike the `mapping_settings` key this has only a singular purpose, therefore it only contains a string pointing to a **local** file containing the appropriated flat dictionary for the mapping. If both `graph_map` and `graph_map_ref` are defined the content of `graph_map` gets priority and entries with the same key in the referenced file will be ignored.
  * Value: `a string pointing with the filepath to a local file` *Files handled by OS, networked resources in LAN might work*
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
      "name": "Some Text that is used in debugging but not elsewhere",
      "source": "dict",
      "graph": "",
      "field": "",
      "required": "optional"
    }
  ]
}
```
## The Class
Originally  the entire logic behind the SPCHT format was written as a set of procedures just churning away. Later the need for a cleaner solution has arisen and everything was remodeled for a object oriented solution. The *Spcht* Class was created, it holds a bunch of variables and offers a few public functions. Some work without an instance of the class. Each instance of a *Spcht* Objects holds the information of one descriptive file.

### non-instantiated functions

```python
def is_dictkey(dictionary: dict, *keys) -> bool
def list_has_elements(iterable) -> bool
def list_wrapper(some_elements: any) -> list
def all_variants(variant_matrix: list) -> list
def match_positions(regex: str, string: str) -> list
def insert_list_into_str(list_of_strings, string, regex, pattern_length, strict=True)
def extract_dictmarc_value(raw_dict, sub_dict, field="field", subfield="subfield")
def is_float(string: str) -> bool
def is_int(string: str) -> bool
def if_possible_make_this_numerical(value: any) -> str or int or float
def slice_marc_shorthand(string: str) -> tuple
def validate_regex(regex_string: str) -> bool
def marc21_fixRecord(record, validation=False, replace_method="decimal")
def marcleader2report(marc21_leader, output=sys.stdout)
def check_format(descriptor, out=sys.stderr, i18n=None)
```

These functions provide some utility which is mostly used internally for the other functions but might as well be useful elsewhere. They are written in a way that makes reusing them easy, although most of them are simple enough to not bother

| Function                             | Purpose                                                      |
| ------------------------------------ | ------------------------------------------------------------ |
| **is_dictkey**                       | Returns true when *all* provided keys are present in the provide dictionary |
| **list_has_elements**                | Checks if an iterable has any elements *Note, this function seems verbose and unnecessary* |
| **all_variants**                     | A given list containing additional lists of elements will be iterated so all possible combination will be returned as a list of lists (a matrix, or 2-dimensional array) |
| **list_wrapper**                     | If the input is already a list nothing happens, otherwise this returns [input] |
| **match_positions**                  | While standard regex functions only return one position, this returns a list of start and stop of the provided pattern in the string |
| **insert_list_into_string**          | This basically does `{} {} {}".format(*list)` but will also do checks whether enough elements are provided or not. It also implements a custom insert method instead of `str.format` |
| **extract_dictmarc_value**           | Convenience function to abstract the retrieval of data from different datasources |
| **is_float**                         | checks if a string could be a float                          |
| **is_int**                           | checks if a string could be an int                           |
| **if_possible_make _this_numerical** | Transforms a give string, if possible, to the lowest type of numerical value. String > Integer > Float |
| **slice_marc_shorthand**             | Returns a tuple of field and subfield of a given *Marc 21 Shorthand* of the structure `624:a` |
| **validate_regex**                   | Returns true if the provided string is valid regex, false if not |
| **marc21_fixRecord**                 | Replaces some unicode Characters like ö, ä and ü that came through the database to the interpreter |
| **marcleader2report**                | Gives a verbose report about the content of the provided Marc21 leader string (length = 24 Byte) |
| **check_format**                     | Returns true if the provided descriptor (in dictionary Spcht format) is a valid Spcht descriptor, otherwise false and an error print. (*Might throw exceptions in later iterations*) |



### instantiated functions

```python
def debug_print(self, *args, **kwargs)
def debug_mode(self, status)
def export_full_descriptor(self, filename, indent=3)
def load_json(self, filename)
def descri_status(self)
def getSaveAs(self, key=None)
def cleanSaveAs(self)
def load_descriptor_file(self, filename)
def get_node_graphs(self)
def get_node_fields(self)
def set_default_fields(self, list_of_strings)
def processData(self, raw_dict, graph, marc21="fullrecord", marc21_source="dict")
def __init__(self, filename=None, check_format=False, debug=False)
```

| Function                   | Purpose                                                      |
| -------------------------- | ------------------------------------------------------------ |
| **debug_print**            | Used to only print something to `self.debug_out` when the `self._debug` variable is set to true |
| **debug_mode**             | Toggles the debug mode with True and anything else, enables some debug prints in the processing process |
| **export_full_descriptor** | Saves the "compiled" (with all loaded referenced) descriptor file at the specified place as json |
| **load_json**              | encapsulated json file loading, throws a variety of exceptions if the json file is invalid or anything else went wrong |
| **descri_status**          | Returns true if a descriptor file was successfully loaded into this instance of Spcht |
| **getSaveAs**              | returns (all/a key) of the `self._saveas` dictionary that was saved through the processing up till now |
| **cleanSaveas**            | Removes duplicated entries of the `self._saveas` Variable    |
| **load_descriptor**        | Loads the specified, local descriptor file and validates it.  Returns true when successfull |
| **processData**            | Main function, inputs a flat dictionary of one set of data that get mapped according to the descriptor file. Requires successfully loaded descriptor file. |
| **get_node_graphs**        | Returns a list of strings of all used graphs in the loaded spcht file, can theoretically return an empty list |
| **get_node_fields**        | Returns a list of strings of all used fields, the field `fullrecord` is always included per default |
| **set_default_fields**     | Changes the default list of default fields consisting of `fullrecord` to something else |



### public variables

```python
self.std_out = sys.stdout
self.std_err = sys.stderr
self.debug_out = sys.stdout
```

### Private functions





### Ideas // Planning

