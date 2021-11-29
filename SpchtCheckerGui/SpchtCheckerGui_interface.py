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
import sys
import os

from PySide2.QtGui import QStandardItemModel, QStandardItem, QFontDatabase, QIcon, QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument, QPalette
from PySide2.QtWidgets import *
from PySide2 import QtCore, QtWidgets

import SpchtCheckerGui_i18n
import SpchtConstants


def resource_path(relative_path: str) -> str:
    """
    Returns the path to a ressource, normally just echos, but when this is packed with PyInstall there wont be any
    additional files, therefore this is the middleware to access packed data
    :param relative_path: relative path to a file
    :return: path to the file
    :rtype: str
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# ! import language stuff
i18n = SpchtCheckerGui_i18n.Spcht_i18n(resource_path("./GuiLanguage.json"), language='en')



class SpchtMainWindow(object):

    def create_ui(self, MainWindow: QMainWindow):
        self.FIXEDFONT = self.FIXEDFONT = tryForFont(9)
        self.input_timer = QtCore.QTimer()
        self.input_timer.setSingleShot(True)
        self.spcht_timer = QtCore.QTimer(SingleShot=True)

        self.policy_minimum_expanding = QSizePolicy()
        self.policy_minimum_expanding.Policy = QSizePolicy.MinimumExpanding
        self.policy_expanding = QSizePolicy()
        self.policy_expanding.Policy = QSizePolicy.Expanding
        # * Window Setup
        MainWindow.setBaseSize(1280, 720)
        MainWindow.setMinimumSize(1440, 960)
        MainWindow.setWindowTitle(i18n['window_title'])
        MainWindow.setWindowFlags(QtCore.Qt.WindowMinimizeButtonHint & QtCore.Qt.WindowMaximizeButtonHint)

        checker_wrapper = QWidget()
        checker_layout = QGridLayout(checker_wrapper)

        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        # left side
        top_file_bar = QHBoxLayout()
        self.linetext_spcht_filepath = QLineEdit(PlaceholderText=i18n['str_sdf_file_placeholder'], ReadOnly=True)
        # self.btn_create_spcht = QPushButton(i18n['btn_create_spcht'])
        self.btn_load_spcht_file = QPushButton(i18n['btn_sdf_txt'])
        self.btn_load_spcht_retry = QPushButton(i18n['generic_retry'], Disabled=True)
        top_file_bar.addWidget(self.linetext_spcht_filepath)
        # top_file_bar.addWidget(self.btn_create_spcht)
        top_file_bar.addWidget(self.btn_load_spcht_file)
        top_file_bar.addWidget(self.btn_load_spcht_retry)

        bottom_file_bar = QHBoxLayout()
        self.str_testdata_filepath = QLineEdit(PlaceholderText=i18n['str_jsonfile_placeholder'], ReadOnly=True)
        self.linetext_subject_prefix = QLineEdit(PlaceholderText=i18n['str_subject_placeholder'], ReadOnly=True, MaximumWidth=250)
        self.btn_load_testdata_file = QPushButton(i18n['btn_testdata_txt'], ToolTip=i18n['btn_testdata_tooltip'], Disabled=True)
        self.btn_load_testdata_retry = QPushButton(i18n['generic_retry'], ToolTip=i18n['btn_retry_tooltip'], Disabled=True)
        bottom_file_bar.addWidget(self.str_testdata_filepath)
        bottom_file_bar.addWidget(self.linetext_subject_prefix)
        bottom_file_bar.addWidget(self.btn_load_testdata_file)
        bottom_file_bar.addWidget(self.btn_load_testdata_retry)

        # middle part - View 1
        center_layout = QHBoxLayout()

        control_bar_above_treeview = QGridLayout(Margin=0)
        self.btn_tree_expand = QPushButton(i18n['generic_expandall'], Flat=True, FixedHeight=15)
        self.btn_tree_collapse = QPushButton(i18n['generic_collapseall'], Flat=True, FixedHeight=15)
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
        self.lst_fields = QListView(MaximumWidth=200)
        self.lst_fields_model = QStandardItemModel()
        self.lst_fields.setModel(self.lst_fields_model)
        fields = QVBoxLayout()
        fields.addWidget(label_fields)
        fields.addWidget(self.lst_fields)

        label_graphs = QLabel("Graphs")
        self.lst_graphs = QListView(MaximumWidth=300)
        self.lst_graphs_model = QStandardItemModel()
        self.lst_graphs.setModel(self.lst_graphs_model)
        graphs = QVBoxLayout()
        graphs.addWidget(label_graphs)
        graphs.addWidget(self.lst_graphs)

        center_layout.addLayout(control_bar_above_treeview)
        center_layout.addLayout(fields)
        center_layout.addLayout(graphs)

        # middle part - View 2
        self.console = QTextEdit(ReadOnly=True, Font=self.FIXEDFONT)

        # middle part - View 3
        self.txt_tabview = QTextEdit(ReadOnly=True)
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
        self.btn_tristate = QPushButton(SizePolicy=self.policy_minimum_expanding, Flat=True, MinimumWidth=80)
        self.btn_tristate.setStyleSheet("text-align: left;")  # crude hack
        self.tristate = 0
        self.btn_change_main = QPushButton(i18n['gui_builder'], MaximumWidth=200, Flat=True)
        self.notifybar = QStatusBar(SizeGripEnabled=False)
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
        self.field_completer = QCompleter()
        self.field_completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)

        self.explorer = QWidget()
        self.explore_main_vertical = QVBoxLayout(self.explorer)

        # ? right row
        self.explorer_center_layout = QHBoxLayout()

        # ? navigation of compiled data
        self.explorer_middle_nav_layout = QHBoxLayout()
        self.explorer_mid_nav_dummy = QWidget()
        self.explorer_mid_nav_dummy.setMaximumWidth(400)
        self.explorer_mid_nav_dummy.setLayout(self.explorer_middle_nav_layout)
        #self.explorer_left_horizontal_spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        #self.explorer_right_horizontal_spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.explorer_leftleft_button = QPushButton("<<")
        self.explorer_left_button = QPushButton("<")
        self.explorer_rightright_button = QPushButton(">>")
        self.explorer_right_button = QPushButton(">")
        self.explorer_bottom_center_layout = QVBoxLayout()
        self.explorer_middle_nav_layout.setContentsMargins(0, 0, 0, 0)
        self.explorer_linetext_search = QLineEdit(parent=self.explorer, Alignment=QtCore.Qt.AlignCenter)
        self.explorer_center_search_button = QPushButton(i18n['find'])
        self.explorer_bottom_center_layout.addWidget(self.explorer_linetext_search)
        self.explorer_bottom_center_layout.addWidget(self.explorer_center_search_button)
        SpchtMainWindow.massSetProperty(self.explorer_leftleft_button,
                                        self.explorer_right_button,
                                        self.explorer_left_button,
                                        self.explorer_rightright_button,
                                        maximumWidth=75,
                                        minimumSize=(25, 70))
        SpchtMainWindow.massSetProperty(self.explorer_linetext_search,
                                        self.explorer_center_search_button,
                                        maximumWidth=400,
                                        minimumSize=(200, 30))
        self.explorer_linetext_search.setSizePolicy(self.policy_minimum_expanding)

        #self.explorer_middle_nav_layout.addItem(self.explorer_left_horizontal_spacer)
        #self.explorer_middle_nav_layout.addStretch()
        self.explorer_middle_nav_layout.addWidget(self.explorer_leftleft_button)
        self.explorer_middle_nav_layout.addWidget(self.explorer_left_button)
        self.explorer_middle_nav_layout.addLayout(self.explorer_bottom_center_layout)
        self.explorer_middle_nav_layout.addWidget(self.explorer_right_button)
        self.explorer_middle_nav_layout.addWidget(self.explorer_rightright_button)
        #self.explorer_middle_nav_layout.addStretch()
        #self.explorer_middle_nav_layout.addItem(self.explorer_right_horizontal_spacer)

        # self.explore_main_vertical.addLayout(self.explorer_bottom_layout)

        # ? main tool box view
        self.explorer_toolbox = QToolBox()
        self.explorer_toolbox.setMinimumWidth(800)
        self.explorer_filtered_data = QTableWidget()
        self.explorer_spcht_result = QTextEdit()
        SpchtMainWindow.massSetProperty(self.explorer_spcht_result,
                                        self.explorer_filtered_data,
                                        maximumWidth=400,
                                        minimumWidth=200)
        ver_layout_19 = QVBoxLayout()
        ver_layout_19.addWidget(self.explorer_filtered_data)
        #ver_layout_19.addLayout(self.explorer_middle_nav_layout)
        ver_layout_19.addWidget(self.explorer_mid_nav_dummy)
        ver_layout_19.addWidget(self.explorer_spcht_result)

        self.explorer_toolbox_page0 = QWidget()
        # ? filter bar
        self.explorer_top_layout = QHBoxLayout()

        self.explorer_field_filter = QLineEdit()
        self.explorer_field_filter.setPlaceholderText(i18n['linetext_field_filter_placeholder'])
        self.explorer_filter_behaviour = QCheckBox(i18n['check_blacklist_behaviour'], Checked=True)
        self.explorer_field_filter.setText(
            "spelling, barcode, rvk_path, rvk_path_str_mv, topic_facet, author_facet, institution, spellingShingle")
        # additional widgets here

        self.explorer_top_layout.addWidget(self.explorer_field_filter)
        self.explorer_top_layout.addWidget(self.explorer_filter_behaviour)
        # self.explore_main_vertical.addLayout(self.explorer_top_layout)
        self.explorer_data_file_path = QLineEdit(ReadOnly=True)
        self.explorer_data_load_button = QPushButton(i18n['generic_load'])
        ver_layout_18 = QVBoxLayout(self.explorer_toolbox_page0)
        hor_layout_20 = QHBoxLayout()
        hor_layout_20.addWidget(self.explorer_data_file_path)
        hor_layout_20.addWidget(self.explorer_data_load_button)
        hor_layout_21 = QHBoxLayout()
        self.explorer_dictionary_treeview = QTreeView()
        hor_layout_21.addWidget(self.explorer_dictionary_treeview)
        ver_layout_18.addLayout(self.explorer_top_layout)
        ver_layout_18.addLayout(hor_layout_20)
        ver_layout_18.addLayout(hor_layout_21)

        self.explorer_toolbox_page1 = QWidget()
        ver_layout_23 = QVBoxLayout(self.explorer_toolbox_page1)
        hor_layour_22 = QHBoxLayout()
        self.explorer_node_add_btn = QPushButton(i18n['generic_add'], FixedWidth=150)
        self.explorer_node_create_btn = QPushButton(i18n['generic_new'], FixedWidth=150)
        self.explorer_node_import_btn = QPushButton(i18n['generic_import'], FixedWidth=150)
        self.explorer_node_export_btn = QPushButton(i18n['generic_export'], FixedWidth=150)
        self.explorer_node_load_btn = QPushButton(i18n['generic_load'], FixedWidth=150)
        self.explorer_node_save_btn = QPushButton(i18n['generic_save'], FixedWidth=150)
        self.explorer_node_compile_btn = QPushButton(i18n['generic_compile'], FixedWidth=150)
        self.mthSpchtBuilderBtnStatus(0)
        self.explorer_node_spcht_filepath = QLabel("", sizePolicy=self.policy_expanding, MaximumWidth=9999)
        hor_layour_22.addWidget(self.explorer_node_add_btn)
        hor_layour_22.addWidget(self.explorer_node_spcht_filepath)
        #hor_layour_22.addStretch(0)
        hor_layour_22.addWidget(self.explorer_node_import_btn)
        hor_layour_22.addWidget(self.explorer_node_export_btn)
        #hor_layour_22.addWidget(self.explorer_node_compile_btn)
        hor_layour_23 = QHBoxLayout()
        hor_layour_23.addWidget(self.explorer_node_create_btn)
        hor_layour_23.addStretch(255)
        hor_layour_23.addWidget(self.explorer_node_load_btn)
        hor_layour_23.addWidget(self.explorer_node_save_btn)
        hor_layour_23.addWidget(self.explorer_node_compile_btn)

        self.explorer_node_treeview = QTreeView()
        #self.explorer_node_treeview.setDragDropMode(QAbstractItemView.InternalMove)
        ver_layout_23.addWidget(self.explorer_node_treeview, 1)
        ver_layout_23.addLayout(hor_layour_22)
        ver_layout_23.addLayout(hor_layour_23)

        self.explorer_tabview = QTabWidget()
        self.explorer_tabview.setTabShape(QTabWidget.Rounded)
        # ! Tab Widgets
        # * general Tab
        self.exp_tab_general = QWidget()
        exp_tab_form_general = QFormLayout(self.exp_tab_general)

        # line 1
        self.exp_tab_node_name = QLineEdit(PlaceholderText=i18n['node_name_placeholder'])
        exp_tab_form_general.addRow(i18n['node_name'], self.exp_tab_node_name)
        # line 1
        self.exp_tab_node_field = QLineEdit(PlaceholderText=i18n['node_field_placeholder'], Completer=self.field_completer)
        exp_tab_form_general.addRow(i18n['node_field'], self.exp_tab_node_field)
        # line 1
        self.exp_tab_node_source = QComboBox(placeholderText=i18n['node_source_placeholder'])
        self.exp_tab_node_source.addItems(SpchtConstants.SOURCES)
        exp_tab_form_general.addRow(i18n['node_source'], self.exp_tab_node_source)
        # line 2
        self.exp_tab_node_mandatory = QCheckBox()
        exp_tab_form_general.addRow(i18n['node_mandatory'], self.exp_tab_node_mandatory)
        # line 3
        self.exp_tab_node_uri = QCheckBox()
        exp_tab_form_general.addRow(i18n['node_uri'], self.exp_tab_node_uri)
        # line 4
        self.exp_tab_node_tag = QLineEdit(PlaceholderText=i18n['node_tag_placeholder'])
        exp_tab_form_general.addRow(i18n['node_tag'], self.exp_tab_node_tag)
        #line 5
        self.exp_tab_node_predicate = QLineEdit(PlaceholderText=i18n['node_predicate_placeholder'])
        exp_tab_form_general.addRow(i18n['node_predicate'], self.exp_tab_node_predicate)
        #line 6
        self.exp_tab_node_comment = QTextEdit()
        exp_tab_form_general.addRow(i18n['node_comment'], self.exp_tab_node_comment)

        # * simple text transformation
        self.exp_tab_simpletext = QWidget()
        exp_tab_form_simpletext = QFormLayout(self.exp_tab_simpletext)
        # line 1
        self.exp_tab_node_prepend = QLineEdit(PlaceholderText=i18n['node_prepend_placeholder'])
        exp_tab_form_simpletext.addRow(i18n['node_prepend'], self.exp_tab_node_prepend)
        # line 2
        self.exp_tab_node_append = QLineEdit(PlaceholderText=i18n['node_append_placeholder'])
        exp_tab_form_simpletext.addRow(i18n['node_append'], self.exp_tab_node_append)
        # line 3
        self.exp_tab_node_cut = QLineEdit(PlaceholderText=i18n['node_cut_placeholder'])
        exp_tab_form_simpletext.addRow(i18n['node_cut'], self.exp_tab_node_cut)
        # line 4
        self.exp_tab_node_replace = QLineEdit(PlaceholderText=i18n['node_replace_placeholder'])
        exp_tab_form_simpletext.addRow(i18n['node_replace'], self.exp_tab_node_replace)
        # line 4
        self.exp_tab_node_match = QLineEdit(PlaceholderText=i18n['node_match_placeholder'])
        exp_tab_form_simpletext.addRow(i18n['node_match'], self.exp_tab_node_match)

        # * if tab
        self.exp_tab_if = QWidget()
        exp_tab_form_if = QFormLayout(self.exp_tab_if)
        # line 1
        self.exp_tab_node_if_field = QLineEdit(PlaceholderText=i18n['node_if_field'], Completer=self.field_completer)
        exp_tab_form_if.addRow(i18n['node_if_field'], self.exp_tab_node_if_field)
        # line 2
        self.exp_tab_node_if_condition = QComboBox(placeholderText=i18n['node_if_comparator'])
        self.exp_tab_node_if_condition.addItems(set([x for x in SpchtConstants.SPCHT_BOOL_OPS.values()]))
        self.exp_tab_node_if_condition.setCurrentIndex(0)
        exp_tab_form_if.addRow(i18n['node_if_condition'], self.exp_tab_node_if_condition)
        # line 3
        fleeting = QFormLayout()
        floating = QHBoxLayout()
        self.exp_tab_node_if_value = QLineEdit(PlaceholderText=i18n['node_if_value'])
        self.exp_tab_node_if_many_values = QLineEdit(PlaceholderText=i18n['node_if_many_values'], ReadOnly=True, Disabled=True)
        self.exp_tab_node_if_enter_values = QPushButton(i18n['node_if_enter_btn'], Disabled=True)
        floating.addWidget(self.exp_tab_node_if_enter_values)
        floating.addWidget(self.exp_tab_node_if_many_values, stretch=255)
        self.exp_tab_node_if_decider1 = QRadioButton("Single Value", checked=True)#alignment=QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter
        self.exp_tab_node_if_decider2 = QRadioButton("Multi Value")
        fleeting.addRow(self.exp_tab_node_if_decider1, self.exp_tab_node_if_value)
        fleeting.addRow(self.exp_tab_node_if_decider2, floating)
        exp_tab_form_if.addRow(QLabel(i18n['node_if_value'], Alignment=QtCore.Qt.AlignTop), fleeting)
        # line 4

        # * mapping tab
        self.exp_tab_mapping = QWidget()
        exp_tab_form_mapping = QGridLayout(self.exp_tab_mapping)
        exp_tab_form_mapping.setColumnStretch(2, 255)
        exp_tab_form_mapping.setAlignment(QtCore.Qt.AlignTop)
        # line 1
        exp_tabl_label41 = QLabel(i18n['node_mapping'])
        self.exp_tab_node_mapping_btn = QPushButton(i18n['node_details'])
        self.exp_tab_node_mapping_preview = QLabel("")
        exp_tab_form_mapping.addWidget(exp_tabl_label41, 0, 0)
        exp_tab_form_mapping.addWidget(self.exp_tab_node_mapping_btn, 0, 1)
        exp_tab_form_mapping.addWidget(self.exp_tab_node_mapping_preview, 0, 2)
        # line 2
        exp_tab_label_42 = QLabel(i18n['node_mapping_ref'])
        self.exp_tab_node_mapping_ref_btn = QPushButton(i18n['node_mapping_ref_load'])
        self.exp_tab_node_mapping_ref_path = QLineEdit("", ReadOnly=True)
        exp_tab_form_mapping.addWidget(exp_tab_label_42, 1, 0)
        exp_tab_form_mapping.addWidget(self.exp_tab_node_mapping_ref_btn, 1, 1)
        exp_tab_form_mapping.addWidget(self.exp_tab_node_mapping_ref_path, 1, 2)
        # line 2
        exp_tab_label_43 = QLabel(i18n['node_mapping_settings'])
        exp_tab_form_43 = QFormLayout()
        exp_tab_form_mapping.addWidget(exp_tab_label_43, 2, 0)
        exp_tab_form_mapping.itemAtPosition(2, 0).setAlignment(QtCore.Qt.AlignTop)
        exp_tab_form_mapping.addLayout(exp_tab_form_43, 2, 1, 1, 2)
        label_431 = QLabel(i18n['node_mapping_default'])
        label_432 = QLabel(i18n['node_mapping_inherit'])
        label_433 = QLabel(i18n['node_mapping_casesens'])
        label_434 = QLabel(i18n['node_mapping_regex'])
        self.exp_tab_mapping_default = QLineEdit(PlaceholderText=i18n['node_mapping_setting_default_placeholder'])
        self.exp_tab_mapping_inherit = QCheckBox()
        self.exp_tab_mapping_casesens = QCheckBox()
        self.exp_tab_mapping_regex = QCheckBox()
        exp_tab_form_43.addRow(label_431, self.exp_tab_mapping_default)
        exp_tab_form_43.addRow(label_432, self.exp_tab_mapping_inherit)
        exp_tab_form_43.addRow(label_433, self.exp_tab_mapping_casesens)
        exp_tab_form_43.addRow(label_434, self.exp_tab_mapping_regex)
        # line X + 1
        exp_tab_form_mapping.setRowStretch(3, 255)
        SpchtMainWindow.massSetProperty(self.exp_tab_node_mapping_ref_btn,
                                        self.exp_tab_node_mapping_btn,
                                        maximumWidth=200)

        # * Inheritance Tab
        self.exp_tab_inheritance = QWidget()
        exp_tab_form_inheritance = QFormLayout(self.exp_tab_inheritance)
        self.exp_tab_node_subdata = QLineEdit(PlaceholderText=i18n['node_subdata_placeholder'])
        self.exp_tab_node_subnode = QLineEdit(PlaceholderText=i18n['node_subnode_placeholder'])
        self.exp_tab_node_subnode_of = QComboBox(PlaceholderText=i18n['node_subnode_of_placeholder'], ToolTip=i18n['parent_note'])
        self.exp_tab_node_subdata_of = QComboBox(PlaceholderText=i18n['node_subdata_of_placeholder'])
        self.exp_tab_node_fallback = QComboBox(PlaceholderText=i18n['node_subfallback_placeholder'])
        exp_tab_form_inheritance.addRow(i18n['node_subdata'], self.exp_tab_node_subdata)
        exp_tab_form_inheritance.addRow(i18n['node_subdata_of'], self.exp_tab_node_subdata_of)
        exp_tab_form_inheritance.addRow(i18n['node_subnode'], self.exp_tab_node_subnode)
        exp_tab_form_inheritance.addRow(i18n['node_subnode_of'], self.exp_tab_node_subnode_of)
        exp_tab_form_inheritance.addRow(QLabel(""))
        exp_tab_form_inheritance.addRow(i18n['node_fallback'], self.exp_tab_node_fallback)

        self.tab_node_insert_add_fields = QLineEdit()

        # * Michelangelo Tab (i just discovered i cannot write 'miscellaneous' without googling)
        self.exp_tab_misc = QWidget()
        exp_tab_form_various = QFormLayout(self.exp_tab_misc)
        # line 1
        self.exp_tab_node_display_spcht = QPushButton(i18n['debug_spcht_json'])
        self.exp_tab_node_display_computed = QPushButton(i18n['debug_computed_json'])
        self.exp_tab_node_save_node = QPushButton("Save changes")
        self.exp_tab_node_testlock = QPushButton("Lock Up")
        exp_tab_form_various.addRow(i18n['debug_node_spcht'], self.exp_tab_node_display_spcht)
        exp_tab_form_various.addRow(i18n['debug_node_computed'], self.exp_tab_node_display_computed)
        exp_tab_form_various.addRow(i18n['debug_node_save'], self.exp_tab_node_save_node)
        exp_tab_form_various.addRow(i18n['debug_node_lock'], self.exp_tab_node_testlock)

        # bottom status line
        hor_layout_100 = QHBoxLayout()
        self.explorer_switch_checker = QPushButton(i18n['gui_checker'], MaximumWidth=150, Flat=True)
        self.explorer_status_bar = QLabel()
        hor_layout_100.addWidget(self.explorer_switch_checker)
        hor_layout_100.addWidget(self.explorer_status_bar)

        # ! End of Tab Widgets, adding content
        self.explorer_tabview.addTab(self.exp_tab_general, i18n['tab_general'])
        self.explorer_tabview.addTab(self.exp_tab_simpletext, i18n['tab_simpletext'])
        self.explorer_tabview.addTab(self.exp_tab_if, i18n['tab_if'])
        self.explorer_tabview.addTab(self.exp_tab_mapping, i18n['tab_mapping'])
        self.explorer_tabview.addTab(self.exp_tab_inheritance, i18n['tab_inheritance'])
        self.explorer_tabview.addTab(self.exp_tab_misc, i18n['tab_misc'])

        self.explorer_toolbox_page2 = QWidget(self.explorer_tabview)

        self.explorer_toolbox.addItem(self.explorer_toolbox_page0, i18n['builder_toolbox_load_data'])
        self.explorer_toolbox.addItem(self.explorer_toolbox_page1, i18n['builder_toolbox_node_overview'])
        self.explorer_toolbox.addItem(self.explorer_tabview, i18n['builder_toolbox_main_builder'])

        self.explorer_center_layout.addWidget(self.explorer_toolbox)
        #self.explorer_center_layout.addWidget(self.explorer_tree_spcht_view)
        self.explorer_center_layout.addLayout(ver_layout_19)
        self.explore_main_vertical.addLayout(self.explorer_center_layout)
        self.explore_main_vertical.addLayout(hor_layout_100)

    @staticmethod
    def set_max_size(width=0, height=0, *args):
        for each in args:
            if isinstance(each, (QPushButton, QLineEdit)):
                if width:
                    each.setMaximumWidth(width)
                if height:
                    each.setMaximumHeight(height)

    @staticmethod
    def massSetProperty(*widgets, **properties):
        """
        Sets properties for all widgets to the same, currently supports:

        * QPushButton
        * QLineEdit
        * QTableWidget
        * QTextEdit

        And Properties:

        * maximumWidth
        * maximumHeight
        * minimumHeight
        * miniumWidth
        * sizePolicy
        * alignment
        * disabled (will always set True, Parameter doesnt matter)
        * enabled (will always set True)
        :param widgets: A QT Widget
        :type widgets: QPushButton or QLineEdit
        :param properties: selected properties
        :type properties: int or QSizePolicy or bool or tuple
        :return: nothing
        :rtype: None
        """
        for each in widgets:
            if isinstance(each, (QPushButton, QLineEdit, QTableWidget, QTextEdit)):
                if 'maximumHeight' in properties:
                    each.setMaximumHeight(properties['maximumHeight'])
                if 'maximumWidth' in properties:
                    each.setMaximumWidth(properties['maximumWidth'])
                if 'maximumSize' in properties:
                    each.setMaximumSize(*properties['maximumSize'])
                if 'minimumHeight' in properties:
                    each.setMinimumHeight(properties['minimumHeight'])
                if 'minimumWidth' in properties:
                    each.setMinimumWidth(properties['minimumWidth'])
                if 'minimumSize' in properties:
                    each.setMinimumSize(*properties['minimumSize'])
                if 'fixedHeight' in properties:
                    each.setFixedHeight(properties['fixedHeight'])
                if 'fixedWidth' in properties:
                    each.setFixedWidth(properties['FixedWidth'])
                if 'fixedSize' in properties:
                    each.setFixedSize(*properties['fixedSize'])
                if 'sizePolicy' in properties:
                    each.setSizePolicy(properties['sizePolicy'])
                if 'alignment' in properties:
                    each.setAlignment(properties['alignment'])
                if 'disabled' in properties:
                    each.setDisabled(properties['disabled'])
                if 'enabled' in properties:
                    each.setEnabled(properties['enabled'])


class ListDialogue(QDialog):
    def __init__(self, title:str, main_message:str, headers=[],init_data=None, parent=None):
        #ListDialogue.result()
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)

        self.layout = QVBoxLayout()
        top_mesage = QLabel(main_message)
        self.table = QTableWidget()
        self.addBtn = QPushButton(i18n['insert_before'], icon=QIcon.fromTheme('insert-image'))
        self.deleteBtn = QPushButton(i18n['generic_delete'], icon=QIcon.fromTheme('delete'))
        btn_line = QHBoxLayout()
        btn_line.addWidget(self.addBtn)
        btn_line.addWidget(self.deleteBtn)
        self.layout.addWidget(top_mesage)
        self.layout.addWidget(self.table)
        self.layout.addLayout(btn_line)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        # * setup table
        self.tablemodel = QStandardItemModel()

        if not headers:
            if init_data and isinstance(init_data, dict):
                dict_len = 2
                for value in init_data.values():
                    if isinstance(value, list):
                        if temp := len(value) > dict_len:
                            dict_len = temp
                self.table.setColumnCount(dict_len)
            else:
                self.table.setColumnCount(1)
                self.table.setHorizontalHeaderLabels([i18n['value']])
        else:
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

        if init_data:
            if isinstance(init_data, list):
                self.table.setRowCount(len(init_data)+1)
                for i, each in enumerate(init_data):
                    self.table.setItem(i, 0, QTableWidgetItem(each))
            if isinstance(init_data, dict):
                self.table.setRowCount(len(init_data.keys()) + 1)
                for i, (key, value) in enumerate(init_data.items()):
                    self.table.setItem(i, 0, QTableWidgetItem(str(key)))
                    if isinstance(value, list):
                        for j, each in enumerate(value):
                            self.table.setItem(i, j+1, QTableWidgetItem(str(each)))
                    else:
                        self.table.setItem(i, 1, QTableWidgetItem(str(value)))
                self.table.resizeColumnToContents(0)
        else:
            self.table.setRowCount(1)

        self.table.horizontalHeader().setStretchLastSection(True)

        # ! final event setup:
        self.deleteBtn.clicked.connect(self.deleteCurrentRow)
        self.addBtn.clicked.connect(self.insertCurrentRow)
        self.table.itemChanged.connect(self.dataChange)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def deleteCurrentRow(self):
        # https://stackoverflow.com/a/50427744
        rows = set()
        for index in self.table.selectedIndexes():
            rows.add(index.row())

        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)

    def insertCurrentRow(self):
        rows = set()
        for index in self.table.selectedIndexes():
            rows.add(index.row())
        lastRow = 0  # i have the feeling that this is not the most optimal way
        for row in sorted(rows):
            lastRow = row
        self.table.insertRow(lastRow)

    def dataChange(self):
        # adds empty lines if none are present after editing
        model = self.table.model()
        is_empty = False
        for row in range(self.table.rowCount()):
            row_filled = False
            for column in range(self.table.columnCount()):
                cell_data = self.table.item(row, column)
                if cell_data and str(cell_data.text()).strip() != "":
                    row_filled = True
                    break
            if not row_filled:  # at least one empty line
                is_empty = True
                break

        if not is_empty:
            self.table.setRowCount(self.table.rowCount()+1)

    def getList(self):
        model = self.table.model()
        data = []
        for row in range(model.rowCount()):
            cell_data = model.data(model.index(row, 0))
            if cell_data:  # for some reasons Python 3.8 cannot combine those with an and, weird
                if (content := str(cell_data).strip()) != "":
                    data.append(content)
        return data

    def getDictionary(self):
        temp_model = self.table.model()
        data = {}
        for row in range(temp_model.rowCount()):
            key = temp_model.data(temp_model.index(row, 0))
            if key:
                values = []
                for column in range(1, temp_model.columnCount()):
                    values.append(temp_model.data(temp_model.index(row, column)))
                if len(values) == 1:
                    values = values[0]
                data[key] = values
        return data

    def getData(self):
        if self.table.columnCount() == 1:
            return self.getList()
        else:
            return self.getDictionary()


class JsonDialogue(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.FIXEDFONT = tryForFont(10)
        self.setWindowTitle(i18n['json_dia_title'])
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)
        self.resize(800, 600)
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.editor = QPlainTextEdit(Font=self.FIXEDFONT)  # QTextEdit(Font=self.FIXEDFONT)
        editor_style = QTextCharFormat()
        bla = self.editor.palette()
        bla.setColor(QPalette.Window, QColor.fromRgb(251, 241, 199))
        bla.setColor(QPalette.WindowText, QColor.fromRgb(60, 131, 54))
        self.editor.setPalette(bla)
        highlight = JsonHighlighter(self.editor.document())

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.editor)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        if isinstance(data, str):
            self.editor.setPlainText(data)
        elif isinstance(data, (list, dict)):
            self.editor.setPlainText(json.dumps(data, indent=3))

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def getContent(self):
        return self.editor.toPlainText()


class FernmeldeAmt(QtCore.QObject):
    up = QtCore.Signal()
    down = QtCore.Signal()
    check = QtCore.Signal()
    uncheck = QtCore.Signal()


class MoveUpDownWidget(QWidget):
    def __init__(self, label, parent=None):
        super(MoveUpDownWidget, self).__init__()
        self.c = FernmeldeAmt()
        self.check = QCheckBox(label)
        self.up = QPushButton("↑")
        self.down = QPushButton("↓")
        SpchtMainWindow.massSetProperty(self.up, self.down, maximumWidth=30, maximumHeight=20)

        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(7, 0, 7, 0)
        layout.addWidget(self.check)
        layout.addSpacing(1)
        layout.addWidget(self.up)
        layout.addWidget(self.down)
        self.setLayout(layout)
        self.down.clicked.connect(self.downE)
        self.up.clicked.connect(self.upE)

    def downE(self, event):
        self.c.down.emit()

    def upE(self, event):
        self.c.up.emit()


class JsonHighlighter(QSyntaxHighlighter):
    braces = ['\{', '\}', '\(', '\)', '\[', '\]']
    bools = ["TRUE", "FALSE", "True", "False", "true", "false"]
    colons = ["\:", "\,"]

    def __init__(self, parent: QTextDocument, lexer=None):
        super(JsonHighlighter, self).__init__(parent)
        self.colors = {}
        self.colorSchema()
        self.highlightingRules = []

        qSTYLES = {
            'bools': self.qformat(214, 93, 14, style='bold'),
            'braces': self.qformat(124, 111, 100),
            'string': self.qformat(152, 151, 26),
            'number': self.qformat(177, 98, 134, style="bold"),
            'colons': self.qformat(69, 133, 136, style="bold")
        }

        rules = []
        rules += [(f'{x}', 0, qSTYLES['braces']) for x in JsonHighlighter.braces]
        rules += [(f'{x}', 0, qSTYLES['bools']) for x in JsonHighlighter.bools]
        rules += [(f'{x}', 0, qSTYLES['colons']) for x in JsonHighlighter.colons]
        rules.append(('[0-9]+', 0, qSTYLES['number']))
        rules.append(('"([^"]*)"', 0, qSTYLES['string']))
        self.rules = [(QtCore.QRegExp(pat), index, fmt) for (pat, index, fmt) in rules]
        # this only really works because the last rule overwrites all the wrongly matched things from before

    def highlightBlock(self, text):
        for expressions, nth, forma in self.rules:
            index = expressions.indexIn(text, 0)
            while index >= 0:
                index = expressions.pos(nth)
                length = len(expressions.cap(nth))
                self.setFormat(index, length, forma)
                index = expressions.indexIn(text, index + length)
        self.setCurrentBlockState(0)
        # self.setFormat(0, 25, self.rules[0][2])

    @staticmethod
    def qformat(*color, style=''):
        """Return a QTextCharFormat with the given attributes.
        """
        _color = QColor.fromRgb(*color)

        _format = QTextCharFormat()
        _format.setForeground(_color)
        if 'bold' in style:
            _format.setFontWeight(QFont.Bold)
        if 'italic' in style:
            _format.setFontItalic(True)

        return _format

    def colorSchema(self):
        # GruvBox Light
        # https://github.com/morhetz/gruvbox
        self.colors['bg'] = QColor.fromRgb(251, 241, 199)
        self.colors['red'] = QColor.fromRgb(204, 36, 29)
        self.colors['green'] = QColor.fromRgb(152, 151, 26)
        self.colors['yellow'] = QColor.fromRgb(215, 153, 33)
        self.colors['blue'] = QColor.fromRgb(69, 133, 136)
        self.colors['purple'] = QColor.fromRgb(177, 98, 134)
        self.colors['fg'] = QColor.fromRgb(60, 131, 54)
        self.colors['fg0'] = QColor.fromRgb(40, 40, 40)
        self.colors['gray'] = QColor.fromRgb(124, 111, 100)


# Logging directly into Qt Widget Console
# https://stackoverflow.com/a/66664679
class QLogHandler(QtCore.QObject, logging.Handler):
    new_record = QtCore.Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        super(logging.Handler).__init__()
        formatter = Formatter('%(asctime)s|%(levelname)s|%(message)s|', '%d/%m/%Y %H:%M:%S')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg) # <---- emit signal here


class Formatter(logging.Formatter):
    def formatException(self, ei):
        result = super(Formatter, self).formatException(ei)
        return result

    def format(self, record):
        s = super(Formatter, self).format(record)
        if record.exc_text:
            s = s.replace('\n', '')
        return s


def tryForFont(size: int):
    """
    tries to load one of the specified fonts in the set size
    :param size: point size of the font in px
    :type size: int
    :return: hopefully one of the QFonts, else a fixed font one
    :rtype: QFont
    """
    _fixed_font_candidates = [("Iosevka", "Light"), ("Fira Code", "Regular"), ("Hack", "Regular")]
    std_font = QFontDatabase().font("fsdopihfgsjodfgjhsadfkjsdf", "Doomsday", size)
    # * i am once again questioning my logic here but this seems to work
    for font, style in _fixed_font_candidates:
        a_font = QFontDatabase().font(font, style, size)
        if a_font != std_font:
            return a_font
    backup = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    backup.setPointSize(size)
    return backup

