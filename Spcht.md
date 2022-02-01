 

# Spcht

This is a slightly specialised tool that extracts data from the Folio library services platform, transforms them and inserts them into an arbitrary triplestore. It uses the already established Spcht-infrastructures and methods but is unfortunately a lot more geared to a single purpose and harder to adapt / modify.

### First Run

The whole process from a blank slate triplestore in the first run would look like this:

1. retrieving all available data from folio via the OKAPI-Endpoints `/locations, /service-points` and `/location_units`
2. filtering the data for a specific location name, by default this is `entrance$` 
3. assembling those data to list of data entries, each representing one location
4. using three different Spcht descriptor files to assemble the actual triples, a set of delta subjects for later updates and another set of subjects, one for each opening hour, likewise for later updates.
5. generating a hash for each location and calendar opening hour definition
6. utilising the already established WorkOrder methods to insert the data, residing as a turtle file at this point, into the triplestore by either **sparql** oder, if its an OpenLink Virtuoso, possibly via **isql**

### Folio structure

The relevant part of the folio data lie in a small compartment that is the `location_units` module and additionally the `location` part of it. There is a distinction between *libraries*, *campus*es, *institutions* and *servicepoints* that matter.

* "institution" is the overall organisation, it can consist of many "libraries" and "campuses" scattered over the country or even the world
* "campus" is the local entity libraries are organised under, similar to university campuses, a *fenced* compound that defines an area, that fence can be everything from a real brick wall to an imaginary border that includes half of the city

* "library" is, roughly speaking, the building any given amount of shelves filled with books resides, it can contain multiple "locations"
* "location" stands for places within a "library", small ones might only have one, big ones might have multiple floors with more than five locations each, locations are the go to entry point for all data operations
* "servicepoints" are like a specialised type of location that can be interacted with. While locations might only define a place a servicepoint is a promise. A servicepoint has a time where someone or something is actively interacting with customers. Only service points can have opening hours.

If speaking about the pure technical organisation of the data it looks roughly like this:
```
LOCATION					SERVICEPOINT
├name						├id		
├🔗LIBRARY					├name
├🔗INSTITUTION				├code
├🔗CAMPUS					└staffSlips (doesnt matter here)
├🔗PRIMARYSERVICEPOINT
├[🔗SERVICEPOINTS]
└details {}
```

There is also some additional data describing normal database stuff like metadata, more ids and some functionality this tool doesn't care about. The most important part of a location among the links to all other things is the field `details`, it can contain arbitrary key-value pairs that can be entered by a user on the folio side. To utilise those data its important to have a proper schema and well communicated unified structure for data. All further operation assume that the data provided by `details` is uniform and each one key describes always the same thing.

It was stated that every servicepoint has opening hours linked to it, but as visible, there are no ids for opening hours inside a given servicepoint. For that kind of data the tool has to query the calendar interface `/calendar/periods/{UUID}/period` where "UUID" is the given id of any one servicepoint. *Folio* then returns a list of all available calendars with a timerange that describes **when** those calendars actually apply, therefore a third request is necessary to get the detailed list of open and closing times on a day-by-day basis.

Back to the locations, there are two links to servicepoints, there is for one a list of all servicepoints that reside at that location and there is also the primary location. This tool will always assume that the primary servicepoint holds the relevant opening hours for a location.

*All those endpoints are configurable in the config file if every anything changes here*

### The Working file

To save the current state of the updates and data a file based "database" is utilised. It might as well be a lean sqlite file but the necessary access seems to favor a simple and solid solution without the need to add overhead. By default the file is called `folio2triple.save.json` and is, as the name suggests, a json-file. Its overall structure looks like this:

```json
{
   "meta": { },
   "hashes": {
      "location": { },
      "opening": { }
   },
   "triples": {
      "location": { UUID: [], ... },
      "opening": { UUID: str, ...}
   }
}
```

The first key, 'meta' holds time based data on when the three processed where called last and some statistics. Hashes holds the hash of serialised information of locations and opening. Under the key 'triples' the so called "delta-subjects" are stored. These are used to surgical remove old and abandoned entries without deploying additional garbage collection tools.


### Update process

The aforementioned complexity comes from the need to keep a tightly synced link between data in folio and the triplestore. To keep data as up to date as possible there are three update intervals (that can be adjusted):

* Checking for changes in opening hours (*default: all 6 hours*)
* Checking for changed or deleted locations (*default: all 3 days*)
* Checking for new locations (*default: all 7 days*)

While opening hours might change quite often its highly unlikely that structural changes happen more often that once or twice a year, but when it happens those changes are supposed to be propagated in a timely manner

#### Opening hour changes

Opening hours in folio are designed as calendar entries, as it seems the original functionality is derived from a timetable as its possible to overlap opening hours in the editor (but not save). For every service point there is an assigned opening hour calendar that can be shared among multiple locations or rather service points (that are bound to service points anyway)

To keep the footprint of requests to the OKAPI interface low only that data is requested that is absolutely necessary. While creating the opening hours a hash over all hours and days was created that gets compared on checkup. For checkup only those opening hours that are known will be queried. 

When there is a change the aforementioned "delta subjects" will be utilised, these are part of the triple that define the opening hour triple for any one given location (organised in departments), the tool will then delete all links to specific opening hours and replace those with new entries (and might create specific opening&closing times that do yet not exist). Afterwards the hash list is updated and the tool goes back into hibernation till called the next time.

#### Location Changes

Similar to the opening changes there is a hash for a location, it does not include the opening hours but as part of the process those will be replaced as well, regardless of actual changes. When updating any given location the entire "department" inside the triplestore will be deleted, this included data that lies under another node like addresses or geographic positions. As the tool cannot know those and seperate them from data like the opening hours that might be used by more than one instance additional data was saved in the working file. If, for any reason, a location vanishes entirely the corresponding triple store entries will be deleted and not replaced as it would be for an update.

#### New Entry Check

By default, every 7 days all location data will be downloaded and its names searched for a specific, configured name to find new so called "entrances" that define the opening hours for any one given building. Different from the initial blank slate operation this will only fetch all locations but only those institutions, libraries and servicepoints that are actually necessary to create a new "department"

*Ironically, the example use case for this has always the same institution and campus for every single library so that the 'data hoarder' approach actually uses less data band with. Overall this shouldn't matter either way as it all is pure text data and no media like videos is part of it*

### The configuration file - folio2triplestore_config.py

This file contains all settings and file path to other files that are needed for the overall procedure. In a standard installation the file wont be present and instead a file called `folio2triplestore_config.example.py` can be found within the `./foliotools` folder.

## General design philosophy

Broadly speaking, there were two approaches to maintain synchronicity between the triplestore and the Folio that is the master of all data in this use case. Either way there needs to be some procedure that checks whether the data in the triplestore still reflect the content of the Folio. This tools does manage its update times itself, defined by three parameters in the configuration file, there would have been an alternative to make it a pure command line dependent application. In both cases the script has to be called by *cron* or some other kind of task scheduler. I believe to compress some complexity by managing the time frames for updates inside the same configuration file that holds other information concerning the process i choose the *better* way. Although there is room for discussion [^1]

[^1]: as always

