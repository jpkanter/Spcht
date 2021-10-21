#!/usr/bin/env python
# coding: utf-8

# Copyright 2021 by Leipzig University Library, http://ub.uni-leipzig.de
#                   JP Kanter, <kanter@ub.uni-leipzig.de>
#
# This file is part of the Solr2Triplestore Tool.
#
# This program is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Solr2Triplestore Tool.  If not, see <http://www.gnu.org/licenses/>.
#
# @license GPL-3.0-only <https://www.gnu.org/licenses/gpl-3.0.en.html>

SOURCES = ("dict", "marc", "tree")
SPCHT_BOOL_OPS = {"equal":"==", "eq":"==","greater":">","gr":">","lesser":"<","ls":"<",
                    "greater_equal":">=","gq":">=", "lesser_equal":"<=","lq":"<=",
                  "unequal":"!=","uq":"!=","=":"==","==":"==","<":"<",">":">","<=":"<=",">=":">=","!=":"!=","exi":"exi"}

WORK_ORDER_STATUS = ("Freshly created",  # * 0
                     "fetch started",  # *  1
                     "fetch completed",  # * 2
                     "processing started",  # *  3
                     "processing completed",  # *  4
                     "intermediate process started",  # * 5
                     "intermediate process finished",  # * 6
                     "inserting started",  # *  7
                     "insert completed/finished",  # * 8
                     "fullfilled")  # * 9

# this is basically the json Schema once more
BUILDER_KEYS = {
    "name": "str",
    "field": "str",
    "source": "str",
    "predicate": "str",
    "required": "boolean",
    "type": "boolean",
    "alternatives": "list",
    "mapping": "dict",
    "mapping_settings": "dict",
    "joined_map": "dict",
    "joined_field": "str",
    "joined_map_ref": "str",
    "match": "str",
    "append": "str",
    "prepend": "str",
    "cut": "str",
    "replace": "str",
    "insert_into": "str",
    "insert_add_field": "list",
    "if_field": "str",
    "if_value": "str",
    "if_condition": "str",
    "fallback": "str",
    "comment": "str",
    "sub_nodes": "str",
    "sub_data": "str",
    "tag": "str",
    "static_field": "str",
    "append_uuid_predicate_fields": "list",
    "append_uuid_object_fields": "list"
}
# all keys that reference another node
BUILDER_REFERENCING_KEYS = ["sub_nodes", "sub_data", "fallback"]
BUILDER_SINGLE_REFERENCE = ["fallback"]
BUILDER_LIST_REFERENCE = ["sub_nodes", "sub_data"]

RANDOM_NAMES = ['Trafalgar', 'Miranda', 'Kathmandu', 'Venerable', 'Crazy Horse', 'Peerless', 'Qiuxing', 'Swordfish', 'Berlin', 'Perseverance', 'Manila',
'Nishizawa', 'Courageous', 'Mongol', 'Dubai', 'Tiger Shark', 'Atlas', 'Melbourne', 'Buffalo', 'Baghdad', 'Jubilant',
'Galaxy', 'Cyclone', 'Vladivostok', 'Lima', 'Athens', 'Istanbul', 'Abhay', 'Mystic', 'Soobrazitelny', 'Karachi',
'Tehran', 'Shestakov', 'Brisbane', 'Yamamoto', 'Sultan', 'Alexander', 'Platypus', 'Minstrel', 'Delhi', 'Milan',
'Stingray', 'Gothenburg', 'Lightning', 'Surabaya', 'Winger', 'Gibraltar', 'Archer', 'Cheetah', 'Taciturn', 'Albatross',
'Minx', 'Excalibur', 'Tiger', 'Damascus', 'Chariot', 'Sao Paulo', 'Aardvark', 'Tsushima', 'Tornado', 'Vigilance',
'Kyoto', 'Lisbon', 'Hussar', 'Athena', 'Jiangkun', 'Greyhound', 'Ladybird', 'Valorous', 'Calgary', 'Kazakov',
'Johannesburg', 'Skylark', 'Florence', 'Rotterdam', 'Novgorod', 'Hong Kong', 'Cavalier', 'Venomous', 'Gallant', 'Javelin',
'Rickenbacker', 'Mumbai', 'Supreme', 'Sydney', 'Sardine', 'Wyvern', 'Verdun', 'Nelson', 'Bogota', 'Trojan',
'Hyderabad', 'Concord', 'Ark Royal', 'Camel', 'Saracen', 'Cantacuzino', 'Haifeng', 'Luxembourg', 'New York', 'Volgograd',
'Hood', 'Prague', 'Tunis', 'Zhengsheng', 'Penguin', 'Santiago', 'Grey Wolf', 'Falcon', 'Kaga', 'Formidable',
'Sarajevo', 'Walrus', 'Seoul', 'Scourge', 'Dolphin', 'Nova', 'Druid', 'Persistent', 'Riyadh', 'Abu Dhabi',
'Cherub', 'Wulong', 'Lexington', 'Vampire', 'Diadem', 'Cutlass', 'King Fish', 'Fortune', 'Geneva', 'Endurance',
'Panther', 'Nebula', 'Resolute', 'Taizhao', 'Mermaid', 'Brumowski', 'Kiev', 'Hailong', 'Zulu', 'Buzzard',
'Fonck', 'Datong', 'Protector', 'Vendetta', 'Belgrade', 'Juutilainen', 'Fox', 'Akagi', 'Deterrent', 'Monitor',
'Glasgow', 'Bulwark', 'Akshay', 'Aquila', 'Valiant', 'Hermes', 'Richthofen', 'Faithful', 'Constellation', 'Rapier',
'Undaunted', 'Midway', 'Bremen', 'Mogadishu', 'Chimera', 'Bismarck', 'Agile', 'Gauntlet', 'Indignant', 'Osaka',
'Shaoxing', 'Reliant', 'Hercules', 'Philadelphia', 'Steregushchiy', 'Crossbow', 'Hawk', 'Antelope', 'Ulysses', 'Belfast',
'Bellerophon', 'Jackal', 'Kestrel', 'Eagle', 'Coyote', 'Singapore', 'Spider', 'Vilnius', 'Beijing', 'Warsaw',
'Naiad', 'Spitfire', 'Onward', 'Pittsburgh', 'Phoenix', 'Horizon', 'Akula', 'Orca', 'Zürich', 'Battleaxe',
'Birmingham', 'Dauntless', 'Fearless', 'Hanoi', 'Andromeda', 'Yongcheng', 'Stockholm', 'Bloodhound', 'Hamburg', 'Accentor',
'Valley Forge', 'Vienna', 'Ankara', 'Orion', 'Chaoyang', 'Van Lierde', 'Bong', 'Wasp', 'Guardian', 'Polecat',
'Bulldog', 'Tapir', 'Enterprise', 'Doblestnyi', 'Highlander', 'St. Petersburg', 'Boyington', 'Bruiser', 'Kuala Lumpur', 'Sturgeon',
'Stratagem', 'Success', 'Venture', 'Starfish', 'Meteor', 'Crucible', 'Comet', 'Hurricane', 'Harrier', 'Cape Town',
'Yinghao', 'Agincourt', 'Raptor', 'Indefatigable', 'Detroit', 'Excelsior', 'Acorn', 'King Cobra', 'Velox', 'Marksman',
'Edinburgh', 'Courage', 'Leopard', 'Düsseldorf', 'Seraph', 'Venator', 'Chicago', 'Algiers', 'Brussels', 'Coral Sea',
'Cobra', 'Yamato', 'Houston', 'Tomoe Gozen', 'Valencia', 'Hammer', 'Tallinn', 'Dromedary', 'Chengdu', 'North Star',
'Nymph', 'Decisive', 'Utmost', 'Oracle', 'Salamander', 'Xenophon', 'Nighthawk', 'Typhoon', 'Usurper', 'Vulture',
'Myrmidon', 'Petrel', 'Sentinel', 'Kabul', 'Hornet', 'Dervish', 'Badger', 'Illustrious', 'Peacock', 'Devastator',
'Vigorous', 'Granicus', 'San Francisco', 'Prodigal', 'Scimitar', 'Shredder', 'Madrid', 'Black Prince', 'Pearl', 'Blazer',
'Viking', 'Whirlwind', 'Retribution', 'Quebec', 'Washington', 'Belisarius', 'Tel Aviv', 'Tapei', 'Broadsword', 'Miami',
'Guangzhou', 'Saratoga', 'Ocelot', 'Tripoli', 'Revenant', 'Osprey', 'Prudent', 'Knight', 'Austin', 'Venice',
'John Paul Jones', 'Firefly', 'Shark', 'Sphinx', 'Serpent', 'Brazzaville', 'Wolfhound', 'Pharsalus', 'Cairo', 'Jerusalem',
'Coppens', 'Forger', 'Brilliant', 'Ocean', 'Indomitable', 'Baracca', 'Copenhagen', 'Starwolf', 'Rodger Young', 'Montevideo',
'Alligator', 'Chivalrous', 'Helsinki', 'Eclipse', 'Stork', 'Apollo', 'Victorious', 'Anaconda', 'Sparrow', 'Jutland',
'Artemis', 'Lyon', 'Indianapolis', 'London', 'Viper', 'Denver', 'Victory', 'Sniper', 'Boston', 'Smolensk',
'Asp', 'Longbow', 'Audacity', 'Porcupine', 'Hannibal', 'Waterloo', 'Saladin', 'Cossack', 'Dublin', 'Papillon',
'Buenos Aires', 'Narwhal', 'Mustang', 'Bass', 'Shanghai', 'Patrician', 'Glowworm', 'Apache', 'Versatile', 'Agrippa',
'Islamabad', 'Fortitude', 'Montreal', 'Allegiance', 'Bangalore', 'Intrepid', 'Trident', 'Sharpshooter', 'Edmonton', 'Bratislava',
'Trondheim', 'Valorous', 'Paragon', 'Garuda', 'Ferret', 'Wolverine', 'Constitution', 'Hangzhou', 'Warhammer', 'Peregrine',
'Haddock', 'Mediator', 'Arrow', 'Moscow', 'Bombay', 'Century', 'Scythe', 'Raven', 'Scorcher', 'St. Louis',
'Elephant', 'Lancer', 'Grappler', 'Jaguar', 'Musashi', 'Vigilant', 'Yokohama', 'Stalker', 'Minsk', 'Pharaoh',
'Pegasus', 'Calcutta', 'Atlanta', 'Endeavor', 'Providence', 'Parthian', 'Aztec', 'Bangkok', 'Claymore', 'Los Angeles',
'Nautilus', 'Marseille', 'Ottawa', 'Lizard', 'Redoubtable', 'Gladius', 'Lion', 'Adventure', 'Vancouver', 'Minneapolis',
'Tomahawk', 'Dexterous', 'Musketeer', 'Gazelle', 'Buccaneer', 'Earnest', 'Rio de Janeiro', 'Nairobi', 'Tijuana', 'Sevastopol',
'Taiyang', 'Amsterdam', 'Seattle', 'Paradox', 'Budapest', 'Pelican', 'Meihong', 'Paris', 'Riga', 'Bonaventure',
'Magic', 'Jakarta', 'Nimble', 'Errant', 'Austerlitz', 'Havana', 'Yangwei', 'Defiant', 'Boxer', 'Rome',
'Dar es Salaam', 'Soyuz', 'Celestial', 'Mannock', 'Hotspur', 'Defender', 'Krakow', 'Defiance', 'Exeter', 'Reaver',
'Mosquito', 'Challenger', 'Casablanca', 'München', 'Fierce', 'Goliath', 'Charlemagne', 'Baltimore', 'Adder', 'Xerxes',
'Frankfurt', 'Vivacious', 'Matador', 'Tokyo', 'Ajax', 'Griffin', 'Bucharest', 'New Orleans', 'Kozhedub', 'Barcelona',
'Scorpion', 'Dingo', 'Invincible', 'Rifleman', 'Azrael', 'Hartmann', 'Obdurate', 'Dragonfly', 'Essex', 'Sakai',
'Mongoose', 'Lynx', 'Yorktown', 'Infinity', 'Trumpet', 'Oslo', 'Armadillo', 'Kangaroo', 'Janissary', 'Senator',
'Beagle', 'Toronto', 'Gettysburg', 'Shadow', 'Jackdaw', 'Dallas', 'Odyssey', 'Python', 'Warspite', 'Ranger',
'Actium', 'Icarus', 'Rattlesnake', 'Beirut', 'Shrike', 'Wizard', 'Mexico City', 'Liverpool', 'Akira', 'Puma',
'Lagos', 'Potemkin', 'Truncheon', 'Manchester', 'Guangxing', 'Bishop', 'Decimator']


if __name__ == "__main__":
    print("this file is not meant to be executed and only contains constant variables")
    exit(0)
