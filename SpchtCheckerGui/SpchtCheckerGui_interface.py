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


from PySide2.QtGui import QStandardItemModel, QStandardItem, QFontDatabase, QIcon
from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtCore

import SpchtCheckerGui_i18n

# ! import language stuff
i18n = SpchtCheckerGui_i18n.Spcht_i18n("./GuiLanguage.json")


class SpchtMainWindow(object):

    def create_ui(self, MainWindow: QMainWindow):
        self.FIXEDFONT = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.FIXEDFONT.setPointSize(10)
        self.input_timer = QtCore.QTimer()
        self.input_timer.setSingleShot(True)

        # * Window Setup
        MainWindow.setBaseSize(1280, 720)
        MainWindow.setMinimumSize(720, 480)
        MainWindow.setWindowTitle(i18n['window_title'])
        MainWindow.setWindowFlags(QtCore.Qt.WindowMinimizeButtonHint & QtCore.Qt.WindowMaximizeButtonHint)

        checker_wrapper = QWidget()
        checker_layout = QGridLayout(checker_wrapper)

        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        # left side
        top_file_bar = QHBoxLayout()
        self.linetext_spcht_filepath = QLineEdit()
        self.linetext_spcht_filepath.setPlaceholderText(i18n['str_sdf_file_placeholder'])
        self.linetext_spcht_filepath.setReadOnly(True)
        # self.btn_create_spcht = QPushButton(i18n['btn_create_spcht'])
        self.btn_load_spcht_file = QPushButton(i18n['btn_sdf_txt'])
        self.btn_load_spcht_retry = QPushButton(i18n['generic_retry'])
        self.btn_load_spcht_retry.setDisabled(True)
        top_file_bar.addWidget(self.linetext_spcht_filepath)
        # top_file_bar.addWidget(self.btn_create_spcht)
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
            [i18n['generic_name'], i18n['generic_predicate'], i18n['generic_source'], i18n['generic_objects'],
             i18n['generic_info'], i18n['generic_comments']])
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
        self.console.setFont(self.FIXEDFONT)

        # middle part - View 3
        self.txt_tabview = QTextEdit()
        self.txt_tabview.setReadOnly(True)
        self.txt_tabview.setFont(self.FIXEDFONT)
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
        self.btn_change_main = QPushButton("Checker")
        self.btn_change_main.setMaximumWidth(60)
        self.btn_change_main.setFlat(True)
        self.notifybar = QStatusBar()
        self.notifybar.setSizeGripEnabled(False)
        self.processBar = QProgressBar()
        bottombar = QHBoxLayout()
        bottombar.setContentsMargins(0, 0, 0, 0)
        bottombar.addWidget(self.btn_tristate)
        bottombar.addWidget(self.btn_change_main)
        bottombar.addWidget(self.notifybar)
        randombarasWidget = QWidget()
        randombarasWidget.setLayout(bottombar)
        self.bottomStack.addWidget(randombarasWidget)
        self.bottomStack.addWidget(self.processBar)

        # * explorer layout
        self.create_explorer_layout()

        # general layouting
        self.MainPageLayout = QStackedWidget()
        randomStackasWidget = QWidget()
        randomStackasWidget.setLayout(center_layout)
        self.MainPageLayout.addWidget(self.console)
        self.MainPageLayout.addWidget(randomStackasWidget)
        self.MainPageLayout.addWidget(tabView)

        checker_layout.addLayout(top_file_bar, 0, 0)
        checker_layout.addWidget(self.MainPageLayout, 1, 0)
        checker_layout.addLayout(bottom_file_bar, 2, 0)
        # main_layout.addLayout(bottombar, 3, 0)
        checker_layout.addWidget(self.bottomStack, 3, 0)

        self.central_widget.addWidget(checker_wrapper)
        self.central_widget.addWidget(self.explorer)

    def create_explorer_layout(self):
        self.explorer = QWidget()
        self.explore_main_vertical = QVBoxLayout(self.explorer)

        # ? top row explorer
        self.explorer_top_layout = QHBoxLayout()

        self.explorer_field_filter = QLineEdit()
        self.explorer_field_filter.setPlaceholderText(i18n['linetext_field_filter_placeholder'])
        self.explorer_filter_behaviour = QCheckBox(i18n['check_blacklist_behaviour'])
        self.explorer_filter_behaviour.setChecked(True)
        self.explorer_field_filter.setText(
            "spelling, barcode, rvk_path, rvk_path_str_mv, topic_facet, author_facet, institution, spellingShingle")
        # additional widgets here

        self.explorer_top_layout.addWidget(self.explorer_field_filter)
        self.explorer_top_layout.addWidget(self.explorer_filter_behaviour)
        self.explore_main_vertical.addLayout(self.explorer_top_layout)

        # ? central row
        self.explorer_center_layout = QHBoxLayout()

        self.explorer_toolbox = QToolBox()
        self.explorer_toolbox.setMinimumWidth(800)
        self.explorer_tree_spcht_view = QTreeView()
        self.explorer_tree_spcht_view.setMaximumWidth(400)
        self.populate_spcht_view()
        self.explorer_spcht_result = QTextEdit()
        self.explorer_spcht_result.setMaximumWidth(400)
        ver_layout_19 = QVBoxLayout()
        ver_layout_19.addWidget(self.explorer_tree_spcht_view)
        ver_layout_19.addWidget(self.explorer_spcht_result)

        self.explorer_toolbox_page0 = QWidget()
        self.explorer_data_file_path = QLineEdit()
        self.explorer_data_file_path.setReadOnly(True)
        self.explorer_data_load_button = QPushButton(i18n['generic_load'])
        hor_layout_20 = QHBoxLayout(self.explorer_toolbox_page0)
        hor_layout_20.addWidget(self.explorer_data_file_path)
        hor_layout_20.addWidget(self.explorer_data_load_button)

        self.explorer_toolbox_page1 = QWidget()
        self.explorer_toolbox_page2 = QWidget()

        self.explorer_dictionary_treeview = QTreeView()
        hor_layout_21 = QHBoxLayout(self.explorer_toolbox_page1)
        hor_layout_21.addWidget(self.explorer_dictionary_treeview)

        self.explorer_marc_treeview = QTreeView()
        hor_layout_22 = QHBoxLayout(self.explorer_toolbox_page2)
        hor_layout_22.addWidget(self.explorer_marc_treeview)

        self.explorer_toolbox.addItem(self.explorer_toolbox_page0, i18n['toolbox_load_data'])
        self.explorer_toolbox.addItem(self.explorer_toolbox_page1, i18n['toolbox_page1'])
        self.explorer_toolbox.addItem(self.explorer_toolbox_page2, i18n['toolbox_page2'])

        self.explorer_center_layout.addWidget(self.explorer_toolbox)
        #self.explorer_center_layout.addWidget(self.explorer_tree_spcht_view)
        self.explorer_center_layout.addLayout(ver_layout_19)
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
        self.explorer_linetext_search = QLineEdit(parent=self.explorer)
        self.explorer_center_search_button = QPushButton(i18n['find'])
        self.explorer_bottom_center_layout.addWidget(self.explorer_linetext_search)
        self.explorer_bottom_center_layout.addWidget(self.explorer_center_search_button)
        SpchtMainWindow.set_max_size(25, 70,
                                     self.explorer_leftleft_button,
                                     self.explorer_right_button,
                                     self.explorer_left_button,
                                     self.explorer_rightright_button)
        SpchtMainWindow.set_max_size(200, 20,
                                     self.explorer_linetext_search,
                                     self.explorer_center_search_button)

        self.explorer_bottom_layout.addItem(self.explorer_left_horizontal_spacer)
        self.explorer_bottom_layout.addWidget(self.explorer_leftleft_button)
        self.explorer_bottom_layout.addWidget(self.explorer_left_button)
        self.explorer_bottom_layout.addLayout(self.explorer_bottom_center_layout)
        self.explorer_bottom_layout.addWidget(self.explorer_right_button)
        self.explorer_bottom_layout.addWidget(self.explorer_rightright_button)
        self.explorer_bottom_layout.addItem(self.explorer_right_horizontal_spacer)

        self.explore_main_vertical.addLayout(self.explorer_bottom_layout)

    def populate_spcht_view(self):
        self.spcht_tree_model = QStandardItemModel()
        key_list = ["field", "alternatives", "required", "predicate", "source", "match", "if_field", "if_value",
                    "if_condition", "append", "prepend", "cut", "replace", "insert_into", "insert_add_field", "mapping",
                    "mapping_settings", "joined_map", "joined_filed", "comment"]
        self.spcht_tree_model.setHorizontalHeaderLabels([i18n['generic_property'], i18n['generic_value']])
        top_node = QStandardItem("Name")
        top_node.setCheckable(True)
        top_node.setCheckState(QtCore.Qt.Checked)
        top_node.setEditable(False)
        self.spcht_tree_model.setItem(0, 0, top_node)
        for idx, each in enumerate(key_list):
            prop = QStandardItem(each)
            prop.setEditable(False)
            value = QStandardItem("")
            top_node.setChild(idx, 0, prop)
            top_node.setChild(idx, 1, value)

        test = QStandardItem("Test")
        self.explorer_tree_spcht_view.setModel(self.spcht_tree_model)
        idx = self.spcht_tree_model.index(0, 0)
        self.explorer_tree_spcht_view.expand(idx)

    @staticmethod
    def set_max_size(width=0, height=0, *args):
        for each in args:
            if isinstance(each, (QPushButton, QLineEdit)):
                if width:
                    each.setMaximumWidth(width)
                if height:
                    each.setMaximumHeight(height)

