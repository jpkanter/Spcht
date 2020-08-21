# Fork for EFRE Linked Open Data ElasticSearch Toolchain

The [original](https://github.com/slub/efre-lod-elasticsearch-tools) toolchain of the **SLUB** was to complex for my needs, further i found its documentation
in the parts that interested me the most more than lacking. Especially the total absence of any 
comments had proven tiresome. This started out as a fork but transformed into its own project, there are no parts of the original code left but a lot of inspiration was drawn. Therefore there is still the original project around, just in spirit and terms of creativity.

## Content

## solr2virtuoso_bridge.py

The main part of the logic. It offers a handful of functions useable via a command line interface. Most settings that can be specified via a direct ressource can also referenced in a config json file with the key `para`.

### local_tools.py

To cleanup the main functions a bit some auxiliary functions where placed here to keep the code more readable.

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

