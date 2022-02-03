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

import json
import logging
import os
import re
import sys
import copy
import codecs
import time
from dateutil.relativedelta import relativedelta
from datetime import datetime
from pathlib import Path

import appdirs
from PySide2.QtGui import QStandardItemModel, QStandardItem, QIcon, QScreen
from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtCore

# own imports
import Core.SpchtErrors as SpchtErrors
import Utils.local_tools as local_tools
import Utils.SpchtConstants as SpchtConstants
from Gui.SpchtBuilder import SpchtBuilder, SimpleSpchtNode, RESERVED_NAMES
from Core.SpchtCore import Spcht

import Core.SpchtUtility as SpchtUtility
from Gui.SpchtCheckerGui_interface import SpchtMainWindow, ListDialogue, JsonDialogue, SelectionDialogue, QLogHandler, SolrDialogue, resource_path, i18n, __appauthor__, __appname__

__SOLR_MAX_START__ = 25000
__SOLR_MAX_ROWS__ = 500
__SOLR_DEFAULT_QUERY__ = "*.*"

__TITLE_VERSION__ = "131221.21:21"


logging.basicConfig(level=logging.DEBUG)

# Windows Stuff for Building under Windows
try:
    from PySide2.QtWinExtras import QtWin
    myappid = 'UBL.SPCHT.checkerGui.0.8'
    QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass


def delta_time_human(**kwargs):
    # https://stackoverflow.com/a/11157649
    attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds', 'microseconds']
    delta = relativedelta(**kwargs)
    human_string = ""
    for attr in attrs:
        if getattr(delta, attr):
            if human_string != "":
                human_string += ", "
            human_string += '%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1])
    return human_string


def disableEdits(*args1: QStandardItem):
    # why is this even necessary, why why why
    for each in args1:
        each.setEditable(False)


def time_log(line: str, time_string="%Y.%m.%d-%H:%M:%S", spacer="\n", end="\n"):
    return f"{datetime.now().strftime(time_string)}{spacer}{line}{end}"


def confirm_flatness(data: dict or list) -> bool:
    """
    Takes some data, presumed dictionary or list and checks if its all flat or nested
    :param dict or list data:
    :return: True or False if not so flat
    :rtype: bool
    """
    if isinstance(data, dict):
        for item in data.values():
            if isinstance(item, dict):
                return False
            if isinstance(item, list):
                for each in item:
                    if isinstance(each, (list, dict)):
                        return False
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, list):
                return False
            if isinstance(entry, dict):
                for item in entry.values():
                    if isinstance(item, dict):
                        return False
                    if isinstance(item, list):
                        for each in item:
                            if isinstance(each, (list, dict)):
                                return False
    return True


def data_object_keys(data):
    all_fields = set()
    if isinstance(data, dict):
        for field in recurse_dictionary(data):
            all_fields.add(field)
    if isinstance(data, list):
        variants = recurse_list(data)
        if variants:
            for each in variants:
                all_fields.add(f"[]>{each}")
        # no else, if there are only values of values the set is empty as their is nothing to talk to
    return all_fields


def recurse_dictionary(dictionary: dict):
    result_set = set()
    for key, element in dictionary.items():
        if isinstance(element, dict):
            for each in recurse_dictionary(dictionary[key]):
                result_set.add(f"{key}>{each}")
        elif isinstance(element, list):
            variants = recurse_list(dictionary[key])
            if variants:
                for each in variants:
                    result_set.add(f"{key}>{each}")
            else:
                result_set.add(key)
        else:
            result_set.add(key)
    return result_set


def recurse_list(multivalue: list):
    # returns an empty set if only actual values were found
    result_set = set()
    for element in multivalue:
        if isinstance(element, dict):
            for each in recurse_dictionary(element):
                result_set.add(f"[]>{each}")
        elif isinstance(element, list):
            variants = recurse_list(element)
            if variants:
                for each in variants:
                    result_set.add(f"[]>{each}")
            else:
                result_set.add(f"[]>[]")
    return result_set


def handle_variants(dictlist: dict or list) -> list:
    """
    When loading json test data there multiple formatstructures possible, for now its either direct export from solr
    or an already curated list, to make it easier here this function exists
    :param dictlist: the loaded json files content, most likely a list but could also be a dict
    :return: a list of dictionaries
    :rtype: list
    """
    # ? structure list of dictionary list > dict > key:value
    if isinstance(dictlist, list):
        for each in dictlist:
            if not isinstance(each, dict):
                raise SpchtErrors.ParsingError
        # ! condition for go_purple here
        return dictlist
    if isinstance(dictlist, dict):
        if 'response' in dictlist:
            if 'docs' in dictlist['response']:
                return handle_variants(dictlist['response']['docs'])
    return []
    # return dictlist  # this will most likely throw an exception, we kinda want that


class SpchtChecker(QMainWindow, SpchtMainWindow):
    """
    Gui for the Spcht Checker & Builder, as this is a rather big mess read further to get some thoughts behind the
    general layout:

    * Originally i thought in just using an external .ui file but the design fidility i get by using play code is a lot
      nicer for me, therefore i went that route. That idea birthed the SpchtCheckerGui_interface.py. This file actually
      contains more than just the interface but also Widgets and SubMenus as part of the file but not the class
    * Usually PEP8 recommends not to name functions in python with CamelCase and reserve that name scheme only for
      classes, this is quite often ignored. I decided to deviate from the standard a bit by using CamelCase for all
      class functions but use a underlaying logic to determine the different usages. All variables and objects like
      the interface elements are still using snake_case. Functions are differenciated by prefix:
       * actFunction is an 'action' therefore the direct result of a button beeing pressed or any other even
       * mthFunction are 'methods', functions that can be called by different parts of the code
       * utlFunction are utilities, functions serve an abstarct purpose, possibly reused at vastly different places
    * due timing some class-based variables have to be defined outside of the actual init, this is mostly all
      of the interface like self.console but also some of the 'savegame' variables, in detail those are:
       * self.tabview_menu - governs which columns of the SpchtExplorer widgets gets displayed
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # * condensly generates the names for SpchtView Headers
        self.node_headers = [{'key': x, 'header': i18n[f'col_{x}']} for x in SpchtBuilder.displaySpchtHeaders()]
        self.spcht_builder = None   # the builder upon all SpchtBuilder activity is based on
        self.active_spcht_node = None  # the current, in the node view openend SpchtNode
        self.active_data_tables = {}  # additional data that cannot be easily displayed in the view
        self.data_cache = None  # repository of data an example Spcht can work upon
        self.active_data = None   # the one entry that is currently active to work upon
        self.active_data_index = 0  # index in the datacache of the current data

        # governs Quality of Life Features:
        self.META_unsaved = False  # nodes were altered but not yet saved to a file
        self.META_changed = False  # the current node was altered and that change not saved to the SpchtBuilder
        self.META_adoption = False  # if the parent of a note changes
        self.ERROR_missing_nodes = []
        # ! this creates the entire ui, small line, big cause
        self.create_ui(self)
        self.taube = Spcht(schema_path=f"{os.getcwd()}/SpchtSchema.json")
        self.setWindowTitle(f"{i18n['window_title']} - {__TITLE_VERSION__}")

        # * Event Binds
        self.surpress_comboevent = False
        self.utlSetupEventBinds()
        self.utlSetupNodeTabConstants()

        # various
        self.console.insertPlainText(time_log(f"Init done, program started"))
        self.console.insertPlainText(f"Working Directory: {os.getcwd()}\n")
        # self.setupLogging()  # plan was to get logging into the console widget but i am too stupid

        self.mthLayoutCenter()

        # * Savegames
        self.lineeditstyle = self.exp_tab_node_field.styleSheet()  # this is probably a horrible idea
        self.console.insertPlainText(f"Time for init: {time.time()-self.time0:.2f}\n")

    def closeEvent(self, event):
        if self.META_unsaved:
            if not self.utlUnsavedPrompt(i18n['dialogue_unsaved_exit']):
                event.ignore()
                return
        self.utlSaveUserSettings()
        event.accept()
        # event.ignore()

    def utlSetupNodeTabConstants(self):
        self.LINE_EDITS = {"name": self.exp_tab_node_name,
                      "field": self.exp_tab_node_field,
                      "tag": self.exp_tab_node_tag,
                      "predicate": self.exp_tab_node_predicate,
                      "prepend": self.exp_tab_node_prepend,
                      "append": self.exp_tab_node_append,
                      "match": self.exp_tab_node_match,
                      "cut": self.exp_tab_node_cut,
                      "replace": self.exp_tab_node_replace,
                      "if_value": self.exp_tab_node_if_value,
                      "if_field": self.exp_tab_node_if_field,
                      "sub_data": self.exp_tab_node_subdata,
                      "sub_nodes": self.exp_tab_node_subnode}
        self.COMBOBOX = [{'key': "source", 'widget': self.exp_tab_node_source},
                         {'key': "if_condition", 'widget': self.exp_tab_node_if_condition},
                         {'key': "parent", 'widget': self.exp_tab_node_subdata_of},  # ? the problem here is that they
                         {'key': "parent", 'widget': self.exp_tab_node_subnode_of},  # ? are exclusive and overwrite each other
                         {'key': "fallback", 'widget': self.exp_tab_node_fallback}]
        self.CHECKBOX = {"required": {
                            "widget": self.exp_tab_node_mandatory,
                            "bool": {False: "optional", True: "mandatory"}
                        },
                        "type": {
                            "widget": self.exp_tab_node_uri,
                            "bool": {False: "literal", True: "uri"}
                        },
                        "predicate_inheritance": {
                            "widget": self.exp_tab_node_predicate_inheritance,
                            "bool": {False: False, True: True}
                        }
                        }
        self.CLEARONLY = [
            {'mth': "line", 'widget': self.exp_tab_node_mapping_preview},
            {'mth': "line", 'widget': self.exp_tab_node_mapping_ref_path},
            {'mth': "line", 'widget': self.exp_tab_node_if_many_values},
            {'mth': "text", 'widget': self.exp_tab_node_comment}
        ]
        self.COMPLEX = [
            {'type': "line", 'widget': self.exp_tab_node_mapping_ref_path, 'key': 'mapping_settings>$ref'},
            {'type': "line", 'widget': self.exp_tab_mapping_default, 'key': 'mapping_settings>$default'},
            {'type': "check", 'widget': self.exp_tab_mapping_inherit, 'key': 'mapping_settings>$inherit', 'bool': {True: True, False: False}},
            {'type': "check", 'widget': self.exp_tab_mapping_regex, 'key': 'mapping_settings>$regex', 'bool': {True: True, False: False}},
            {'type': "check", 'widget': self.exp_tab_mapping_casesens, 'key': 'mapping_settings>$casesens', 'bool': {True: True, False: False}},
        ]
        self.FILL = [
            {'type': "combo", 'widget': self.exp_tab_node_subdata_of, 'fct': "getSubdataParents", 'key': "sub_data"},
            {'type': "combo", 'widget': self.exp_tab_node_subnode_of, 'fct': "getSubnodeParents", 'key': "sub_nodes"},
            {'type': "combo", 'widget': self.exp_tab_node_fallback, 'fct': "getSolidParents", 'key': "fallback"},
        ]
        self.dialogue = [
            {'key': "if_value", 'data': "list", 'widget': self.exp_tab_node_if_many_values},
            {'key': "insert_add_fields", 'data': "listdict", 'widget': self.tab_node_insert_add_fields},
            {'key': "mapping", 'data': "dict", 'widget': self.exp_tab_node_mapping_preview}
        ]

    def utlSetupEventBinds(self):
        self.btn_load_spcht_file.clicked.connect(self.actLoadSpcht)
        self.btn_load_spcht_retry.clicked.connect(self.actSpchtLoadRetry)
        self.btn_tristate.clicked.connect(self.actToggleTriState)
        self.btn_load_testdata_file.clicked.connect(lambda: self.actLoadTestData(True))
        self.btn_load_testdata_retry.clicked.connect(self.actRetryTestdata)
        self.btn_tree_expand.clicked.connect(self.treeview_main_spcht_data.expandAll)
        self.btn_tree_collapse.clicked.connect(self.treeview_main_spcht_data.collapseAll)
        self.btn_change_main.clicked.connect(self.actChangeMainView)
        self.explorer_switch_checker.clicked.connect(self.actChangeMainView)
        self.actToggleTriState(0)
        # self.explorer_data_file_path.doubleClicked.connect(self.act_data_load_dialogue)  # line edit does not emit events :/
        self.explorer_data_load_button.clicked.connect(self.actLoadTestData)
        self.explorer_data_solr_button.clicked.connect(self.actSolrLoad)
        self.explorer_field_filter.textChanged[str].connect(self.actExecDelayedFieldChange)
        self.input_timer.timeout.connect(self.mthExecDelayedFieldChange)
        self.explorer_field_filter.returnPressed.connect(self.mthExecDelayedFieldChange)
        self.explorer_field_filter_helper.clicked.connect(self.actFieldFilterHelper)
        self.explorer_filter_behaviour.stateChanged.connect(self.mthExecDelayedFieldChange)

        #self.explorer_center_search_button.clicked.connect(self.test_button)
        self.explorer_node_create_btn.clicked.connect(self.actCreateSpchtBuilder)
        self.explorer_node_add_btn.clicked.connect(self.actCreateSpchtNode)
        self.explorer_node_duplicate_btn.clicked.connect(self.actDuplicateSpchtNode)
        self.explorer_node_clone_btn.clicked.connect(self.actCloneSpchtNode)
        self.explorer_node_import_btn.clicked.connect(self.actLoadSpcht)
        self.explorer_node_load_btn.clicked.connect(self.actOpenSpchtBuilder)
        self.explorer_node_export_btn.clicked.connect(self.actExportSpchtNode)
        self.explorer_node_save_btn.clicked.connect(self.actSaveSpchtBuilder)
        self.explorer_node_treeview.doubleClicked.connect(self.mthDisplayNodeDetails)

        self.explorer_center_search_button.clicked.connect(lambda: self.actFindDataCache(self.explorer_linetext_search.text()))
        self.explorer_linetext_search.returnPressed.connect(lambda: self.actFindDataCache(self.explorer_linetext_search.text()))
        self.explorer_left_button.clicked.connect(lambda: self.actFindDataCache("-1"))
        self.explorer_leftleft_button.clicked.connect(lambda: self.actFindDataCache("-10"))
        self.explorer_right_button.clicked.connect(lambda: self.actFindDataCache("+1"))
        self.explorer_rightright_button.clicked.connect(lambda: self.actFindDataCache("+10"))
        #self.explorer_tree_spcht_view.selectionModel().selectionChanged.connect(self.fct_explorer_spcht_change)
        #self.spcht_tree_model.itemChanged.connect(self.fct_explorer_spcht_change)

        # * Spcht Node Edit Tab
        self.spcht_timer.timeout.connect(self.actCreateTempAndCompute)
        self.exp_tab_node_name.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_field.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_source.currentIndexChanged.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_tag.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_predicate.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_append.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_prepend.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_match.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_cut.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_replace.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_uri.stateChanged.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_mandatory.stateChanged.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_mapping_btn.clicked.connect(self.actMappingInput)
        self.exp_tab_node_if_field.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_if_value.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_if_many_values.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_if_condition.currentIndexChanged.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_if_decider1.toggled.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_if_decider2.toggled.connect(self.actDelayedSpchtComputing)

        self.exp_tab_node_fallback.currentIndexChanged.connect(self.actFallbackWarning)
        self.exp_tab_node_subdata_of.currentIndexChanged.connect(lambda: self.actSetNodeParent(self.exp_tab_node_subdata_of))
        self.exp_tab_node_subnode_of.currentIndexChanged.connect(lambda: self.actSetNodeParent(self.exp_tab_node_subnode_of))

        self.exp_tab_node_if_decider1.toggled.connect(self.actChangeIfValue)
        self.exp_tab_node_if_enter_values.clicked.connect(self.actChooseIfValues)

        self.exp_tab_node_display_spcht.clicked.connect(lambda: self.actDisplayJson(1))
        self.exp_tab_node_display_computed.clicked.connect(lambda: self.actDisplayJson(0))
        self.exp_tab_node_save_node.clicked.connect(self.mthSaveBuilderNode)
        self.exp_tab_node_orphan_node.clicked.connect(self.orphanNode)
        self.exp_tab_node_delete_node.clicked.connect(self.deleteBuilderNode)
        self.exp_tab_node_builder.clicked.connect(self.actShowCompleteBuilder)

        temp_header = self.explorer_node_treeview.header()
        temp_header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        temp_header.customContextMenuRequested.connect(self.actSpchtTabviewColumnMenu)

    def utlSetupLogging(self):
        handler = QLogHandler(self)
        logging.getLogger(__name__).addHandler(handler)
        logging.getLogger(__name__).setLevel(logging.DEBUG)
        handler.new_record.connect(self.console.append)
        #logging.warning("i think this isnt working at all, sad times")

    def loadUserSettings(self):
        setting_folder = appdirs.user_config_dir(__appname__, __appauthor__, roaming=True)
        save_data = {}
        try:
            with open(os.path.join(setting_folder, "user_settings.json"), "r") as save:
                save_data = json.load(save)
        except FileNotFoundError:
            logging.warning("No 'savegame' file found, might be the first start, in this case this is normal")
        except json.decoder.JSONDecodeError as e:
            logging.warning(f"'savegame' file found but reading it failed: {e}")
        self.save_blacklist = save_data.get('blacklist', False)
        self.save_field_filter = save_data.get('field_filter', None)
        self.tabview_active_columns = save_data.get('active_columns', {})
        self.solr_defaults = save_data.get('solr_defaults', None)
        for element in self.node_headers:
            if element['key'] not in self.tabview_active_columns:
                self.tabview_active_columns[element['key']] = True
        self.console.insertPlainText(f"Loaded {len(save_data)} settings from {os.path.join(setting_folder,'user_settings.json')}\n")

    def utlSaveUserSettings(self):
        save_path = appdirs.user_config_dir(__appname__,__appauthor__, roaming=True)
        savegame = Path(save_path)
        savegame.mkdir(parents=True, exist_ok=True)
        savegame = savegame / "user_settings.json"  # i am actually amazed that path just uses the divide function for this
        # ! congregating data
        blacklist = self.explorer_filter_behaviour.isChecked()
        field_filter = self.explorer_field_filter.text()

        save_data = {
            "blacklist": blacklist,
            "field_filter": field_filter,
            "active_columns": self.tabview_active_columns,
            "solr_defaults": self.solr_defaults
        }

        with savegame.open("w", encoding="utf-8") as save:
            json.dump(save_data, save, indent=2)

    def mthLayoutCenter(self):
        center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())

    def actSpchtLoadRetry(self):
        self.mthLoadSpcht(self.linetext_spcht_filepath.displayText())

    def mthLoadSpcht(self, path_To_File):
        try:
            with open(path_To_File, "r") as file:
                spcht_data = json.load(file)
                status, output = SpchtUtility.schema_validation(spcht_data, schema=resource_path("./SpchtSchema.json"))
        except json.decoder.JSONDecodeError as e:
            self.console.insertPlainText(time_log(f"JSON Error: {str(e)}\n"))
            self.utlWriteStatus("Json error while loading Spcht")
            self.actToggleTriState(0)
            return None
        except FileNotFoundError as e:
            self.console.insertPlainText(time_log(f"File not Found: {str(e)}\n"))
            self.utlWriteStatus("Spcht file could not be found")
            self.actToggleTriState(0)
            return None

        if status:
            if not self.taube.load_descriptor_file(path_To_File):
                self.console.insertPlainText(time_log(
                    f"Unknown error while loading SPCHT, this is most likely something the checker engine doesnt account for, it might be 'new'\n"))
                self.utlWriteStatus("Unexpected kind of error while loading Spcht")
                return False
            self.actToggleTriState(1)
            self.btn_load_testdata_file.setDisabled(False)
            self.mthPopulateTreeviewWithSpcht()
            self.mthPopulateTextViews()
            self.utlWriteStatus("Loaded spcht discriptor file")
            self.mthSpchtBuilderBtnStatus(1)
            self.explorer_toolbox.setItemText(1, f"{i18n['builder_toolbox_node_overview']} - {path_To_File}")
            self.spcht_builder = SpchtBuilder(spcht_data, spcht_base_path=str(Path(path_To_File).parent))
            self.mthFillNodeView(self.spcht_builder.displaySpcht())
            self.explorer_toolbox.setCurrentIndex(1)
        else:
            self.console.insertPlainText(time_log(f"SPCHT Schema Error: {output}\n"))
            self.utlWriteStatus("Loading of spcht failed")
            self.actToggleTriState(0)
            return None

    def mthPopulateTreeviewWithSpcht(self):
        i = 0
        # populate views
        if self.spchttree_view_model.hasChildren():
            self.spchttree_view_model.removeRows(0, self.spchttree_view_model.rowCount())
        for each in self.taube:
            i += 1
            tree_row = QStandardItem(each.get('name', f"Element #{i}"))
            SpchtChecker.mthPopulateTreeviewRecursion(tree_row, each)
            tree_row.setEditable(False)
            self.spchttree_view_model.appendRow(tree_row)
            self.treeview_main_spcht_data.setFirstColumnSpanned(i - 1, self.treeview_main_spcht_data.rootIndex(), True)

    @staticmethod
    def mthPopulateTreeviewRecursion(parent, node):
        info = ""
        if node.get('type') == "mandatory":
            col0 = QStandardItem("!!!")
            col0.setToolTip("This field is mandatory")
        else:
            col0 = QStandardItem("")
        col1 = QStandardItem(node.get('predicate', ""))
        col1.setToolTip(node.get('predicate', ""))
        col2 = QStandardItem(node.get('source'))
        fields = node.get('field', "") + " |"
        if 'alternatives' in node:
            fields += " Alts: "
            for each in node['alternatives']:
                fields += f"{each}, "
        col3 = QStandardItem(fields[:-2])
        col3.setToolTip(fields[:-2])
        # other fields
        additionals = ["append", "prepend", "cut", "replace", "match", "joined_field"]
        for each in additionals:
            if each in node:
                info += f"{node[each]}; "
        col5 = QStandardItem(info[:-2])
        col5.setToolTip(info[:2])
        # comments
        commentlist = []
        for each in node.keys():
            finding = re.match(r"(?i)^(comment).*$", each)
            if finding is not None:
                commentlist.append(finding.string)
        commentText = ""
        commentBubble = ""
        for each in commentlist:
            commentText += node[each] + ", "
            commentBubble += node[each] + "\n"
        col6 = QStandardItem(commentText[:-2])
        col6.setToolTip(commentBubble[:-1])
        disableEdits(col0, col1, col2, col3, col5, col6)
        parent.appendRow([col0, col1, col2, col3, col5, col6])
        if 'fallback' in node:
            SpchtChecker.mthPopulateTreeviewRecursion(parent, node['fallback'])

    def mthPopulateTextViews(self):
        # retrieve used fields & graphs
        fields = self.taube.get_node_fields()
        predicates = self.taube.get_node_predicates()
        self.lst_fields_model.clear()
        self.lst_graphs_model.clear()
        for each in fields:
            tempItem = QStandardItem(each)
            tempItem.setEditable(False)
            self.lst_fields_model.appendRow(tempItem)
        for each in predicates:
            tempItem = QStandardItem(each)
            tempItem.setEditable(False)
            self.lst_graphs_model.appendRow(tempItem)

    def actToggleTriState(self, status=0):
        toggleTexts = ["[1/3] Console", "[2/3] View", "[3/3]Tests", "Explorer"]
        if isinstance(status, bool):  # connect calls as false
            if self.tristate == 2:
                self.tristate = 0
            else:
                self.tristate += 1
            self.MainPageLayout.setCurrentIndex(self.tristate)
        else:
            self.MainPageLayout.setCurrentIndex(status)
            self.tristate = self.MainPageLayout.currentIndex()
        self.btn_tristate.setText(toggleTexts[self.tristate])

    def actChangeMainView(self):
        if self.central_widget.currentIndex() == 0:
            self.central_widget.setCurrentIndex(1)
        else:
            self.central_widget.setCurrentIndex(0)

    def actLoadSpcht(self):
        if self.META_unsaved:
            if not self.utlUnsavedPrompt(i18n['dialogue_unsaved_load']):
                return
        path_To_File, file_type = QtWidgets.QFileDialog.getOpenFileName(self, "Open spcht descriptor file", "../", "Spcht Json File (*.spcht.json);;Json File (*.json);;Every file (*.*)")

        if not path_To_File:
            return None

        self.btn_load_spcht_retry.setDisabled(False)
        self.linetext_spcht_filepath.setText(path_To_File)
        self.mthLoadSpcht(path_To_File)

    def mthGatherAvailableFields(self, data=None, marc21=False, deepdive=False):
        if not data:
            data = self.data_cache
        if not data:
            return []
        all_fields = set()
        for _, block in enumerate(data):
            if not deepdive:
                for key in block.keys():
                    all_fields.add(key)
            else:  # methods for arbitrary data
                for each in data_object_keys(block):
                    all_fields.add(each)
            if 'fullrecord' in block and marc21:
                temp_marc = SpchtUtility.marc2list(block['fullrecord'])
                for main_key, top_value in temp_marc.items():
                    if isinstance(top_value, list):
                        for param_list in top_value:
                            for sub_key in param_list:
                                all_fields.add("{main_key}:{sub_key}")
                                all_fields.add(f"{main_key:03d}:{sub_key}")
                    elif isinstance(top_value, dict):
                        for sub_key in top_value:
                            all_fields.add(f"{main_key}:{sub_key}")
                            all_fields.add(f"{main_key:03d}:{sub_key}")  # i think this is faster than if-ing my way through
            if _ > 100:
                # ? having halt conditions like this always seems arbitrary but i really struggle to imagine how much more
                # ? unique keys one hopes to get after 100 entries. On my fairly beefy machine the processing for 500
                # ? entries was 3,01 seconds, for 10K it was around 46 seconds. The 600ms for 100 seem acceptable
                break
        return list(all_fields)

    def actLoadTestData(self, graph_prompt=False):
        path_to_file, type = QtWidgets.QFileDialog.getOpenFileName(self, "Open explorable data", "../", "Json File (*.json);;Every file (*.*)")

        if path_to_file == "":
            return None

        try:
            with open(path_to_file, "r") as file:
                test_data = json.load(file)
        except FileNotFoundError:
            self.utlWriteStatus("Loading of example Data file failed.")
            return False
        except json.JSONDecodeError as e:
            self.utlWriteStatus(f"Example data contains json errors: {e}")
            self.console.insertPlainText(time_log(f"JSON Error in Example File: {str(e)}\n"))
            return False
        if test_data:
            self.data_cache = handle_variants(test_data)
            if len(self.data_cache) and confirm_flatness(self.data_cache):
                self.utlWriteStatus("Testdata loaded, normal solr format")
                self.mthSetTestData(path_to_file, self.data_cache)
            elif len(test_data):
                self.mthSetWorkableTestData(path_to_file, test_data)
                self.utlWriteStatus("Test loaded, unusal format, data for LiveSpcht useable bot not exploreable")
            else:
                self.console.insertPlainText(f"Loading of file {path_to_file} failed, most likely an unsupported format\n")

        if graph_prompt:
            graphtext = self.linetext_subject_prefix.displayText()
            graph, status = QtWidgets.QInputDialog.getText(self, "Insert Subject name",
                                                        "Insert non-identifier part of the subject that is supposed to be mapped onto",
                                                        text=graphtext)
            if status is False or graph.strip() == "":
                return None
            if self.actProcessTestdata(path_to_file, graph):
                self.btn_load_testdata_retry.setDisabled(False)
                self.linetext_subject_prefix.setText(graph)

    def mthSetTestData(self, source: str, data: list):
        self.str_testdata_filepath.setText(source)
        # * explorer stuff
        self.explorer_data_file_path.setText(source)
        self.active_data = data[0]
        self.active_data_index = 0
        self.explorer_linetext_search.setPlaceholderText(f"{1} / {len(data)}")
        self.mthFillExplorer(data)
        temp_model = QStandardItemModel()
        [temp_model.appendRow(QStandardItem(x)) for x in self.mthGatherAvailableFields(marc21=True)]
        self.field_completer.setModel(temp_model)
        self.explorer_field_filter.setDisabled(False)
        self.explorer_field_filter_helper.setDisabled(False)
        self.explorer_filter_behaviour.setDisabled(False)
        self.explorer_dictionary_treeview.setHidden(False)
        self.explorer_arbitrary_data.setHidden(True)
        if self.active_spcht_node:
            temp = self.mthCreateTempSpcht()
            self.mthComputeSpcht(temp)

    def mthSetWorkableTestData(self, source: str, data):
        """
        Some data might be not exactly within specs but still readable with sub_nodes, sub_data and source:tree
        :param str source: path to file
        :param data:
        :return: nothing
        :rtype: None
        """
        self.explorer_data_file_path.setText(source)

        self.explorer_field_filter.setDisabled(True)
        self.explorer_field_filter_helper.setDisabled(True)
        self.explorer_filter_behaviour.setDisabled(True)
        self.explorer_dictionary_treeview.setHidden(True)
        self.explorer_arbitrary_data.setHidden(False)

        if isinstance(data, dict):
            data = list(data)
        self.data_cache = data
        self.active_data = data[0]
        self.active_data_index = 0
        self.explorer_linetext_search.setPlaceholderText(f"{1} / {len(data)}")
        temp_model = QStandardItemModel()
        [temp_model.appendRow(QStandardItem(x)) for x in self.mthGatherAvailableFields(data, marc21=True, deepdive=True)]
        self.field_completer.setModel(temp_model)
        self.explorer_arbitrary_data.setText(json.dumps(data, indent=3))

        if self.active_spcht_node:
            temp = self.mthCreateTempSpcht()
            self.mthComputeSpcht(temp)

    def actRetryTestdata(self):
        if self.data_cache:
            self.mthLoadSpcht(self.linetext_spcht_filepath.displayText())
            self.actProcessTestdata(self.str_testdata_filepath.displayText(), self.linetext_subject_prefix.displayText())
        # its probably bad style to directly use interface element text

    def actProcessTestdata(self, filename, subject):
        debug_dict = {}  # TODO: loading of definitions
        basePath = Path(filename)
        descriPath = os.path.join(f"{basePath.parent}", f"{basePath.stem}.descri{basePath.suffix}")
        print("Additional description path:",descriPath)
        # the ministry for bad python hacks presents you this path thingy, pathlib has probably something better i didnt find in 10 seconds of googling
        try:
            with open(descriPath) as file:  # complex file operation here
                temp_dict = json.load(file)
                if isinstance(temp_dict, dict):
                    code_green = 1
                    for key, value in temp_dict.items():
                        if not isinstance(key, str) or not isinstance(value, str):
                            self.utlWriteStatus("Auxilliary data isnt in expected format")
                            code_green = 0
                            break
                    if code_green == 1:
                        debug_dict = temp_dict
        except FileNotFoundError:
            self.utlWriteStatus("No auxilliary data has been found")
            pass  # nothing happens
        except json.JSONDecodeError:
            self.utlWriteStatus("Loading of auxilliary testdata failed due a json error")
            pass  # also okay
        # loading debug data from debug dict if possible
        time_process_start = datetime.now()

        tbl_list = []
        text_list = []
        thetestset = handle_variants(self.data_cache)
        self.mthProgressMode(True)
        self.processBar.setMaximum(len(thetestset))
        i = 0
        for entry in thetestset:
            i += 1
            self.processBar.setValue(i)
            try:
                temp = self.taube.process_data(entry, subject)
            except Exception as e:  # probably an AttributeError but i actually cant know, so we cast the WIDE net
                self.mthProgressMode(False)
                self.utlWriteStatus(f"SPCHT interpreting encountered an exception {e}")
                return False
            if isinstance(temp, list):
                text_list.append(
                "\n=== {} - {} ===\n".format(entry.get('id', "Unknown ID"), debug_dict.get(entry.get('id'), "Ohne Name")))
                for each in temp:
                    tbl_list.append(each)
                    tmp_sparql = SpchtUtility.quickSparqlEntry(each)
                    text_list.append(tmp_sparql)
        # txt view
        self.txt_tabview.clear()
        for each in text_list:
            self.txt_tabview.insertPlainText(each)
        # table view
        if self.mdl_tbl_sparql.hasChildren():
            self.mdl_tbl_sparql.removeRows(0, self.mdl_tbl_sparql.rowCount())
        for each in tbl_list:
            col0 = QStandardItem(str(each.subject))
            col1 = QStandardItem(str(each.predicate))
            col2 = QStandardItem(str(each.sobject))
            disableEdits(col0, col1, col2)
            self.mdl_tbl_sparql.appendRow([col0, col1, col2])
        self.actToggleTriState(2)
        time3 = datetime.now()-time_process_start
        self.utlWriteStatus(f"Testdata processing finished, took {delta_time_human(microseconds=time3.microseconds)}")
        self.mthProgressMode(False)
        return True

    def utlWriteStatus(self, text):  # criminally underutilized
        self.notifybar.showMessage(time_log(text, time_string="%H:%M:%S", spacer=" ", end=""))

    def mthProgressMode(self, mode):
        # ! might go hay wire if used elsewhere cause it resets the buttons in a sense, unproblematic when
        # ! only used in processData cause all buttons are active there
        if mode:
            self.btn_load_testdata_retry.setDisabled(True)
            self.btn_load_testdata_file.setDisabled(True)
            self.btn_load_spcht_retry.setDisabled(True)
            self.btn_load_spcht_file.setDisabled(True)
            self.bottomStack.setCurrentIndex(1)
        else:
            self.btn_load_testdata_retry.setDisabled(False)
            self.btn_load_testdata_file.setDisabled(False)
            self.btn_load_spcht_retry.setDisabled(False)
            self.btn_load_spcht_file.setDisabled(False)
            self.bottomStack.setCurrentIndex(0)

    def actExplorerSpchtChange(self):
        index = self.spcht_tree_model.index(0, 0)
        element = self.spcht_tree_model.itemFromIndex(index)
        logging.debug(str(self.spcht_tree_model.data(index)))
        spcht = {}
        for row in range(element.rowCount()):
            if element.child(row, 1).text().strip():
                spcht[element.child(row, 0).text()] = element.child(row, 1).text().strip()
        self.explorer_spcht_result.insertPlainText(json.dumps(spcht, indent=2) )
        self.explorer_spcht_result.setFont(self.FIXEDFONT)
        if self.data_cache:
            vogl = Spcht()
            vogl._raw_dict = self.data_cache[0]
            try:
                self.explorer_spcht_result.clear()
                result = vogl._recursion_node(spcht)
                if result:
                    logging.debug(result)
                    for each in result:
                        self.explorer_spcht_result.insertPlainText(str(each))
            except Exception as e:
                error = e.__class__.__name__
                error += f"\n{e}"
                self.explorer_spcht_result.insertPlainText(error)

    def actExecDelayedFieldChange(self):
        if self.data_cache:
            self.input_timer.start(2000)

    def mthExecDelayedFieldChange(self):
        if self.data_cache:
            self.mthFillExplorer(self.data_cache)

    def actCreateTempAndCompute(self):
        temp = self.mthCreateTempSpcht()
        if temp:
            if temp['name'] != self.active_spcht_node['name']:
                self.explorer_toolbox.setItemText(2, f"{i18n['builder_toolbox_main_builder']} - {self.active_spcht_node['name']} -> {temp['name']}")
            else:
                self.explorer_toolbox.setItemText(2, f"{i18n['builder_toolbox_main_builder']} - {self.active_spcht_node['name']}")
            self.mthComputeSpcht(temp)

    def actSolrLoad(self, message=None):
        if self.solr_defaults == None:
            self.solr_defaults = {"q": "*:*"}
        dlg = SolrDialogue(i18n['solr_load_title'], message=message, defaults=self.solr_defaults, parent=self)
        if dlg.exec_():
            self.solr_defaults = dlg.getData()
            # ? some sanity
            if 'start' in self.solr_defaults:
                if SpchtUtility.is_int(self.solr_defaults['start']):
                    self.solr_defaults['start'] = int(self.solr_defaults['start'])
                    if self.solr_defaults['start'] > __SOLR_MAX_START__:
                        self.solr_defaults['start'] = __SOLR_MAX_START__
                else:
                    self.solr_defaults['start'] = 0
            if 'rows' in self.solr_defaults:
                if SpchtUtility.is_int(self.solr_defaults['rows']):
                    self.solr_defaults['rows'] = int(self.solr_defaults['rows'])
                    if self.solr_defaults['rows'] > __SOLR_MAX_ROWS__:
                        self.solr_defaults['rows'] = __SOLR_MAX_ROWS__
                else:
                    self.solr_defaults['rows'] = 0
            try:
                result = self.mthLoadFromSolr(self.solr_defaults)
            except SpchtErrors.ParsingError as e:
                self.actSolrLoad(e)
            if result and len(result) > 0:  # shouldnt that be implied by "is result"?
                self.data_cache = result
                self.mthSetTestData(self.solr_defaults['url'], self.data_cache)
                # do the insert data boogaloo
            else:
                self.actSolrLoad(i18n['solr_load_failed'])

    def mthLoadFromSolr(self, parameters):
        para = copy.copy(parameters)
        url = para.pop('url', None)
        if not url:
            return None
        para['wt'] = "json"
        para['rows'] = para.get('rows', 10)
        para['start'] = para.get('start', 0)
        str_response = local_tools.load_remote_content(url, para)
        dict_response = local_tools.test_json(str_response)
        if not dict_response:
            return None
        return local_tools.solr_handle_return(dict_response)

    def actFieldFilterHelper(self):
        all_fields = set()
        if self.data_cache:
            for line in self.data_cache:
                for key in line:
                    if key != "fullrecord":  # ! TODO: do not make fullrecord static text
                        all_fields.add(key)
        filtering = self.explorer_field_filter.text()
        if not filtering:
            field_filter = []
        else:
            field_filter = [x.strip() for x in filtering.split(",")]
        dlg = SelectionDialogue(i18n['dialogue_filter_helper'], field_filter, list(all_fields), self)
        if dlg.exec_():
            self.explorer_field_filter.setText(", ".join(dlg.getListA()))

    def mthFillExplorer(self, data):
        # * Check if filter is elegible

        all_keys = set()
        for line in data:
            for key in line:
                if key != "fullrecord":  # ! TODO: do not make fullrecord static text
                    all_keys.add(key)
        filtering = self.explorer_field_filter.text()
        if filtering:
            fields = [x.strip() for x in filtering.split(",")]
            if self.explorer_filter_behaviour.isChecked():
                all_keys = [y for y in all_keys if y not in fields]
            else:
                all_keys = [y for y in fields if y in all_keys]
        fixed_keys = dict.fromkeys(sorted(all_keys, key=lambda x: x.lower()), None)
        logging.debug(f"_fill_explorer: fixed_keys: {fixed_keys}")

        data_model = QStandardItemModel()
        data_model.setHorizontalHeaderLabels([x for x in fixed_keys.keys()])

        for vertical, line in enumerate(data):
            data_model.setVerticalHeaderItem(vertical, QStandardItem(str(vertical)))
            for horizontal, a_key in enumerate(fixed_keys.keys()):
                text = ""
                if a_key in line:
                    if isinstance(line[a_key], list):
                        schreib = ""
                        text = QStandardItem(f"[]{line[a_key][0]}")
                        for each in line[a_key]:
                            schreib += f"{each}\n"
                            text.appendRow(QStandardItem(each))
                        text = schreib
                    else:
                        text = str(line[a_key])
                data_model.setItem(vertical, horizontal, QStandardItem(text))
                data_model.setData(data_model.index(vertical, horizontal), QtCore.Qt.AlignTop, QtCore.Qt.TextAlignmentRole)
        self.explorer_dictionary_treeview.setModel(data_model)

    def test_button(self):
        dlg = ListDialogue("Testtitle", "Do Stuff", headers=["key", "mapping"], init_data={"exe": "excecutor", "rtf": "rich text"}, parent=self)
        if dlg.exec_():
            print(dlg.getData())

    def actFindDataCache(self, find_string):
        if not self.data_cache:
            self.explorer_linetext_search.setPlaceholderText("No data loaded yet")
        if find_string == "+1" or find_string == "+10":
            find_string = str(self.active_data_index + 1 + int(find_string[1:]))  # this is so dirty
        elif find_string == "-10" or find_string == "-1":
            find_string = str(self.active_data_index + 1 - int(find_string[1:]))  # this is so dirty
        if re.search(r"^\w*:\w+$", find_string):  # search string
            key, value = find_string.split(":")
            key = key.strip()
            value = value.strip()
            if key.strip() != "":  # key: value search
                for _, repo in enumerate(self.data_cache):
                    if key in repo:
                        if repo[key] == value:
                            self.active_data = self.data_cache[_]
                            self.active_data_index = _
                            self.explorer_linetext_search.setPlaceholderText(f"{_ + 1} / {len(self.data_cache)}")
                            self.explorer_linetext_search.setText("")
                            break
            else:  # value only search
                pass
        elif SpchtUtility.is_int(find_string):
            number = int(find_string) - 1
            temp_len = len(self.data_cache)
            if number <= 0:
                number = 0 # first index
                self.active_data = self.data_cache[number]
            elif number >= temp_len:
                number = temp_len-1 # last index
            self.active_data = self.data_cache[number]
            self.active_data_index = number
            self.explorer_linetext_search.setPlaceholderText(f"{number+1} / {len(self.data_cache)}")
            self.explorer_linetext_search.setText("")
        temp = self.mthCreateTempSpcht()
        if temp:
            self.mthComputeSpcht(temp)

    def mthFillNodeView(self, builder_display_data):
        floating_model = QStandardItemModel()
        floating_model.setHorizontalHeaderLabels([x['header'] for x in self.node_headers])
        for _, header in enumerate(self.node_headers):
            if _ == 0:
                continue
            floating_model.horizontalHeaderItem(_).setDragEnabled(True)
        skip = 0
        special_nodes = RESERVED_NAMES  # reserved names from spcht builder, eg :ROOT:, :MAIN: and :UNUSED:
        for prio in special_nodes:
            if prio in builder_display_data:
                floating_model.setItem(skip, 0, self.utlTreeviewLine(prio, builder_display_data[prio]))
                builder_display_data.pop(prio)
                skip += 1
        for big_i, (parent, group) in enumerate(builder_display_data.items()):
            floating_model.setItem(big_i + skip, 0, self.utlTreeviewLine(parent, group))
        self.explorer_node_treeview.setModel(floating_model)
        self.explorer_node_treeview.expandAll()
        self.mthHideTabviewColumns()

    def utlTreeviewLine(self, parent, props) -> QStandardItem:
        top_node = QStandardItem(parent)
        for i, each in enumerate(props):
            for index, key in enumerate(self.node_headers):
                element = QStandardItem(each.get(key['key'], ""))
                element.setEditable(False)
                top_node.setChild(i, index, element)
        top_node.setEditable(False)
        return top_node

    def mthSetSpchtTabView(self, SpchtNode=None):  # aka NodeToForms
        if not SpchtNode:
            SpchtNode = {}  # PEP no likey when setting to immutable as default
        self.surpress_comboevent = True

        # ? just clears all the fields that do not get assigned a value by default
        for details in self.CLEARONLY:
            if details['mth'] == "line":
                details['widget'].setText("")
            if details['mth'] == "text":
                details['widget'].setText("")
            self.exp_tab_node_if_decider1.setChecked(True)

        # ? fills widgets with dynamic data
        for fill in self.FILL:
            if fill['type'] == "combo":
                gaseous = QStandardItemModel()
                gaseous.appendRow(QStandardItem(""))
                data = getattr(self.spcht_builder, fill['fct'])()
                for each in data:
                    gaseous.appendRow(QStandardItem(each))
                fill['widget'].setModel(gaseous)
                # ? index will be set by self.COMBOBOX
        # ? simple data that is just an arbitrary string
        for key, widget in self.LINE_EDITS.items():
            value = SpchtNode.get(key, "")
            if isinstance(value, (int, float, str, bool)):
                widget.setText(str(value))
        for y in self.COMBOBOX:
            index = y['widget'].findText(SpchtNode.get(y['key'], ""), QtCore.Qt.MatchFixedString)
            if index > 0:
                y['widget'].setCurrentIndex(index)
            else:
                y['widget'].setCurrentIndex(0)
        # ? some checkbox items that are filled with either true/false by logic outlined in data
        for key, details in self.CHECKBOX.items():
            if key not in SpchtNode:
                details['widget'].setChecked(0)
            else:
                reverse_bool = {value: key for key, value in details['bool'].items()}
                details['widget'].setChecked(reverse_bool[SpchtNode[key]])
        for cplx in self.COMPLEX:
            keys = cplx['key'].split(">")
            if keys:
                value = SpchtNode
                for key in keys:
                    key = key.strip()
                    if key in value:
                        value = value[key]
                    else:
                        value = None
                        break
                if value:
                    if cplx['type'] == "line":
                        cplx['widget'].setText(value)
                    elif cplx['type'] == "check":
                        cplx['widget'].setChecked(cplx['bool'][value])
                else:
                    if cplx['type'] == "line":
                        cplx['widget'].setText("")
                    elif cplx['type'] == "check":
                        cplx['widget'].setChecked(False)
        # ? manual configured things
        if 'if_value' in SpchtNode and isinstance(SpchtNode['if_value'], list):
            self.active_data_tables['if_value'] = SpchtNode['if_value']
            self.exp_tab_node_if_many_values.setText(str(self.active_data_tables['if_value']))
            self.exp_tab_node_if_decider2.setChecked(True)
        else:
            self.exp_tab_node_if_decider1.setChecked(True)
            self.exp_tab_node_if_many_values.setText("")
        # * parent
        if 'name' in SpchtNode:  # for cleanup step an empty spcht will be given
            self.exp_tab_node_parent.setText(self.spcht_builder[SpchtNode['name']]['parent'])
        else:  # available
            self.exp_tab_node_parent.setText("")
        if 'parent' in SpchtNode:
            self.exp_tab_node_orphan_node.setDisabled(False)
            if SpchtNode['parent'] == ":MAIN:":
                self.exp_tab_node_orphan_node.setText(i18n['explorer_orphan_node'])
            elif SpchtNode['parent'] == ":UNUSED:":
                self.exp_tab_node_orphan_node.setText(i18n['explorer_reunite_node'])
            else:
                self.exp_tab_node_orphan_node.setText(i18n['explorer_orphan_not_available'])
                self.exp_tab_node_orphan_node.setDisabled(True)
        self.META_adoption = True

        # * comments
        self.exp_tab_node_comment.setText(SpchtNode.get('comment', ""))
        # * release:
        self.surpress_comboevent = False

    def mthDisplayNodeDetails(self):
        indizes = self.explorer_node_treeview.selectedIndexes()
        if not indizes:
            return
        # * big copy & paste block for security & convinience
        if self.META_changed:
            if not self.utlChangedPrompt(i18n['dialogue_changed_upon_switch']):
                return

        item = indizes[0]  # name of the node, should better be unique
        nodeName = item.model().itemFromIndex(item).text()
        if nodeName in self.spcht_builder.repository:
            self.active_spcht_node = self.spcht_builder.compileNode(nodeName, always_inherit=True)
            self.explorer_toolbox.setItemText(2, f"{i18n['builder_toolbox_main_builder']} - {self.active_spcht_node['name']}")
            self.mthSetSpchtTabView(self.spcht_builder[nodeName].properties)
            self.mthComputeSpcht()
            self.mthLockTabview(False)
            self.explorer_tabview.setCurrentIndex(0)
            self.explorer_toolbox.setCurrentIndex(2)
            self.META_changed = False

    def mthComputeSpcht(self, spcht_descriptor=None):
        if not spcht_descriptor:
            spcht_descriptor = self.spcht_builder.compileNodeReference(self.active_spcht_node)
        if not self.active_data or not spcht_descriptor:
            return
        fake_spcht = {
            "id_source": "dict",
            "id_field": "id",
            "nodes": [spcht_descriptor]
        }
        habicht = Spcht()
        habicht._DESCRI = fake_spcht
        habicht.default_fields = []
        used_fields = habicht.get_node_fields2()
        element0 = copy.copy(self.active_data)
        if "fullrecord" in element0:
            element0.pop("fullrecord")
        habicht._raw_dict = element0
        if 'fullrecord' in self.active_data:
            habicht._m21_dict = SpchtUtility.marc2list(self.active_data['fullrecord'])
        self.explorer_filtered_data.setRowCount(len(used_fields))
        self.explorer_filtered_data.setColumnCount(2)
        self.explorer_filtered_data.setHorizontalHeaderLabels(["Key", "Value"])
        for i, key in enumerate(used_fields):  # lists all used fields
            if key == "fullrecord":
                continue
            self.explorer_filtered_data.setItem(i, 0, QTableWidgetItem(key))
            if key in element0:
                self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem(str(element0[key])))
            elif re.search(r"^[0-9]{1,3}:\w+$", key):  # filter for marc
                value = habicht.extract_dictmarc_value({'source': 'marc', 'field': key}, raw=True)
                if value:
                    self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem(str(value)))
                self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem("::MISSING::"))
            elif re.search(r"^((\w*)>)+\w+$", key):  # source tree, contains at least one 'word' + '>', otherwise it might be dict
                try:
                    value = habicht.extract_dictmarc_value({'source': 'tree', 'field': key}, raw=True)
                    if value:
                        self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem(str(value)))
                    else:
                        self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem("::MISSING::"))
                except TypeError as e:
                    print(f"TypeErorr: {e}")
            else:
                self.explorer_filtered_data.setItem(i, 1, QTableWidgetItem("::MISSING::"))
        self.explorer_filtered_data.resizeColumnToContents(0)
        self.explorer_filtered_data.horizontalHeader().setStretchLastSection(True)
        self.explorer_spcht_result.setText("")
        try:
            processsing_results = habicht._recursion_node(spcht_descriptor)
        except SpchtErrors.DataError as e:
            processsing_results = ""
            self.explorer_spcht_result.setText(f"SpchtError.DataError: {e}\n")
        except TypeError as e:
            processsing_results = ""
            self.explorer_spcht_result.setText(f"TypeError: {e}\n")
        if processsing_results:
            lines = ""
            for each in processsing_results:
                lines += f"{each.predicate} - {each.sobject}\n"
            self.explorer_spcht_result.setText(lines)
        else:
            self.explorer_spcht_result.append("::NORESULT::")

    def actDelayedSpchtComputing(self):
        self.META_changed = True
        if self.active_data:
            self.spcht_timer.start(1000)

    def mthCreateTempSpcht(self):
        if self.active_spcht_node:
            temp = self.mthNodeFormsToSpcht(self.active_spcht_node)
            if temp:
                # ? apparently to get the true temp node i need to get a new builder with the changed node so i can
                # ? can compile accordingly to properly collapse the dependencies..
                temp_builder = copy.deepcopy(self.spcht_builder)
                smp = SimpleSpchtNode(temp['name'])
                smp.import_dictionary(temp)
                #smp.parent = temp.get('parent', self.active_spcht_node.get('parent', ":MAIN:"))
                #smp.predicate_inheritance = temp.get('predicate_inheritance', True)
                temp_builder.modify(self.active_spcht_node['name'], smp)
                temp = temp_builder.compileNode(temp['name'], always_inherit=True)
                temp = temp_builder.compileNodeReference(temp)
                return temp
            return None

    def mthNodeFormsToSpcht(self, source_node=None):
        raw_node = {'required': 'optional'}  # legacy bullshit i thought that was more important in the past
        if source_node:
            raw_node = copy.copy(source_node)
        # self.exp_tab_node_field.setStyleSheet("border: 1px solid red; border-radius: 2px")
        for key, widget in self.LINE_EDITS.items():
            value = str(widget.text()).strip()
            if value != "":
                raw_node[key] = value
            else:
                raw_node.pop(key, None)
        for y in self.COMBOBOX:
            # this is a lil' bit dangerous with parent as it has 3 widgets that uses it
            value = str(y['widget'].currentText()).strip()
            if value != "":
                raw_node[y['key']] = value
            else:
                raw_node.pop(y['key'], None)
        # * special combo boxes (puts this whole complex system in question doesnt it?
        sub_data = str(self.exp_tab_node_subdata_of.currentText()).strip()
        sub_nodes = str(self.exp_tab_node_subnode_of.currentText()).strip()
        if sub_nodes or sub_data:
            raw_node['parent'] = sub_nodes if sub_nodes else sub_data
        else:
            raw_node['parent'] = self.active_spcht_node['parent']
        for key, details in self.CHECKBOX.items():
            raw_node[key] = details['bool'][details['widget'].isChecked()]
        for key, data in self.active_data_tables.items():
            if len(data):
                raw_node[key] = data
        for complex in self.COMPLEX:
            value = None
            if complex['type'] == "line":
                value = str(complex['widget'].text()).strip()
            if complex['type'] == "check":
                reverse_bool = {value: key for key, value in complex['bool'].items()}
                value = reverse_bool[complex['widget'].isChecked()]
            if value:
                keys = complex['key'].split(">")
                local_tools.setDeepKey(raw_node, value, *keys)
        # ? if handling
        if self.exp_tab_node_if_decider2.isChecked():  # single value mode:
            raw_node['if_value'] = self.active_data_tables.get('if_value', [])
        if 'if_value' in raw_node or 'if_field' in raw_node:
            if 'if_value' not in raw_node and raw_node['if_condition'] != "exi":
                raw_node.pop('if_value', None)
                raw_node.pop('if_field', None)
                raw_node.pop('if_condition', None)
            elif 'if_field' not in raw_node:
                raw_node.pop('if_value', None)
                raw_node.pop('if_field', None)
                raw_node.pop('if_condition', None)
            elif raw_node['if_condition'] not in SpchtConstants.SPCHT_BOOL_OPS:
                raw_node.pop('if_value', None)
                raw_node.pop('if_field', None)
                raw_node.pop('if_condition', None)
            elif 'if_value' in raw_node:
                if not isinstance(raw_node['if_value'], list):
                    raw_node['if_value'] = local_tools.convert_to_base_type(raw_node['if_value'])
                    if not isinstance(SpchtUtility.if_possible_make_this_numerical(raw_node['if_value']), (int, float)) and raw_node['if_condition'] in SpchtConstants.SPCHT_BOOL_NUMBERS:
                        raw_node.pop('if_value', None)
                        raw_node.pop('if_field', None)
                        raw_node.pop('if_condition', None)
        else:
            raw_node.pop('if_condition', None)
        # ? comments handling
        comments = self.exp_tab_node_comment.toPlainText()
        lines = comments.split("\n")
        if lines[0].strip() != "":
            raw_node['comment'] = lines[0].strip()
        for i in range(1, len(lines)):
            raw_node[f'comment{i}'] = lines[i]
        if SpchtUtility.is_dictkey(raw_node, 'field', 'source', 'required'):  # minimum viable node
            # after we have checked if everything is there...we delete things if we are in a very specific scenario
            return raw_node
        self.ERROR_missing_nodes = []  # basically an out or order error message, i should probably throw an exception instead
        for element in ["field", "source", "required"]:
            if element not in raw_node:
                self.ERROR_missing_nodes.append(element)
        return {}

    def actMappingInput(self):
        if not self.active_spcht_node:
            return
        compiled_mappings = {}
        if 'mapping' in self.active_spcht_node:
            compiled_mappings.update(self.active_spcht_node['mapping'])
        dlg = ListDialogue(i18n['dialogue_mapping_title'],
                           i18n['dialogue_mapping_text'],
                           [i18n['generic_key'], i18n['generic_value']],
                           compiled_mappings,
                           self)
        if dlg.exec_():
            self.active_data_tables['mapping'] = dlg.getData()
            self.exp_tab_node_mapping_preview.setText(str(self.active_data_tables['mapping']))

    def actDisplayJson(self, mode=0):
        if not self.active_spcht_node:
            return
        if mode == 1:
            data = self.active_spcht_node
        else:
            data = self.mthCreateTempSpcht()
        dlg = JsonDialogue(data)
        if dlg.exec_():
            print(dlg.getContent())

    def actShowCompleteBuilder(self):
        builder = json.dumps(self.spcht_builder.exportDict(), indent=3)
        dlg = JsonDialogue(builder)
        dlg.exec_()

    def actSetNodeParent(self, widget: QWidget):
        """
        Sets currfent parent and unsets the other two widgets, this method can probably be solved better
        :param widget:
        :type widget:
        :return: nothing
        :rtype: None
        """
        if self.surpress_comboevent:
            return
        self.surpress_comboevent = True  # we are doing single threading here, no further events
        if self.META_adoption:
            dlg = QMessageBox()
            dlg.setIcon(QMessageBox.Information)
            dlg.setWindowTitle(i18n['dialogue_parent_change_title'])
            dlg.setText(i18n['dialogue_parent_change'])
            dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            if dlg.exec_() == QMessageBox.Cancel:
                print(self.active_spcht_node.get("parent", ""))
                index = widget.findText(self.active_spcht_node.get("parent", ""), QtCore.Qt.MatchFixedString)
                if index > 0:
                    widget.setCurrentIndex(index)
                else:
                    widget.setCurrentIndex(0)
                self.surpress_comboevent = False
                return
            else:
                self.META_adoption = False
                self.META_changed = True
        value = str(widget.currentText()).strip()
        if value != "":
            for entry in self.COMBOBOX:
                if entry['key'] == "parent":
                    entry['widget'].setCurrentIndex(0)
            index = widget.findText(value, QtCore.Qt.MatchFixedString)
            if index > 0:
                widget.setCurrentIndex(index)
            else:
                widget.setCurrentIndex(0)
        self.surpress_comboevent = False

    def mthSpchtBuilderBtnStatus(self, status: int):
        if status == 0:
            SpchtChecker.massSetProperty(
                self.explorer_node_add_btn,
                self.explorer_node_export_btn,
                self.explorer_node_compile_btn,
                self.explorer_node_save_btn,
                disabled=True
            )
        elif status == 1:
            SpchtChecker.massSetProperty(
                self.explorer_node_add_btn,
                self.explorer_node_export_btn,
                self.explorer_node_compile_btn,
                self.explorer_node_save_btn,
                enabled=True
            )
        elif status == 2:  # only export as SpchtBuilder File
            pass
            # not yet supported / implemented

    def actChangeIfValue(self):
        if self.exp_tab_node_if_decider1.isChecked():
            self.exp_tab_node_if_many_values.setDisabled(True)
            self.exp_tab_node_if_enter_values.setDisabled(True)
            self.exp_tab_node_if_value.setDisabled(False)
        else:
            self.exp_tab_node_if_many_values.setDisabled(False)
            self.exp_tab_node_if_enter_values.setDisabled(False)
            self.exp_tab_node_if_value.setDisabled(True)

    def actChooseIfValues(self):
        dlg = ListDialogue(i18n['dialogue_if_values_title'],
                           i18n['dialogue_if_values_trext'],
                           [i18n['generic_value']],
                           self.active_data_tables.get('if_value'),
                           self)
        if dlg.exec_():
            self.active_data_tables['if_value'] = dlg.getData()
            self.exp_tab_node_if_many_values.setText(str(self.active_data_tables['if_value']))

    def actSaveSpchtBuilder(self):
        if not self.spcht_builder:
            return
        # in case the last node wasnt saved
        if self.META_changed:
            if not self.utlChangedPrompt(i18n['dialogue_changed_upon_save']):
                return

        path_To_File, file_type = QtWidgets.QFileDialog.getSaveFileName(self, i18n['dlg_save_spchtbuilder'], "./",
                                                                        "Spcht Json File (*.spchtbuilder.json);;Json File (*.json);;Every file (*.*)")
        if path_To_File:
            try:
                with codecs.open(path_To_File, "w", encoding='utf-8') as save_game:
                    json.dump(self.spcht_builder.exportDict(), save_game, indent=3, ensure_ascii=False)
                    self.META_unsaved = False
            except FileExistsError:
                logging.warning(f"Cannot overwrite file {path_To_File}")

    def actCreateSpchtBuilder(self):
        if self.META_unsaved:
            if not self.utlUnsavedPrompt(i18n['dialogue_unsaved_create']):
                return
        path = QFileDialog.getExistingDirectory(self, i18n['dia_folder_selection'])
        if path:
            self.mthCreateSpchtBuilder(path)

    def actOpenSpchtBuilder(self):
        if self.META_unsaved:
            if not self.utlUnsavedPrompt(i18n['dialogue_unsaved_load']):
                return
        path_To_File, file_type = QtWidgets.QFileDialog.getOpenFileName(self, i18n['dlg_open_spchtbuilder'], "./",
                                                                        "Spcht Json File (*.spchtbuilder.json);;Json File (*.json);;Every file (*.*)")
        if path_To_File:
            try:
                with open(path_To_File, "r") as spchtbuilderjson:
                    details = None
                    raw_builder = json.load(spchtbuilderjson)
            except FileNotFoundError:
                details = f"Could not find the file path '{path_To_File}' despite OpenSpchtBuilder providing one by dialogue."
                logging.warning(details)
            except json.decoder.JSONDecodeError as e:
                details = f"'SpchtBuilder.json' file found but reading it failed: {e}"
                logging.warning(details)
            if details:
                dlg = QMessageBox(parent=self)
                dlg.setIcon(QMessageBox.Warning)
                dlg.setDetailedText(details)
                dlg.setWindowTitle(i18n['dialogue_open_spchtbuilder_failure_title'])
                dlg.setText(i18n['dialogue_open_spchtbuilder_failure'])
                dlg.exec_()
                return
            leiharbeiter = SpchtBuilder(spcht_base_path=str(Path(path_To_File).parent))  # reset the thing # Leiharbeiter = basically a consultant but paid worse
            if leiharbeiter.importDict(raw_builder):
                self.spcht_builder = leiharbeiter
                self.utlWriteStatus("Loaded SpchtBuilder.json file")
                self.mthSpchtBuilderBtnStatus(1)
                self.explorer_toolbox.setItemText(1, f"{i18n['builder_toolbox_node_overview']} - {path_To_File}")
                self.mthFillNodeView(self.spcht_builder.displaySpcht())
                self.explorer_toolbox.setCurrentIndex(1)
            else:
                print("failed to load import")

    def mthCreateSpchtBuilder(self, directory):
        self.mthSpchtBuilderBtnStatus(1)
        self.spcht_builder = SpchtBuilder(spcht_base_path=directory)
        self.spcht_builder.root['field'] = "id"
        self.spcht_builder.root['source'] = "dict"
        self.mthFillNodeView(self.spcht_builder.displaySpcht())
        self.mthLockTabview(True)
        self.active_spcht_node = None
        self.active_data = None
        self.META_unsaved = True
        self.META_changed = False

    def actCreateSpchtNode(self):
        if self.META_changed:
            if not self.utlChangedPrompt(i18n['dialogue_changed_upon_new']):
                return

        new_node = self.spcht_builder._names.giveName()
        emptyNode = SimpleSpchtNode(new_node, parent=":MAIN:")
        emptyNode['field'] = ""
        emptyNode['source'] = "dict"
        emptyNode['required'] = "optional"
        emptyNode['predicate'] = ""
        self.spcht_builder.add(emptyNode)
        self.mthFillNodeView(self.spcht_builder.displaySpcht())
        self.active_spcht_node = self.spcht_builder.compileNode(new_node, always_inherit=True)
        self.mthSetSpchtTabView(self.spcht_builder[new_node].properties)
        self.mthComputeSpcht()
        self.mthLockTabview(False)
        self.explorer_tabview.setCurrentIndex(0)
        self.explorer_toolbox.setCurrentIndex(2)
        self.META_changed = True

    def actDuplicateSpchtNode(self):
        indizes = self.explorer_node_treeview.selectedIndexes()
        if not indizes:
            return
        item = indizes[0]
        nodeName = item.model().itemFromIndex(item).text()
        if nodeName not in self.spcht_builder:
            return

        if self.META_changed:
            if not self.utlChangedPrompt(i18n['dialogue_changed_upon_switch']):
                return

        new_node = copy.deepcopy(self.spcht_builder[nodeName])
        new_node['name'] = f"Copy {nodeName}"
        new_name = self.spcht_builder.add(new_node)
        self.mthFillNodeView(self.spcht_builder.displaySpcht())
        self.active_spcht_node = self.spcht_builder.compileNode(new_name, always_inherit=True)
        self.mthSetSpchtTabView(self.spcht_builder[new_name].properties)
        self.mthComputeSpcht()
        self.mthLockTabview(False)
        self.explorer_tabview.setCurrentIndex(0)
        self.explorer_toolbox.setCurrentIndex(2)
        self.META_changed = True

    def actCloneSpchtNode(self):
        indizes = self.explorer_node_treeview.selectedIndexes()
        if not indizes:
            return
        item = indizes[0]
        nodeName = item.model().itemFromIndex(item).text()
        if nodeName not in self.spcht_builder:
            return

        if self.META_changed:
            if not self.utlChangedPrompt(i18n['dialogue_changed_upon_switch']):
                return

        new_name = self.spcht_builder.clone(nodeName)
        self.mthFillNodeView(self.spcht_builder.displaySpcht())
        self.active_spcht_node = self.spcht_builder.compileNode(new_name, always_inherit=True)
        self.mthSetSpchtTabView(self.spcht_builder[new_name].properties)
        self.mthComputeSpcht()
        self.mthLockTabview(False)
        self.explorer_tabview.setCurrentIndex(0)
        self.explorer_toolbox.setCurrentIndex(2)
        self.META_changed = True

    def actExportSpchtNode(self):
        file, type = QFileDialog.getSaveFileName(self, i18n['spcht_save_from_builder'], self.spcht_builder.cwd, f"{i18n['spcht_file_name']} (*.spcht.json);;")
        if file:
            if not re.search(r"spcht\.json$", file):
                file = f"{file}.spcht.json"
            self.mthExportSpchtNode(file)

    def mthExportSpchtNode(self, path):
        with codecs.open(path, "w", encoding='utf-8') as spcht_file:
            json.dump(self.spcht_builder.createSpcht(), spcht_file, indent=3, ensure_ascii=False)

    def mthSaveBuilderNode(self):
        if not self.active_spcht_node:
            return
        new_node = self.mthNodeFormsToSpcht(self.active_spcht_node)
        if new_node:
            smp_node = SimpleSpchtNode(new_node['name'])
            smp_node.import_dictionary(new_node)
            #smp_node.properties = new_node
            #smp_node.parent = new_node.get('parent', ":MAIN:")
            # smp_node['fallback'] = new_node.get('fallback') if new_node['fallback']['name'] else ''
            # smp_node['sub_nodes'] = new_node.get('sub_nodes') if new_node['sub_nodes']['name'] else ''
            # smp_node['sub_data'] = new_node.get('sub_data') if new_node['sub_data']['name'] else ''
            new_name = self.spcht_builder.modify(self.active_spcht_node['name'], smp_node)
            self.mthFillNodeView(self.spcht_builder.displaySpcht())
            self.explorer_toolbox.setCurrentIndex(1)
            # resetting interface
            self.mthLockTabview()
            self.active_spcht_node = None
            self.active_data_tables = {}
            self.META_changed = False
            self.META_unsaved = True
            self.explorer_toolbox.setItemText(2, i18n['builder_toolbox_main_builder'])
            return new_name
        else:
            dlg = QMessageBox(parent=self)
            dlg.setIcon(QMessageBox.Information)
            dlg.setWindowTitle(i18n['dialogue_missing_content_title'])
            dlg.setText(i18n['dialogue_missing_content'])
            dlg.setDetailedText(f"{i18n['dialogue_missing_details']}\n{', '.join(self.ERROR_missing_nodes)}")
            dlg.setStandardButtons(QMessageBox.Ok)
            dlg.exec_()
            return False

    def orphanNode(self):
        """
        Unmoores a node from :MAIN: or retethers it
        """
        if not self.active_spcht_node:
            return
        node_name = self.mthSaveBuilderNode()
        if node_name:
            self.spcht_builder.parkNode(node_name)  # yes, i extended SpchtBuilder for that
            self.mthFillNodeView(self.spcht_builder.displaySpcht())  # second time, a bit redundant

    def deleteBuilderNode(self):
        if not self.active_spcht_node:
            return
        dlg = QMessageBox(parent=self)
        dlg.setIcon(QMessageBox.Critical)
        dlg.setWindowTitle(i18n['dialogue_confirm_delete_title'])
        dlg.setText(f"{i18n['dialogue_confirm_delete']} {self.active_spcht_node['name']}")
        dlg.setDetailedText(json.dumps(self.spcht_builder.compileNode(self.active_spcht_node['name']), indent=2))
        dlg.setStandardButtons(QMessageBox.Discard | QMessageBox.Abort)
        if dlg.exec_() == QMessageBox.Abort:
            return
        self.spcht_builder.remove(self.active_spcht_node['name'])
        self.mthFillNodeView(self.spcht_builder.displaySpcht())
        self.explorer_toolbox.setCurrentIndex(1)
        # resetting interface
        self.mthLockTabview()
        self.active_spcht_node = None
        self.active_data_tables = {}
        self.META_changed = False
        self.META_unsaved = True

    def mthLockTabview(self, status=True):
        if status:
            self.mthSetSpchtTabView(SpchtNode=None)
            self.explorer_tabview.setCurrentIndex(0)
            self.explorer_tabview.setDisabled(True)
        else:
            self.explorer_tabview.setDisabled(False)

    def actSpchtTabviewColumnMenu(self, pos):
        menu = QMenu()
        self.tabview_menus = {}
        for each in self.node_headers:
            if each['key'] == "name":
                continue
            self.tabview_menus[each['key']] = QAction(each['header'])
            self.tabview_menus[each['key']].setCheckable(True)
            if self.tabview_active_columns[each['key']]:
                self.tabview_menus[each['key']].setChecked(True)
           # self.tabview_menus[each['key']].toggled.connect(lambda: self.actToggleTabviewColumn(each['key']))
            menu.addAction(self.tabview_menus[each['key']])
        #menu.popup(self.explorer_node_treeview.mapToGlobal(pos))
        all_act = QAction(i18n['menu_display_all'])
        all_act.triggered.connect(self.actDisplayAllTabviewColumns)
        # Test with complex widget
        # move = MoveUpDownWidget("Name")
        # test = QWidgetAction(menu)
        # test.setDefaultWidget(move)
        # menu.addAction(test)
        menu.addSeparator()
        menu.addAction(all_act)
        # ! this is like the worst solution ever but i wont just work
        self.tabview_menus['source'].toggled.connect(lambda: self.actToggleTabviewColumn('source'))
        self.tabview_menus['field'].toggled.connect(lambda: self.actToggleTabviewColumn('field'))
        self.tabview_menus['predicate'].toggled.connect(lambda: self.actToggleTabviewColumn('predicate'))
        self.tabview_menus['type'].toggled.connect(lambda: self.actToggleTabviewColumn('type'))
        self.tabview_menus['mandatory'].toggled.connect(lambda: self.actToggleTabviewColumn('mandatory'))
        self.tabview_menus['sub_nodes'].toggled.connect(lambda: self.actToggleTabviewColumn('sub_nodes'))
        self.tabview_menus['sub_data'].toggled.connect(lambda: self.actToggleTabviewColumn('sub_data'))
        self.tabview_menus['fallback'].toggled.connect(lambda: self.actToggleTabviewColumn('fallback'))
        self.tabview_menus['tech'].toggled.connect(lambda: self.actToggleTabviewColumn('tech'))
        self.tabview_menus['comment'].toggled.connect(lambda: self.actToggleTabviewColumn('comment'))
        menu.exec_(self.explorer_node_treeview.mapToGlobal(pos))

    def actToggleTabviewColumn(self, key):
        if self.tabview_active_columns[key]:
            self.tabview_active_columns[key] = False
        else:
            self.tabview_active_columns[key] = True
        self.mthHideTabviewColumns()

    def actFallbackWarning(self):
        if self.surpress_comboevent:
            return
        fallback = self.exp_tab_node_fallback.currentText()
        node_fallback = self.spcht_builder[self.active_spcht_node['name']].get('fallback', "")
        if fallback == node_fallback:
            return
        alarm = False  # just do escape the 20x indent
        for name, node in self.spcht_builder.items():
            if 'fallback' not in node:
                continue
            if node['fallback'] == fallback:
                alarm = True
                break
        if not alarm:
            return
        dlg = QMessageBox()
        dlg.setText(i18n['dialogue_overwrite_fallback'])
        dlg.setWindowTitle(i18n['dialogue_overwrite_fallback_title'])
        dlg.setIcon(QMessageBox.Warning)
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Reset)
        self.surpress_comboevent = True
        if dlg.exec_() == QMessageBox.Reset:
            idx = self.exp_tab_node_fallback.findText(node_fallback, QtCore.Qt.MatchFixedString)
            if idx > 0:
                self.exp_tab_node_fallback.setCurrentIndex(idx)
            else:
                self.exp_tab_node_fallback.setCurrentIndex(0)
        self.surpress_comboevent = False

    def actDisplayAllTabviewColumns(self):
        for key in self.tabview_active_columns:
            self.tabview_active_columns[key] = True
        self.mthHideTabviewColumns()

    def mthHideTabviewColumns(self):
        for _, each in enumerate(self.node_headers):
            if each['key'] == "name":
                continue
            self.explorer_node_treeview.setColumnHidden(_, not self.tabview_active_columns[each['key']])

    def utlUnsavedPrompt(self, text):
        dlg = QMessageBox(parent=self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle(i18n['dialogue_unsaved_title'])
        dlg.setText(text)
        dlg.setStandardButtons(QMessageBox.Close | QMessageBox.Cancel)
        dlg.setDefaultButton(QMessageBox.Close)
        dlg.setEscapeButton(QMessageBox.Cancel)
        returnal = dlg.exec_()
        if returnal == QMessageBox.Cancel:
            return False
        return True

    def utlChangedPrompt(self, text):
        dlg = QMessageBox(parent=self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle(i18n['dialogue_changed_title'])
        dlg.setText(text)
        dlg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        dlg.setDefaultButton(QMessageBox.Save)
        dlg.setEscapeButton(QMessageBox.Cancel)
        returnal = dlg.exec_()
        if returnal == QMessageBox.Cancel:
            return False
        elif returnal == QMessageBox.Save:
            # message box galore
            if not self.mthSaveBuilderNode():
                dlg = QMessageBox(parent=self)
                dlg.setIcon(QMessageBox.Critical)
                dlg.setWindowTitle(i18n['dialogue_discard_title'])
                dlg.setText(i18n['dialogue_discard_changes'])
                dlg.setStandardButtons(QMessageBox.Discard | QMessageBox.Cancel)
                dlg.setDefaultButton(QMessageBox.Discard)
                dlg.setEscapeButton(QMessageBox.Cancel)
                returnal = dlg.exec_()
                if returnal == QMessageBox.Cancel:
                    return False
        return True


def Run():
    thisApp = QtWidgets.QApplication(sys.argv)
    thisApp.setWindowIcon(QIcon(resource_path('./SpchtCheckerGui/woodpecker.png')))
    window = SpchtChecker()
    window.show()
    try:
        sys.exit(thisApp.exec_())
    except KeyboardInterrupt:
        sys.exit()


if __name__ == "__main__":
    Run()

