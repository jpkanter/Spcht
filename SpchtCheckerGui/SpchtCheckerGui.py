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
import os
import re
import sys
from io import StringIO
from datetime import datetime
from pathlib import Path

from PySide2.QtGui import QStandardItemModel, QStandardItem, QFontDatabase, QIcon
from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtCore
from dateutil.relativedelta import relativedelta
from SpchtDescriptorFormat import Spcht
import SpchtUtility
import SpchtCheckerGui_i18n

# Windows Stuff for Building under Windows
try:
    from PySide2.QtWinExtras import QtWin
    myappid = 'UBL.SPCHT.checkerGui.0.2'
    QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

# ! import language stuff
i18n = SpchtCheckerGui_i18n.Spcht_i18n("./SpchtCheckerGui/GuiLanguage.json")


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
                break
        # ! condition for go_purple here
        return dictlist
    if isinstance(dictlist, dict):
        if 'response' in dictlist:
            if 'docs' in dictlist['response']:
                return dictlist['response']['docs']

    return dictlist  # this will most likely throw an exception, we kinda want that


class SpchtChecker(QDialog):

    def __init__(self):
        super(SpchtChecker, self).__init__()
        FIXEDFONT = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        FIXEDFONT.setPointSize(10)
        self.taube = Spcht()
        # * Window Setup
        self.setBaseSize(1280, 720)
        self.setMinimumSize(720, 480)
        self.setWindowTitle(i18n['window_title'])
        self.setWindowFlags(QtCore.Qt.WindowMinimizeButtonHint & QtCore.Qt.WindowMaximizeButtonHint)

        main_layout = QGridLayout(self)

        # left side
        top_file_bar = QHBoxLayout()
        self.linetext_spcht_filepath = QLineEdit()
        self.linetext_spcht_filepath.setPlaceholderText(i18n['str_sdf_file_placeholder'])
        self.linetext_spcht_filepath.setReadOnly(True)
        self.btn_create_spcht = QPushButton(i18n['btn_create_spcht'])
        self.btn_load_spcht_file = QPushButton(i18n['btn_sdf_txt'])
        self.btn_load_spcht_retry = QPushButton(i18n['generic_retry'])
        self.btn_load_spcht_retry.setDisabled(True)
        top_file_bar.addWidget(self.linetext_spcht_filepath)
        top_file_bar.addWidget(self.btn_create_spcht)
        top_file_bar.addWidget(self.btn_load_spcht_file)
        top_file_bar.addWidget(self.btn_load_spcht_retry)

        bottom_file_bar = QHBoxLayout()
        self.str_testdata_filepath = QLineEdit()
        self.str_testdata_filepath.setPlaceholderText(i18n['str_jsonfile_placeholder'])
        self.str_testdata_filepath.setReadOnly(True)
        self.linetext_subject_prefix = QLineEdit()
        self.linetext_subject_prefix.setPlaceholderText(i18n['str_subject_placeholder'])
        self.linetext_subject_prefix.setReadOnly(True)
        self.linetext_subject_prefix.setMaximumWidth(250)
        self.btn_load_testdata_file = QPushButton(i18n['btn_testdata_txt'])
        self.btn_load_testdata_file.setToolTip(i18n['btn_testdata_tooltip'])
        self.btn_load_testdata_file.setDisabled(True)
        self.btn_load_testdata_retry = QPushButton(i18n['generic_retry'])
        self.btn_load_testdata_retry.setToolTip(i18n['btn_retry_tooltip'])
        self.btn_load_testdata_retry.setDisabled(True)
        bottom_file_bar.addWidget(self.str_testdata_filepath)
        bottom_file_bar.addWidget(self.linetext_subject_prefix)
        bottom_file_bar.addWidget(self.btn_load_testdata_file)
        bottom_file_bar.addWidget(self.btn_load_testdata_retry)

        # middle part - View 1
        center_layout = QHBoxLayout()

        control_bar_above_treeview = QGridLayout()
        control_bar_above_treeview.setMargin(0)
        self.btn_tree_expand = QPushButton(i18n['generic_expandall'])
        self.btn_tree_expand.setFlat(True)
        self.btn_tree_expand.setFixedHeight(15)
        self.btn_tree_collapse = QPushButton(i18n['generic_collapseall'])
        self.btn_tree_collapse.setFlat(True)
        self.btn_tree_collapse.setFixedHeight(15)
        self.treeview_main_spcht_data = QTreeView()
        self.spchttree_view_model = QStandardItemModel()
        self.spchttree_view_model.setHorizontalHeaderLabels(
            [i18n['generic_name'], i18n['generic_predicate'], i18n['generic_source'], i18n['generic_objects'], i18n['generic_info'], i18n['generic_comments']])
        self.treeview_main_spcht_data.setModel(self.spchttree_view_model)
        self.treeview_main_spcht_data.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.treeview_main_spcht_data.setUniformRowHeights(True)
        control_bar_above_treeview.addWidget(self.btn_tree_expand, 0, 0)
        control_bar_above_treeview.addWidget(self.btn_tree_collapse, 0, 1)
        control_bar_above_treeview.setColumnStretch(2, 1)
        control_bar_above_treeview.addWidget(self.treeview_main_spcht_data, 1, 0, 1, 3)

        label_fields = QLabel("Fields")
        self.lst_fields = QListView()
        self.lst_fields.setMaximumWidth(200)
        self.lst_fields_model = QStandardItemModel()
        self.lst_fields.setModel(self.lst_fields_model)
        fields = QVBoxLayout()
        fields.addWidget(label_fields)
        fields.addWidget(self.lst_fields)

        label_graphs = QLabel("Graphs")
        self.lst_graphs = QListView()
        self.lst_graphs.setMaximumWidth(300)
        self.lst_graphs_model = QStandardItemModel()
        self.lst_graphs.setModel(self.lst_graphs_model)
        graphs = QVBoxLayout()
        graphs.addWidget(label_graphs)
        graphs.addWidget(self.lst_graphs)

        center_layout.addLayout(control_bar_above_treeview)
        center_layout.addLayout(fields)
        center_layout.addLayout(graphs)

        # middle part - View 2
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(FIXEDFONT)

        # middle part - View 3
        self.txt_tabview = QTextEdit()
        self.txt_tabview.setReadOnly(True)
        self.txt_tabview.setFont(FIXEDFONT)
        self.tbl_tabview = QTableView()
        self.tbl_tabview.horizontalHeader().setStretchLastSection(True)
        self.tbl_tabview.horizontalHeader().setSectionsClickable(False)
        self.mdl_tbl_sparql = QStandardItemModel()
        self.mdl_tbl_sparql.setHorizontalHeaderLabels(["resource identifier", "property name", "property value"])
        self.tbl_tabview.setModel(self.mdl_tbl_sparql)
        self.tbl_tabview.setColumnWidth(0, 300)
        self.tbl_tabview.setColumnWidth(1, 300)

        tabView = QTabWidget()
        tabView.setTabShape(QTabWidget.Triangular)
        tabView.addTab(self.txt_tabview, "Text")
        tabView.addTab(self.tbl_tabview, "Table")


        # bottom
        self.bottomStack = QStackedWidget()
        self.bottomStack.setContentsMargins(0, 0, 0, 0)
        self.bottomStack.setMaximumHeight(20)
        self.btn_tristate = QPushButton()
        self.btn_tristate.setMaximumWidth(60)
        self.btn_tristate.setFlat(True)
        self.tristate = 0
        self.notifybar = QStatusBar()
        self.notifybar.setSizeGripEnabled(False)
        self.processBar = QProgressBar()
        bottombar = QHBoxLayout()
        bottombar.setContentsMargins(0, 0, 0, 0)
        bottombar.addWidget(self.btn_tristate)
        bottombar.addWidget(self.notifybar)
        randombarasWidget = QWidget()
        randombarasWidget.setLayout(bottombar)
        self.bottomStack.addWidget(randombarasWidget)
        self.bottomStack.addWidget(self.processBar)

        # * explorer layout
        self.explorer = QWidget()
        self.explore_main_vertical = QVBoxLayout(self.explorer)

        # ? top row explorer
        self.explorer_top_layout = QHBoxLayout()

        self.linetext_field_filter = QLineEdit(self.explorer)
        self.linetext_field_filter.setPlaceholderText(i18n['linetext_field_filter_placeholder'])
        # additional widgets here

        self.explorer_top_layout.addWidget(self.linetext_field_filter)
        self.explore_main_vertical.addLayout(self.explorer_top_layout)

        # ? central row
        self.explorer_center_layout = QHBoxLayout()

        self.explorer_toolbox = QToolBox(self.explorer)
        self.explorer_toolbox_page1 = QWidget()
        self.explorer_toolbox_page2 = QWidget()
        self.explorer_toolbox.addItem(self.explorer_toolbox_page1, i18n['toolbox_page1'])
        self.explorer_toolbox.addItem(self.explorer_toolbox_page2, i18n['toolbox_page2'])
        self.explorer_dictionary_treeview = QTreeView(self.explorer_toolbox_page1)
        self.explorer_marc_treeview = QTreeView(self.explorer_toolbox_page2)

        self.explorer_center_layout.addWidget(self.explorer_toolbox)
        self.explore_main_vertical.addLayout(self.explorer_center_layout)

        # ? bottom row
        self.explorer_bottom_layout = QHBoxLayout()

        self.explorer_left_horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.explorer_right_horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.explorer_leftleft_button = QPushButton("<<")
        self.explorer_left_button = QPushButton("<")
        self.explorer_rightright_button = QPushButton(">>")
        self.explorer_right_button = QPushButton(">")
        self.explorer_bottom_center_layout = QVBoxLayout()
        self.explorer_linetext_search = QLineEdit(self.explorer)
        self.explorer_center_search_button = QPushButton(i18n['find'])
        self.explorer_bottom_center_layout.addWidget(self.explorer_linetext_search)
        self.explorer_bottom_center_layout.addWidget(self.explorer_center_search_button)

        self.explorer_bottom_layout.addItem(self.explorer_left_horizontal_spacer)
        self.explorer_bottom_layout.addWidget(self.explorer_leftleft_button)
        self.explorer_bottom_layout.addWidget(self.explorer_left_button)
        self.explorer_bottom_layout.addLayout(self.explorer_bottom_center_layout)
        self.explorer_bottom_layout.addWidget(self.explorer_right_button)
        self.explorer_bottom_layout.addWidget(self.explorer_rightright_button)
        self.explorer_bottom_layout.addItem(self.explorer_right_horizontal_spacer)

        self.explore_main_vertical.addLayout(self.explorer_bottom_layout)

        # general layouting
        self.MainPageLayout = QStackedWidget()
        randomStackasWidget = QWidget()
        randomStackasWidget.setLayout(center_layout)
        self.MainPageLayout.addWidget(self.console)
        self.MainPageLayout.addWidget(randomStackasWidget)
        self.MainPageLayout.addWidget(tabView)
        self.MainPageLayout.addWidget(self.explorer)

        main_layout.addLayout(top_file_bar, 0, 0)
        main_layout.addWidget(self.MainPageLayout, 1, 0)
        main_layout.addLayout(bottom_file_bar, 2, 0)
        #main_layout.addLayout(bottombar, 3, 0)
        main_layout.addWidget(self.bottomStack, 3, 0)

        # * Event Binds
        self.btn_load_spcht_file.clicked.connect(self.btn_spcht_load_dialogue)
        self.btn_load_spcht_retry.clicked.connect(self.btn_spcht_load_retry)
        self.btn_tristate.clicked.connect(self.toogleTriState)
        self.btn_load_testdata_file.clicked.connect(self.btn_clk_loadtestdata)
        self.btn_load_testdata_retry.clicked.connect(self.btn_clk_loadtestdata_retry)
        self.btn_tree_expand.clicked.connect(self.treeview_main_spcht_data.expandAll)
        self.btn_tree_collapse.clicked.connect(self.treeview_main_spcht_data.collapseAll)
        self.toogleTriState(0)

        # various
        self.console.insertPlainText(time_log(f"Init done, program started"))
        self.console.insertPlainText(f"Working Directory: {os.getcwd()}")

    def btn_spcht_load_retry(self):
        self.load_spcht(self.linetext_spcht_filepath.displayText())

    def load_spcht(self, path_To_File):
        try:
            with open(path_To_File, "r") as file:
                testdict = json.load(file)
                status, output = SpchtUtility.schema_validation(testdict, schema="./SpchtSchema.json")
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
        toggleTexts = ["Console", "View", "Tests", "Explorer"]
        if isinstance(status, bool):  # connect calls as false
            if self.tristate == 3:
                self.tristate = 0
            else:
                self.tristate += 1
            self.MainPageLayout.setCurrentIndex(self.tristate)
        else:
            self.MainPageLayout.setCurrentIndex(status)
            self.tristate = self.MainPageLayout.currentIndex()
        self.btn_tristate.setText(toggleTexts[self.tristate])

    def btn_spcht_load_dialogue(self):
        path_To_File, file_type = QtWidgets.QFileDialog.getOpenFileName(self, "Open spcht descriptor file", "../", "Spcht Json File (*.spcht.json);;Json File (*.json);;Every file (*.*)")

        if not path_To_File :
            return None

        self.btn_load_spcht_retry.setDisabled(False)
        self.linetext_spcht_filepath.setText(path_To_File)
        self.load_spcht(path_To_File)

    def btn_clk_loadtestdata(self):
        path_To_File, type = QtWidgets.QFileDialog.getOpenFileName(self, "Open sample data", "../",
                                                                   "Json File (*.json);;Every file (*.*)")

        if path_To_File == "":
            return None

        graphtext = self.linetext_subject_prefix.displayText()
        graph, status = QtWidgets.QInputDialog.getText(self, "Insert Subject name",
                                                    "Insert non-identifier part of the subject that is supposed to be mapped onto",
                                                    text=graphtext)
        if status is False or graph.strip() == "":
            return None
        if self.btn_act_loadtestdata(path_To_File, graph):
            self.btn_load_testdata_retry.setDisabled(False)
            self.str_testdata_filepath.setText(path_To_File)
            self.linetext_subject_prefix.setText(graph)

    def btn_clk_loadtestdata_retry(self):
        self.load_spcht(self.linetext_spcht_filepath.displayText())
        self.btn_act_loadtestdata(self.str_testdata_filepath.displayText(), self.linetext_subject_prefix.displayText())
        # its probably bad style to directly use interface element text

    def btn_act_loadtestdata(self, filename, graph):
        debug_dict = {}  # TODO: loading of definitions
        basePath = Path(filename)
        descriPath = os.path.join(f"{basePath.parent}", f"{basePath.stem}.descri{basePath.suffix}")
        print(descriPath)
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
        try:
            with open(filename, "r") as file:
                thetestset = json.load(file)
        except FileNotFoundError:
            self.write_status("Loading of example Data file failed.")
            return False
        except json.JSONDecodeError as e:
            self.write_status(f"Example data contains json errors: {e}")
            self.console.insertPlainText(time_log(f"JSON Error in Example File: {str(e)}"))
            return False
        tbl_list = []
        text_list = []
        thetestset = handle_variants(thetestset)
        self.progressMode(True)
        self.processBar.setMaximum(len(thetestset))
        i = 0
        for entry in thetestset:
            i += 1
            self.processBar.setValue(i)
            try:
                temp = self.taube.process_data(entry, graph)
            except Exception as e:  # probably an AttributeError but i actually cant know, so we cast the WIDE net
                self.progressMode(False)
                self.write_status(f"SPCHT interpreting encountered an exception {e}")
                return False
            if isinstance(temp, list):
                text_list.append(
                "\n=== {} - {} ===\n".format(entry.get('id', "Unknown ID"), debug_dict.get(entry.get('id'), "Ohne Name")))
                for each in temp:
                    if each[3] == 0:
                        tbl_list.append((each[0], each[1], each[2]))
                        tmp_sparql = f"<{each[0]}> <{each[1]}> \"{each[2]}\" . \n"
                    else:  # "<{}> <{}> <{}> .\n".format(graph + ressource, node['graph'], facet))
                        tmp_sparql = f"<{each[0]}> <{each[1]}> <{each[2]}> . \n"
                        tbl_list.append((each[0], each[1], f"<{each[2]}>"))
                    text_list.append(tmp_sparql)
        # txt view
        self.txt_tabview.clear()
        for each in text_list:
            self.txt_tabview.insertPlainText(each)
        # table view
        if self.mdl_tbl_sparql.hasChildren():
            self.mdl_tbl_sparql.removeRows(0, self.mdl_tbl_sparql.rowCount())
        for each in tbl_list:
            col0 = QStandardItem(each[0])
            col1 = QStandardItem(each[1])
            col2 = QStandardItem(each[2])
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


if __name__ == "__main__":
    thisApp = QtWidgets.QApplication(sys.argv)
    thisApp.setWindowIcon(QIcon(':/icons/woodpecker.ico'))
    window = SpchtChecker()
    window.show()
    try:
        sys.exit(thisApp.exec_())
    except KeyboardInterrupt:
        sys.exit()
