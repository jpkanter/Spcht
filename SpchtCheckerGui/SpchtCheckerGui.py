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
import time
from io import StringIO
from datetime import datetime
from pathlib import Path

from PySide2.QtGui import QStandardItemModel, QStandardItem, QFontDatabase, QIcon, QScreen
from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtCore

from dateutil.relativedelta import relativedelta

import SpchtConstants
import SpchtErrors
import local_tools
from SpchtBuilder import SpchtBuilder
from SpchtCore import Spcht, SpchtThird, SpchtTriple

import SpchtUtility
from SpchtCheckerGui_interface import SpchtMainWindow, ListDialogue, JsonDialogue, QLogHandler
from SpchtCheckerGui_i18n import Spcht_i18n
i18n = Spcht_i18n("./GuiLanguage.json")


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

    return dictlist  # this will most likely throw an exception, we kinda want that


class SpchtChecker(QMainWindow, SpchtMainWindow):
    # as there should be always only one instance of this its hopefully okay this way
    node_headers = [{'key': "name", 'header': i18n['col_name']},
                    {'key': "source", 'header': i18n['col_source']},
                    {'key': "field", 'header': i18n['col_field']},
                    {'key': "predicate", 'header': i18n['col_predicate']},
                    {'key': "type", 'header': i18n['col_type']},
                    {'key': "mandatory", 'header': i18n['col_mandatory']},
                    {'key': "sub_nodes", 'header': i18n['col_sub_nodes']},
                    {'key': "sub_data", 'header': i18n['col_sub_data']},
                    {'key': "fallback", 'header': i18n['col_fallback']},
                    {'key': "comment", 'header': i18n['col_comment']}]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.create_ui(self)
        self.taube = Spcht()

        self.data_cache = None
        self.spcht_builder = None
        self.active_spcht_node = None
        self.active_data = None
        self.active_data_tables = {}
        self.active_data_index = 0

        # * Event Binds
        self.setup_event_binds()
        self.setupNodeTabConstants()

        # various
        self.console.insertPlainText(time_log(f"Init done, program started"))
        self.console.insertPlainText(f"Working Directory: {os.getcwd()}")
        # self.setupLogging()  # plan was to get logging into the console widget but i am too stupid

        self.center()

        # * Savegames
        self.lineeditstyle = self.exp_tab_node_field.styleSheet()  # this is probably a horrible idea

    def setupNodeTabConstants(self):
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
                         {'key': "parent", 'widget': self.exp_tab_node_subdata_of},
                         {'key': "parent", 'widget': self.exp_tab_node_subnode_of},
                         {'key': "parent", 'widget': self.exp_tab_node_fallback}
                         ]
        self.CHECKBOX = {"required": {
                            "widget": self.exp_tab_node_mandatory,
                            "bool": {False: "optional", True: "mandatory"}
                        },
                        "type": {
                            "widget": self.exp_tab_node_uri,
                            "bool": {False: "literal", True: "uri"}
                        }
                        }
        self.CLEARONLY = [
            {'mth': "line", 'widget': self.exp_tab_node_mapping_preview},
            {'mth': "line", 'widget': self.exp_tab_node_mapping_ref_path}
        ]
        self.COMPLEX = [
            {'type': "line", 'widget': self.exp_tab_node_mapping_ref_path, 'key': 'mapping_settings>$ref'},
            {'type': "line", 'widget': self.exp_tab_mapping_default, 'key': 'mapping_settings>$default'},
            {'type': "check", 'widget': self.exp_tab_mapping_inherit, 'key': 'mapping_settings>$inherit', 'bool': {True: True, False: False}},
            {'type': "check", 'widget': self.exp_tab_mapping_regex, 'key': 'mapping_settings>$regex', 'bool': {True: True, False: False}},
            {'type': "check", 'widget': self.exp_tab_mapping_casesens, 'key': 'mapping_settings>$casesens', 'bool': {True: True, False: False}},
        ]
        self.FILL = [
            {'type': "combo", 'widget': self.exp_tab_node_subdata_of, 'fct': "getSubdataParents"},
            {'type': "combo", 'widget': self.exp_tab_node_subnode_of, 'fct': "getSubnodeParents"},
            {'type': "combo", 'widget': self.exp_tab_node_fallback, 'fct': "getSolidParents"}
        ]
        self.dialogue = [
            {'key': "if_value", 'data': "list", 'widget': self.exp_tab_node_if_many_values},
            {'key': "insert_add_fields", 'data': "listdict", 'widget': self.tab_node_insert_add_fields},
            {'key': "mapping", 'data': "dict", 'widget': self.exp_tab_node_mapping_preview}
        ]

    def setup_event_binds(self):
        self.btn_load_spcht_file.clicked.connect(self.actLoadSpcht)
        self.btn_load_spcht_retry.clicked.connect(self.btn_spcht_load_retry)
        self.btn_tristate.clicked.connect(self.toogleTriState)
        self.btn_load_testdata_file.clicked.connect(lambda: self.actLoadTestData(True))
        self.btn_load_testdata_retry.clicked.connect(self.actRetryTestdata)
        self.btn_tree_expand.clicked.connect(self.treeview_main_spcht_data.expandAll)
        self.btn_tree_collapse.clicked.connect(self.treeview_main_spcht_data.collapseAll)
        self.btn_change_main.clicked.connect(self.actChangeMainView)
        self.explorer_switch_checker.clicked.connect(self.actChangeMainView)
        self.toogleTriState(0)
        # self.explorer_data_file_path.doubleClicked.connect(self.act_data_load_dialogue)  # line edit does not emit events :/
        self.explorer_data_load_button.clicked.connect(self.actLoadTestData)
        self.explorer_field_filter.textChanged[str].connect(self.actExecDelayedFieldChange)
        self.input_timer.timeout.connect(self.mthExecDelayedFieldChange)
        self.explorer_field_filter.returnPressed.connect(self.mthExecDelayedFieldChange)
        self.explorer_filter_behaviour.stateChanged.connect(self.mthExecDelayedFieldChange)

        #self.explorer_center_search_button.clicked.connect(self.test_button)
        self.explorer_node_import_btn.clicked.connect(self.actLoadSpcht)
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
        self.spcht_timer.timeout.connect(self.mthCreateTempSpcht)
        self.exp_tab_node_name.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_field.textChanged[str].connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_tag.textChanged[str].connect(self.actDelayedSpchtComputing)
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
        self.exp_tab_node_if_condition.currentIndexChanged.connect(self.actDelayedSpchtComputing)
        self.exp_tab_node_source.currentIndexChanged.connect(self.actDelayedSpchtComputing)

        self.exp_tab_node_fallback.currentIndexChanged.connect(lambda: self.actSetNodeParent(self.exp_tab_node_fallback))
        self.exp_tab_node_subdata_of.currentIndexChanged.connect(lambda: self.actSetNodeParent(self.exp_tab_node_subdata_of))
        self.exp_tab_node_subnode_of.currentIndexChanged.connect(lambda: self.actSetNodeParent(self.exp_tab_node_subnode_of))

        self.exp_tab_node_display_spcht.clicked.connect(lambda: self.actDisplayJson(1))
        self.exp_tab_node_display_computed.clicked.connect(lambda: self.actDisplayJson(0))

    def setupLogging(self):
        handler = QLogHandler(self)
        logging.getLogger(__name__).addHandler(handler)
        logging.getLogger(__name__).setLevel(logging.DEBUG)
        handler.new_record.connect(self.console.append)
        #logging.warning("i think this isnt working at all, sad times")

    def center(self):
        center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())

    def btn_spcht_load_retry(self):
        self.load_spcht(self.linetext_spcht_filepath.displayText())

    def load_spcht(self, path_To_File):
        try:
            with open(path_To_File, "r") as file:
                spcht_data = json.load(file)
                status, output = SpchtUtility.schema_validation(spcht_data, schema="./SpchtSchema.json")
        except json.decoder.JSONDecodeError as e:
            self.console.insertPlainText(time_log(f"JSON Error: {str(e)}"))
            self.write_status("Json error while loading Spcht")
            self.toogleTriState(0)
            return None
        except FileNotFoundError as e:
            self.console.insertPlainText(time_log(f"File not Found: {str(e)}"))
            self.write_status("Spcht file could not be found")
            self.toogleTriState(0)
            return None

        if status:
            if not self.taube.load_descriptor_file(path_To_File):
                self.console.insertPlainText(time_log(
                    f"Unknown error while loading SPCHT, this is most likely something the checker engine doesnt account for, it might be 'new'"))
                self.write_status("Unexpected kind of error while loading Spcht")
                return False
            self.toogleTriState(1)
            self.btn_load_testdata_file.setDisabled(False)
            self.populate_treeview_with_spcht()
            self.populate_text_views()
            self.write_status("Loaded spcht discriptor file")
            self.mthSpchtBuilderBtnStatus(1)
            self.explorer_node_spcht_filepath.setText(path_To_File)
            self.spcht_builder = SpchtBuilder(spcht_data, spcht_base_path=str(Path(path_To_File).parent))
            # ? debug - spchtbuilder to console
            self.console.append("All SpchtBuilder Entries\n")
            for key, entry in self.spcht_builder.repository.items():
                self.console.append(f"{key} - {str([f'{k}={v}' for k, v in entry.properties.items()])}\n")
            self.mthFillNodeView(self.spcht_builder.displaySpcht())
        else:
            self.console.insertPlainText(time_log(f"SPCHT Schema Error: {output}"))
            self.write_status("Loading of spcht failed")
            self.toogleTriState(0)
            return None

    def populate_treeview_with_spcht(self):
        i = 0
        # populate views
        if self.spchttree_view_model.hasChildren():
            self.spchttree_view_model.removeRows(0, self.spchttree_view_model.rowCount())
        for each in self.taube:
            i += 1
            tree_row = QStandardItem(each.get('name', f"Element #{i}"))
            SpchtChecker.populate_treeview_recursion(tree_row, each)
            tree_row.setEditable(False)
            self.spchttree_view_model.appendRow(tree_row)
            self.treeview_main_spcht_data.setFirstColumnSpanned(i - 1, self.treeview_main_spcht_data.rootIndex(), True)

    @staticmethod
    def populate_treeview_recursion(parent, node):
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
            SpchtChecker.populate_treeview_recursion(parent, node['fallback'])

    def populate_text_views(self):
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

    def toogleTriState(self, status=0):
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
        path_To_File, file_type = QtWidgets.QFileDialog.getOpenFileName(self, "Open spcht descriptor file", "../", "Spcht Json File (*.spcht.json);;Json File (*.json);;Every file (*.*)")

        if not path_To_File:
            return None

        self.btn_load_spcht_retry.setDisabled(False)
        self.linetext_spcht_filepath.setText(path_To_File)
        self.load_spcht(path_To_File)

    def mthGatherAvailableFields(self, data=None, marc21=False):
        if not data:
            data = self.data_cache
        if not data:
            return []
        all_fields = []
        for _, block in enumerate(data):
            for key in block.keys():
                all_fields.append(key)
            if 'fullrecord' in block and marc21:
                temp_marc = SpchtUtility.marc2list(block['fullrecord'])
                for main_key, top_value in temp_marc.items():
                    if isinstance(top_value, list):
                        for param_list in top_value:
                            for sub_key in param_list:
                                all_fields.append(f"{main_key}:{sub_key}")
                                all_fields.append(f"{main_key:03d}:{sub_key}")
                    elif isinstance(top_value, dict):
                        for sub_key in top_value:
                            all_fields.append(f"{main_key}:{sub_key}")
                            all_fields.append(f"{main_key:03d}:{sub_key}")  # i think this is faster than if-ing my way through
            if _ > 100:
                # ? having halt conditions like this always seems arbitrary but i really struggle to imagine how much more
                # ? unique keys one hopes to get after 100 entries. On my fairly beefy machine the processing for 500
                # ? entries was 3,01 seconds, for 10K it was around 46 seconds. The 600ms for 100 seem acceptable
                break
        return list(set(all_fields))

    def actLoadTestData(self, graph_prompt=False):
        path_to_file, type = QtWidgets.QFileDialog.getOpenFileName(self, "Open explorable data", "../", "Json File (*.json);;Every file (*.*)")

        if path_to_file == "":
            return None

        try:
            with open(path_to_file, "r") as file:
                test_data = json.load(file)
        except FileNotFoundError:
            self.write_status("Loading of example Data file failed.")
            return False
        except json.JSONDecodeError as e:
            self.write_status(f"Example data contains json errors: {e}")
            self.console.insertPlainText(time_log(f"JSON Error in Example File: {str(e)}"))
            return False
        if test_data:
            # * legacy checker things:
            self.str_testdata_filepath.setText(path_to_file)
            # * explorer stuff
            self.explorer_data_file_path.setText(path_to_file)
            self.data_cache = handle_variants(test_data)
            if len(self.data_cache):
                self.active_data = self.data_cache[0]
                self.active_data_index = 0
                self.explorer_linetext_search.setPlaceholderText(f"{1} / {len(self.data_cache)}")
                self.fct_fill_explorer(self.data_cache)
                temp_model = QStandardItemModel()
                [temp_model.appendRow(QStandardItem(x)) for x in self.mthGatherAvailableFields(marc21=True)]
                self.field_completer.setModel(temp_model)
                if self.active_spcht_node:
                    self.mthCreateTempSpcht()

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

    def actRetryTestdata(self):
        if self.data_cache:
            self.load_spcht(self.linetext_spcht_filepath.displayText())
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
                            self.write_status("Auxilliary data isnt in expected format")
                            code_green = 0
                            break
                    if code_green == 1:
                        debug_dict = temp_dict
        except FileNotFoundError:
            self.write_status("No auxilliary data has been found")
            pass  # nothing happens
        except json.JSONDecodeError:
            self.write_status("Loading of auxilliary testdata failed due a json error")
            pass  # also okay
        # loading debug data from debug dict if possible
        time_process_start = datetime.now()

        tbl_list = []
        text_list = []
        thetestset = handle_variants(self.data_cache)
        self.progressMode(True)
        self.processBar.setMaximum(len(thetestset))
        i = 0
        for entry in thetestset:
            i += 1
            self.processBar.setValue(i)
            try:
                temp = self.taube.process_data(entry, subject)
            except Exception as e:  # probably an AttributeError but i actually cant know, so we cast the WIDE net
                self.progressMode(False)
                self.write_status(f"SPCHT interpreting encountered an exception {e}")
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
        self.toogleTriState(2)
        time3 = datetime.now()-time_process_start
        self.write_status(f"Testdata processing finished, took {delta_time_human(microseconds=time3.microseconds)}")
        self.progressMode(False)
        return True

    def write_status(self, text):
        self.notifybar.showMessage(time_log(text, time_string="%H:%M:%S", spacer=" ", end=""))

    def progressMode(self, mode):
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
            filtering = self.explorer_field_filter.text()
            self.fct_fill_explorer(self.data_cache, filtering)

    def fct_fill_explorer(self, data, filtering=None):
        # * Check if filter is elegible

        all_keys = set()
        for line in data:
            for key in line:
                if key != "fullrecord":  # ! TODO: do not make fullrecord static text
                    all_keys.add(key)
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
        self.mthCreateTempSpcht()
        #self.mthComputeSpcht()

    def mthFillNodeView(self, builder_display_data):
        floating_model = QStandardItemModel()
        floating_model.setHorizontalHeaderLabels([x['header'] for x in self.node_headers])
        for big_i, (parent, group) in enumerate(builder_display_data.items()):
            top_node = QStandardItem(parent)
            for i, each in enumerate(group):
                for index, key in enumerate(self.node_headers):
                    element = QStandardItem(each.get(key['key'], ""))
                    element.setEditable(False)
                    top_node.setChild(i, index, element)
            floating_model.setItem(big_i, 0, top_node)
            top_node.setEditable(False)
        self.explorer_node_treeview.setModel(floating_model)
        self.explorer_node_treeview.expandAll()

    def mthSetSpchtTabView(self, SpchtNode=None):  # aka NodeToForms
        if not SpchtNode:
            SpchtNode = {}  # PEP no likey when setting to immutable as default

        # ? fills combo boxes with dynamic data
        for fill in self.FILL:
            if fill['type'] == "combo":
                gaseous = QStandardItemModel()
                gaseous.appendRow(QStandardItem(""))
                data = getattr(self.spcht_builder, fill['fct'])()
                for each in data:
                    gaseous.appendRow(QStandardItem(each))
                fill['widget'].setModel(gaseous)
        # ? simple data that is just an arbitrary string
        for key, widget in self.LINE_EDITS.items():
            value = SpchtNode.get(key, "")
            if isinstance(value, (int, float, str)):
                widget.setText(value)
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
        # ? just clears all the fields that do not get assigned a value by default
        for details in self.CLEARONLY:
            if details['mth'] == "line":
                details['widget'].setText("")
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


    def mthDisplayNodeDetails(self):
        indizes = self.explorer_node_treeview.selectedIndexes()
        if not indizes:
            return
        item = indizes[0] # name of the node, should better be unique
        nodeName = item.model().itemFromIndex(item).text()
        if nodeName in self.spcht_builder.repository:
            self.active_spcht_node = self.spcht_builder.compileNode(nodeName)
            self.mthSetSpchtTabView(self.spcht_builder[nodeName].properties)
            self.mthComputeSpcht()
        self.explorer_tabview.setCurrentIndex(0)
        self.explorer_toolbox.setCurrentIndex(2)

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
        habicht._m21_dict = SpchtUtility.marc2list(copy.copy(self.active_data).get('fullrecord'))
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
        if processsing_results:
            lines = ""
            for each in processsing_results:
                lines += f"{each.predicate} - {each.sobject}\n"
            self.explorer_spcht_result.setText(lines)
        else:
            self.explorer_spcht_result.append("::NORESULT::")

    def actDelayedSpchtComputing(self):
        if self.active_data:
            self.spcht_timer.start(1000)

    def mthCreateTempSpcht(self):
        if self.active_spcht_node:
            temp = self.mthNodeFormsToSpcht(self.active_spcht_node)
            if temp:
                temp = self.spcht_builder.compileNodeReference(temp)
                self.mthComputeSpcht(temp)

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
            return raw_node
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
            data = self.mthNodeFormsToSpcht(self.active_spcht_node)
        dlg = JsonDialogue(data)
        if dlg.exec_():
            print(dlg.getContent())

    def actSetNodeParent(self, widget: QWidget):
        """
        Sets currfent parent and unsets the other two widgets, this method can probably be solved better
        :param widget:
        :type widget:
        :return: nothing
        :rtype: None
        """
        # ! TODO: something not right, only works for last entry / fallback
        value = str(widget.currentText()).strip()
        if value != "":
            for y in self.COMBOBOX:
                if y['key'] == "parent":
                    y['widget'].currentIndexChanged.disconnect()
                    y['widget'].setCurrentIndex(0)
            index = widget.findText(value, QtCore.Qt.MatchFixedString)
            if index > 0:
                widget.setCurrentIndex(index)
            else:
                widget.setCurrentIndex(0)
        for z in self.COMBOBOX:
            if z['key'] == "parent":
                z['widget'].currentIndexChanged.connect(lambda: self.actSetNodeParent(z['widget']))

    def mthSpchtBuilderBtnStatus(self, status: int):
        if status == 0:
            SpchtChecker.massSetProperty(
                self.explorer_node_add_btn,
                self.explorer_node_export_btn,
                self.explorer_node_compile_btn,
                disabled=True
            )
        elif status == 1:
            SpchtChecker.massSetProperty(
                self.explorer_node_add_btn,
                self.explorer_node_export_btn,
                self.explorer_node_compile_btn,
                enabled=True
            )
        elif status == 2:  # only export as SpchtBuilder File
            pass
            # not yet supported / implemented


if __name__ == "__main__":
    thisApp = QtWidgets.QApplication(sys.argv)
    thisApp.setWindowIcon(QIcon(':/icons/woodpecker.ico'))
    window = SpchtChecker()
    window.show()
    try:
        sys.exit(thisApp.exec_())
    except KeyboardInterrupt:
        sys.exit()
