# Spcht Descriptor Format - in-depth explanation

## Introduction

The processing operation takes a set of data and creates *Linked Data* Triples of them. For that operation, one has to understand how the lowest unit in any triplestore looks:

`<subject> <predicate> "object"` or in more practical terms: 

`<https://data.finc.info/resources/0-1172721416> <dcmitype/issued> "2002"`

The first part is the so called *subject*, the middle is the *predicate* and the last is the *object*, the first two have to be some kind of *UR**I*** (not to be confused with an *UR**L***) but the *object* can be a literal string or another *URI*, referencing another object. A *triplestore* usually contains a tree-like structure, known as graph. 

The input data for which the Spcht descriptor was originally written is inherently linear and not tree-like, there is a distinct 1-dimensional character of those data that makes the transformation from a classical database considerable easier.

The data, JSON-formatted, looks like this: 

```json
{
    "id": 234232,
    "title": "Booktitle",
    "author": "Brechthold Bernd",
    "author_role": "aut",
    "author_gnd": 118514768
}
```

To get a tree-like structure, or at least the core of it so called *nodes* are being generated.

To generate any node from here, we are taking one part, the *ID* as unique part for our subject, combined with a defined graph `https://example.info/data_,` we get a full subject called `https://example.info/data_234232`, this forms the base root upon we can craft additional properties for this node.

We know the title and author of the book in this example, and which 'role' the author had in the creation of the book. A knowledgeable librarian chooses what properties match those data best and defines a *Spcht node* for each of those properties. (Or uses the recommendations of various organisations.)

In case of the title we take `dcmieterms/title` as agreed *predicate* for this kind of information, with this mapping defined we now have all three parts of our node defined. The end result would look like this:

`<https://example.info/data_234232> <dcmiterms/title> "Booktitle"`

While literal strings are easy to understand, they only possess a limited use for any further data operation. For this book we know also an author and what 'role' the author of this book had (they might have been a translator or publisher for instance). Other triplestores and databases have an extensive library of people that is fortunately linked by the key `author_gnd`, of the knowledge of the database our librarian can now write another node-description, stating that the field `author_gnd` contains an id that can be used to create an *URI* to further data. The result would look like this:

```
<https://example.info/data_234232> <dcmiterms/creator> 
	<http://d-nb.info/gnd/118514768>
```

Also of interest, we 'map' our author as 'creator' of this book instead of a generic 'contributor'. With this new data and many more similar nodes we can now use the data for linked data operations. To achieve all this from a simple number that is given in the data we need some tools Spcht provides that are explained in the following text.

## Simplest structure

A Spcht descriptor file contains roughly two parts, the initial **Head** that describes the ID part of a triple and a list of **Nodes**. The Head itself is a node in itself and uses the same functions as any other node with the difference that the result must be a singular, unique value.

```json
{
    "id_source": "dict",
    "id_field": "id",
    "nodes": []
}
```

This would do nothing, there might be a mapped *ID* per dataset, but as there is no actual data to create triples, there nothing will be created. To achieve the two triples we discussed earlier `nodes` needs to contain actual content:

```json
"node": [
  {
    "source": "dict",
    "predicate": "http://purl.org/dc/terms/title",
    "field": "title",
    "required": "optional"
  },
  {
    "source": "dict",
    "predicate": "http://purl.org/dc/terms/creator",
    "field": "author_gnd",
    "prepend": "http://d-nb.info/gnd/",
    "required": "optional",
    "type": "uri"
  }
]
```

There is already a new  field that wasn't discussed yet, `prepend`. Its one of the trans formative parameters that can be included into any node. It appends its text before the actual value provided by the data-field, in this case, the static part of a link. Used on the *jsoned* output from a database that contains those the three fields `id`, `title` and `author_gnd` we would get two triples as discussed in the introduction.

There also two other fields that will be seen in any Spcht-node: `required` and `source`. Those properties serve as switch for different behaviours while processing the data. `required` is a very simple yes/no question, it can only have two values: `mandatory` or `optional`. If a field is not present or otherwise ruled out (*for example by `match`*) and a given node is mandatory the entire data-set is discarded and the process will continue to the next set. Per default only the id in the root-node is mandatory as graph-creation would simply not be possible without an unique identifier.
`source` describes from where the Spcht-process should take the data, a given data-set is by default assumed to be in the format as shown above, a key-value relationship where the value might be a list of simple values. Or in other words, the key on the left always points to either a value like a number or a string or a list (designated by square brackets `[]`) that contains such values. But deviations are possible as special fields can contain special data, as the many data-sets of the [UBL](https://www.ub.uni-leipzig.de) that have a field called `fullrecord`, containing [Marc 21](https://en.wikipedia.org/wiki/MARC_standards#MARC_21) data. Spcht posses procedures to unpack and access such data, with `"source": "marc"` and a present marc-field can be almost normally accessed. There are some edge cases that will be explained further in the Chapter **Source: marc**


## Trans-formative operations

While the literal value of any given data field might be good enough for most use cases there is an expected number of values that wont work without any alterations. To solve this problem, there is a set of operations to transform the extracted value in different ways, these are as follows:

* `prepend` - appends text **before** the value

* `append` - appends text **after** the value

* `cut` & `replace` - replaces a given regex match with a new text

* `insert_into` (& `insert_add_fields`) - inserts the given value in the position of a placeholder inside a string

  *Note: technically does the combination of `append` & `prepend` achieve the exact same thing as `insert_into`, it might be more clear in intend. The use of `insert_add_fields` is the designated use of that function*
  
* `mapping` - Replaces a given value completly with a new one according to a dictionary

### Append & Prepend

The first example shows a simple node with an addition to the retrieved value from a given data-set, the field-value `title` is *augmented* with the text "BOOK:" in the beginning and a " (local)" at the end. Both are static texts. A given title (in this case for a book), like "Faust" would result in a triple like this:

`<RESSOURCE> <dcmiterms/title> "BOOK:Faust (local)"`

```json
{
  "source": "dict",
  "field": "title",
  "predicate": "http://purl.org/dc/terms/title",
  "prepend": "BOOK:",
  "append": " (local)",
  "required": "optional"
}
```

### Insert_into

The same effect can be achieved by using `insert_into`:

```json
{
    "source": "dict",
    "field": "title",
    "predicate": "http://purl.org/dc/terms/title",
    "insert_into": "BOOK: {} (local)",
    "required": "optional"
}
```

The `{}` is a placeholder symbol, this is derived from the Python roots of the process. There can only be one placeholder symbol at the time as there is only one variable (the extracted value from the `title` field) that can be inserted. But `insert_into` is mightier than that! It is possible to pull an arbitrary amount of fields and insert those field-values in a placeholder text. Let us assume a use case where (a part) of our data looks like this:

```json
{
    "title_sub": "eine Tragödie",
    "title_short": "Faust",
    "author_role": ["aut"],
    "author": ["Goethe, Johann Wolfgang von"],
    "ctrlnum": [
      "(DE-627)657059196",
      "(DE-576)9657059194",
      "(DE-599)GBV657059196",
    ],
}
```

For some reasons the title is split in two parts and we don't have a suitable data-field that contains the full title. *There is also additional data that will be used for further examples.*

To combine our data we leverage the abilities of `insert_into` with the addition of the optional node-component `insert_add_fields` which defines additional fields that will be inserted into the placeholders:

```json
{
    "source": "dict",
    "field": "title_short",
    "predicate": "http://purl.org/dc/terms/title",
    "insert_into": "{}: {}",
    "insert_add_fields": ["title_sub"],
    "required": "optional"
}
```

The actual string to insert into is quite simple, it barely contains more than two placeholders and a colon with a space. The content of `insert_add_fields` is more interesting as the field name is written in square brackets `[]`. This defines an **array** in *JSON* (*known as list in Python*), the data-structure used in all Spcht-context. A *JSON*-list can contain any number of data and data-types (for example, the nodes itself reside in a list that contains so called *dictionaries*), the order of data in a list is preserved and duplicates can be present. If, for some reason, you required, to insert the same value twice in at different positions in a placeholder. In this notation the first placeholder will always contain the `field` value, the second placeholder the first position of `insert_add_fields`  will be the second placeholder, the second *add_fields* position will be the third placeholder and so on. Therefore, if you want to set the first placeholder to the content of the first `insert_add_fields` content, you have to swap fields with the one of `field`. There is one caveat here, other operations like `cut`, `replace`, `append`, `prepend` and `mapping` will actually work in concert with `insert_into` but **only** for the first value defined by `field`

### Cut & Replace

The first use case for the Solr2Triplestore bridges assumes that the source-data set, gathered from its solr-source cannot be changed. Therefore is all data that is retrieved "as it". Any necessary transformation has to happen in the descriptor, as seen in the previous functions adding text is a simple matter, replacing text is slightly more complex. In the above example is the key `ctrlnum` that contains different numbers according to some other designation in the brackets. Our fictive mapping only cares for the number after the brackets, and that is where `cut` & `replace` comes into play.

*Note: for simplicity-sake i omitted `required`, `source` and `predicate` as our focus lies on the current mechanic and not the basic structure itself*

```json
{
    "field": "ctrlnum",
    "cut": "^(\\(.*\\))",
    "replace": "",
}
```

The **Regex** looks a bit complicated but is mostly cause the round bracket had to be escaped and then the escaping backslash had to be escaped as well. If entered in a page like [Regex101](https://regex101.com) or [RegexR](https://regexr.com/) it shows that it just matches the beginning of any one given string that is within round brackets. The processing then continues to replace it with an empty string, returning us the pure number from above. All this results us:

​	**RESULT:** `["657059196", "9657059194", "GBV657059196"]`

## Permissive operations

While transforming given data is a valuable tool to make otherwise too entangled values work there is a great possibility that a data set contains data that just does not fit into the grand scheme of things. For such values two tools are at your disposal: 

* `match`
* if conditions

### Match

The function `match`is a simple pre-filter for individual values that applies before other transformations take place. Again **Regex** is utilised to achieve the desired effect. In the example data a bit above there were three entries for the field `ctrlnum`, we already filtered out the number in the round brackets but now we decided that we only really need one number:

```json
{
    "field": "ctrlnum",
    "match": "^(\\(DE-627\\)).*$",
    "cut": "^(\\(DE-627\\))",
    "replace": ""
}
```

The `match` **Regex** looks a bit more complex as i wanted to match the entire string. The `cut` part from above can also now simplified as `match` takes place before other steps, and therefore only needs to cut any given string that contains "*(DE-627)*". The above example in `cut` & `replace` would have worked too, but this way the workings are a bit more clear. The above node would result in the following value:

​	**RESULT**: `"657059196"`

### IF Condition

If filters out the entire node and all `field` values if the condition is not met.

This function is a lot more complex than the first one, therefore we start with the most complicated example to break it down:

```json
{
    "field": "author",
    "if_field": "ctrlnum",
    "if_condition": ">",
    "if_value": "657059195",
    "if_match": "^(\\(DE-627\\)).*$",
    "if_cut": "^(\\(DE-627\\))",
    "if_replace": ""
}
```

The basic idea is that we compare a given value against another another:
	`dynamic_value` `COMPARARTOR` `static_value` or written out:
	`25 >= 20` **-> TRUE**

We see that  there is again `cut`, `replace` and `match`. But this time they all have a prefixed `if_`. These are strictly optional but provide additional functionality for edge cases. As we already know what they do we will ignore them for now.

`if_field` is an arbitrary key in the given data-set that can be any field in the available data, even the actual `field` that is getting mapped. The value retrieved from that data-set key is used for the left side of the comparison, therefore the *dynamic* part.

`if_condition` designates the comparator, as Spcht is made to be written by humans there is some leeway in the exact possible wording, it has to be one of the following list:

* "equal", "eq", "greater", "gr", "lesser", "ls", "greater_equal", "gq", "lesser_equal", "lq", "unequal", "uq", "=", "==", "<", ">", "<=", ">=", "!=", "exi"

There is one special condition called `exi`, it only tests for the existence of the designated `if_field` in the data and nothing more, an `if_value` isnt necessary anymore in this case.

`if_value` describes the static portion of the comparison, instead of a singular value this can also be a list, the comparison can then only be *equal* or *unequal*. If the value is a list it will return **TRUE** if **any** value is equal to `if_field`, if tested for unequality it will return **FALSE** if **any** values ist equal to `if_field`

As visible in the example we test if the value of `if_field` is greater as the *STRING* "657059195" as designated by the quotation marks. The comparative process will try to convert any string to a number if possible. As most databases do not return clean *INTEGER* Values.

As mentioned before, some limited transformation of the `if_field` value is possible, besides the shown usage `prepend` and `append` will also work. There is only one small difference: All trans-formative and permissive checks will be executed before the if-comparison takes places. If `if_field` and `field` are the same data-set key any transformation done to `if_field` will have **no** bearing at any value `field` might contain.

#### If-Edge Case: infinite negativity

If the key for `if_field` can not be found the condition can still return true and will **not** automatically break the processing of that node.

If the `if_condition` is **NOT** *equal*, *greater than* or *greater or equal than* if condition will return **TRUE**. The assumption here is that a non-existence value will always be smaller and unequal of any given value. Absence is interpreted as *infinite negativity*.

## Mapping Operations

Instead of just appending or swapping out some parts of the value it is also possible to replace entire set of values with new ones, for this purpose the `mapping` function exists. In our way above example we got the key `author_role` with the value `aut`. Unsurprisingly the author is also the author of a given book, this must not always be the case but that is besides the point. Roles like that of an author can be neatly mapped to a nice URI like `https://id.loc.gov/vocabulary/relators/aut.html`. For this singular field we could actually work with `append` and `prepend` but that would do no good if we had a list of roles the author had in, for example, a movie adaptations where he was also author, director and actor and once. There is also the very likely case where the resulting URI isn't as convenient. And that is where we use mapping.

### Standard Mapping

```json
{
    "field": "author_role",
    "mapping": {
        "aut": "https://id.loc.gov/vocabulary/relators/aut.html",
        "drt": "https://id.loc.gov/vocabulary/relators/drt.html",
    }
}
```

For our example the result would be quite simple:
	**RESULT:** `https://id.loc.gov/vocabulary/relators/aut.html`

This basically covers the entire function of mapping.  But what if no mapping can be matched, there might be different ways to write a key or upper and lower cases might be a concern? For that there is an additional field called `mapping_settings`. It can contain a selected number of keys and only those:

* `$default` - a value that is used if no match was found
* `$inherit` - a Boolean switch, if **TRUE** the actual field value will be written if no mapping can be achieved
* `$casesens` - another switch, if **FALSE** the mapping will be case-insensitive
* `$regex` - switch, if `TRUE` the mapping-keys will be assumed to be a **REGEX**. All mapping-keys have to be valid **REGEX**
* `$ref` - a string value, referencing an additional, local file

There are some caveats here:

* there will always be only one default value, if a list of values is getting mapped and one or more match, there will be those values but no default. Only if not one value matches, there will be a singular default mapping
* Mapping-Keys are per default case sensitive, if the switch is not set at all only exact string matches will register
* The **Regex** mapping needs more CPU cycles and will be slower. 
* If inheritance is set **TRUE** there will be a value for every element in a list of values, if its **FALSE** there might be an empty set if there is no default value

Lastly, the `$ref` is a local file, Spcht has no functionality to pull external files from a an ftp or web-server. The Path must be accessable and can be relative or absolute, for relative paths, the position of the Spcht Descriptor is always the root, not the folder of the executable. This switch is designed to keep the Main Descriptor more readable. There is a process to export a full Spcht Descriptor from a once loaded Spcht-Object where all referenced are already backed in. 

​	**Important**: if a mapping key exists in a referenced file AND in the main descriptor, the main descriptor takes priority

A full mapping example including a full (and illogical) mapping setting:

```json
{
    "field": "author_role",
    "mapping": {
        ".*(aut).*": "https://id.loc.gov/vocabulary/relators/aut.html",
        ".*(drt).*": "https://id.loc.gov/vocabulary/relators/drt.html",
    },
    "mapping_settings": {
        "$default": "https://id.loc.gov/vocabulary/relators/aut.html",
        "$inherit": false,
        "$casessens": false,
        "$regex": True,
        "$ref": "./mappings/roles.json"
    }
}
```

This does, as described above, match all input values with a described mapping-key by **Regex** and some unknown, additional keys, it will not respect case-sensitivity (which makes no sense cause we match via **Regex**), if nothing can be matched the final value will be `[..]aut.html`. If the input is a list of values and at least one is matched there will be as many values as matches.

​	**Attention**: The shown **Regex** is dangerous cause it uses multiple wild cards, a field value like `author_drt_adress` would match for both visible mapping-keys, the order of the keys should be as written but is not guaranteed in anyway, there is a possibility that  the end result here might be `[..]drt.html`

### Joined Map

Up till now we only ever manipulated the object part of any generated triple and defined the predicate as a constant value via `predicate`.  Different predicates are achieved via different nodes and we absolutely can leverage the *match* and *if*-functions to differentiate between different kind of values. For a set of edge cases Spcht provides some shortcuts to handle those situations easier. 

#### Edge Case 1: parallel filled fields

In at least one instance of the original task, raw data like this was present:

```json
{
    "author2": [
            "Wright, Joe",
            "Oldman, Gary",
            "Delbonnel, Bruno",
            "McCarten, Anthony"
        ],
    "author2_role": [
            "fmd",
            "act",
            "vdg",
            "aus"
        ],
}
```

The order of these entries is not random and is actually joined together. Therefore we can create some nifty triples that would not be possible in any other known Spcht way. As we know that those fields are joined together and the field `author_role2` describes the role of relators in a (*in this case*) movie. 

```json
{
    "field": "author2",
    "joined_field": "author2_role",
    "joined_map": {
        "act": "https://id.loc.gov/vocabulary/relators/aut.html"
    },
    "joined_map_ref": "./mappings/roles.json"
}
```

As visible it is also possible to use a referenced file here, the same rules as before apply, but `joined_map` does not support the other settings (as of now). For this to work the value of `field` and `joined_field` has to be the exact same length. They don't have to be an array/list, if both are singular values the procedure will work as well. (as a singular string is technically also a list of strings with the lengths of one). `joined_map` can be combined with almost any other `field` altering process, if a permissive operation filters out a given value there will be no *predicate*-*object* pair for that particular value, but the process continues, if `if_field` is leveraged and does return **FALSE** the node will be discarded as described above. It is even possible to combine `joined_map` and `mapping` as both part-processes are independent from each other. 

​	**Caveat**: it is not possible to use `insert_into` as this breaks the 1:1 relation of the data 

## Backup operations

### Alternatives

If the source data-set is the result of a longer standing operation there might be historic data that follows a slightly different schema than current versions. `alternatives` defines a set of alternative data-set keys that are to be taken in place of  the original `field`.

```json
{
    "field": "author",
    "alternatives": ["author_name", "aut_name", "writer_name"]
}
```

Any subsequent operations will take places as if the alternative data-set key was the original `field`

### Fallback

For more complex operations a `fallback` can be defined. It is an entire new node that can contain different operations all together, most common use case would be to use another source in the data-set, currently `marc`.

* A `fallback` can contain another `fallback` and so on
* A fallback does not need the `required` field, defining it wont change anything
* A fallback can contain a different `predicate` which will overwrite the one in the node before. If its not defined, the fallback-node will inherit the one of his parent.
* any transformative operation of one node will not take place in any subsequent fallbacks and most be defined anew if the effect is still desired

```json
{
    "source": "dict",
    "predicate": "https://random.graph/de",
    "required": "optional",
    "type": "literal",
    "field": "author_full_name",
    "fallback": {
        "source": "marc",
        "field": "100:0",
        "fallback": {
            "source": "marc",
            "field": "102:a"
        }
    }
}
```

## Source: marc21

The default state of input data for all Spcht operations is a dictionary (or ''*object*'' in JSON-speech), a data representation of an unique key linked to a set of data in an list. The first task that initiated the creation of Spcht handled data from an *Apache Solr* of the UBL that contained a field called `fullrecord`. This field contains the unmolested raw marc21-dataset that the other informations are derived from. As good data should not be wasted, Spcht includes utility to access such information. Unlike the clean dictionary structure marc is an old format that carries heavily upon its decades old burdens. The basic gist to access a marc21-field is to use identifiers like this:

​	`'field': '100:a'`

This should access Marc Field `100`, Subfield `A`, according to [this](https://www.loc.gov/marc/bibliographic/bd100.html) this should be the personal name of the main entry person. So far so good, unfortunatly there is more to it. The following isome reduced real world data to show different keys as it looks for the Spcht process:

```json
{
    "1": {
      "none": "0-1172721416"
   },
   "3": {
      "none": "DE-627"
   },
    "100": {
        "a": "Goethe, Johann Wolfgang von",
        "i1": "1",
        "d": "1749-1832",
        "0": [
            "(DE-588)118540238",
            "(DE-627)133416720",
            "(DE-576)161142842"
        ],
        "4": "aut"
    },
    "936": {
      "a": "LI 39320",
      "i1": "r",
      "i2": "v",
      "b": "Heisig, Bernhard",
      "k": [
         "Kunstgeschichte",
         "Künstler-Monografien",
         "Alphabetische Künstlerliste",
         "Künstler H",
         "Heisig, Bernhard"
      ],
      "0": [
         "(DE-627)1270642103",
         "(DE-625)rvk/96225:",
         "(DE-576)200642103"
      ]
   },
    "951": [
      {
         "a": "MV"
      },
      {
         "a": "XA-DE"
      },
      {
         "a": "XA-PL"
      },
      {
         "b": "XA-DE"
      }
   ],
}
```

We are seeing a lot of things that can be broken down to a few notable key items:

* Normal keys like `a` or `0`, those are the most simple thing
* Indicator Keys like `i1` and `i2`, those are not actually marc but are an internal representation for marc indicators
* `none` Keys, some fields do not have any sub-fields, the `none` key accesses those values that lay on the bare field without subfield designation.
* List of keyed sub-fields like the `951` on, if we access key `951:a` with Spcht, we will get 3 values that are processed: `"MV", "XA-DE", "XA-PL"`
* List of values under a key, this will yield exactly the same as before but is differently notated, field `936:0` will result in `"(DE-627)1270642103", "(DE-625)rvk/96225:", "(DE-576)200642103"`

For the most part one should not worry too much about how exactly Marc21 is handled internal, important is that a field:subfield combination will yield one or more values that is present on that field.

## Additional Spcht Fields

### type

In the second ever example in this document was shown how to create a triple that has an *URI* as object. This behaviour has to be manually set with the key `type`, it can only have two values: `uri` and `literal`. If `type` is not set a node will be assumed to end in a literal object. If set to `triple` the resulting object should be very surely be a valid *URI*, otherwise subsequent processes that transform the mapped data will fail.

### name

This is an entirely optional key that does nothing in the processing or for  the processing. It can be seen in log-files and the *SpchtCheckerGui* Program that analysis SpchtDescriptor Files. It is helpful to keep some order in an otherwise chaotic descriptor.

### comment*

The schema of the Spcht Descriptor Format does not allow any other keys as those described above, with one exception: *comments*. 

A user is not limited to just a field called `comment` as any one key that starts with `comment` is valid. This behaviour might come in handy when a given descriptor is edited by multiple people and the need for documentation of steps  or annotations arises.

*The absolute definitive definition of the Spcht Format can also be seen in the [JSONSchema](../SpchtSchema.json) File.*

