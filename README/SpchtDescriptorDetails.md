# Spcht Descriptor Format - in-depth explanation

# Introduction

The processing operation takes a set of data and creates *Linked Data* Triples of them. For that operation one has to understand the lowest unit in any triplestore looks:

`<subject> <predicate> "object"` or in more practical terms: 

`<https://data.finc.info/resources/0-1172721416> <http://purl.org/dc/terms/issued> "2002"`

The first part is the so called *subject*, the middle is the *predicate* and the last is the *object*, the first two have to be some kind of *UR**I*** (not to be confused with an *UR**L***) but the *object* can be a literal string or another *URI*, referencing another object. A *triplestore* usually contains a tree-like structure, known as graph. 

The input data for which the Spcht descriptor was originally written is inherently linear and not tree-like, there is a distinct 1-dimensional character of those data that makes the transformation from a classical database considerable easier.

The data, JSON-formatted, looks like this: 

![basic_data](./basic_data.png)

To generate a node from here we are taking one part, the *ID* as unique part for our subject, combined with a defined graph `https://example.info/data_` we get a full subject called `https://example.info/data_234232`, this forms the base root upon we can craft additional properties for this node.

We know the title and author of the book and which 'role' the author had in the creation of the book. A knowledgeable librarian chooses what properties match those data best and defines a *Spcht node* for each of those properties. 

In case of the title we take `http://purl.org/dc/terms/title` as agreed *predicate* for this kind of information, with this mapping defined we now have all three parts of our node defined. The end result would look like this:

`<https://example.info/data_234232> <http://purl.org/dc/terms/title> "Booktitle"`

While literal strings are easy to understand, they only possess a limited use for any further data operation. For this book we know also an author and what 'role' the author of this book had (they might have been a translator or publisher for instance). Other triplestores and databases have an extensive library of people that is fortunately linked by the key `author_gnd`, of the knowledge of the database our librarian can now write another node-description, stating that the field `author_gnd` contains an id that can be used to create an *URI* to further data. The result would look like this:

```
<https://example.info/data_234232> <http://purl.org/dc/terms/creator> 
	<http://d-nb.info/gnd/118514768>
```

Also of interest, we 'map' our author as 'creator' of this book instead of a generic 'contributor'. With this new data and many more similar nodes we can now use the data for linked data operations.

# Simplest structure

A Spcht descriptor file contains roughly two parts, the initial **Head** that describes the ID part of a triple and a list of **Nodes**. The Head itself is a node in itself and uses the same functions as any other node with the difference that the result must be a singular value.

![Basic Spcht Code](./basic_spcht.png)

This would do nothing, there might be a mapped *ID* per dataset, but as there is no actual data to create triples, nothing can be created. To achieve the two triples we discussed earlier `nodes` needs to contain actual content:

![basic_node](./basic_node.png)

There is already a new  field that wasn't discussed yet, `prepend`. Its one of the trans formative parameters that can be included into any node. It appends its text before the actual value provided by the data-field, in this case, the static part of a link. Used on the *jsoned* output from a database that contains those the three fields `id`, `title` and `author_gnd` we would get two triples as discussed in the introduction.