#!/usr/bin/python3
# -*- coding: utf-8 -*-

import base64
from datetime import datetime
from itertools import permutations
import locale
import mimetypes
import os
import platform
import PyQt5.QtCore as Qc
import PyQt5.QtGui as Qg
import PyQt5.QtWidgets as Qw
import re
import shlex
import sqlite3
import subprocess
import sys
import time

# QT RESOURCE FILE WITH MIME ICONS AND DARK GUI THEME ICONS
# IF NOT AVAILABLE ONLY 2 ICONS REPRESENTING FILE & DIRECTORY ARE USED
try:
    import resource_file
    RESOURCE_AVAILABLE = True
except ImportError:
    RESOURCE_AVAILABLE = False

# SCANDIR ALLOWS MUCH FASTER INDEXING OF THE FILE SYSTEM, OBVIOUS IN LITE MODE
# IS NOW PART OF PYTHON 3.5, FUNCTIONALY REPLACING os.walk
try:
    import scandir
    SCANDIR_AVAILABLE = True
except ImportError:
    SCANDIR_AVAILABLE = False

# THE DATABASE WAS BUILD USING FTS5 EXTENSION OF SQLITE3
FTS5_AVAILABLE = False

# FOR REGEX MODE, WHEN REGEX QUERY CAN BE RUN SO ONLY ONE ACCESS DATABASE
REGEX_QUERY_READY = True


# THREAD FOR ASYNC SEARCHES IN THE DATABASE
# RETURNS FIRST 500(number_of_results) RESULTS MATCHING THE QUERY
# fts VALUE DECIDES IF USE FAST "MATCH" OR SLOWER BUT SUBSTRING AWARE "LIKE"
class Thread_db_query(Qc.QThread):
    db_query_signal = Qc.pyqtSignal(str, list, list)

    def __init__(self, db_query, set, parent=None):
        super().__init__()
        self.words_quoted = []
        self.number_of_results = set['number_of_results']
        self.fts = set['fts']
        self.regex_mode = set['regex_mode']
        self.db_query = db_query

    def run(self):
        cur = con.cursor()

        if self.regex_mode is True:
            q = 'SELECT * FROM angry_table '\
                'WHERE path REGEXP \'{}\' LIMIT {}'.format(
                    self.db_query, self.number_of_results)
            cur.execute(q)

        elif self.fts is True:
            sql_query = self.match_query_adjustment(self.db_query)
            q = 'SELECT * FROM angry_table '\
                'WHERE angry_table MATCH \'{}\' LIMIT {}'.format(
                    sql_query, self.number_of_results)
            cur.execute(q)

        elif self.fts is False:
            sql_query = self.like_query_adjustment(self.db_query)
            q = 'SELECT * FROM angry_table '\
                'WHERE path LIKE {} LIMIT {}'.format(
                    sql_query, self.number_of_results)
            cur.execute(q)

        db_query_result = cur.fetchall()
        self.db_query_signal.emit(self.db_query,
                                  db_query_result,
                                  self.words_quoted)

    # FTS CHECKBOX IS UNCHECKED, SO NO INDEXING
    # PERMUTATION OF INPUT PHRASES IS USED SO THAT ORDER DOES NOT MATTER
    def like_query_adjustment(self, input):
        input = input.replace('"', '""')

        o = []
        p = permutations(input.strip().split())
        for x in p:
            o.append('"%{0}%"'.format('%'.join(x)))

        return ' OR path LIKE '.join(o)

    # FTS CHECKBOX IS CHECKED, FTS VIRTUAL TABLES ARE USED
    def match_query_adjustment(self, input):
        if '?' in input or '\\' in input:
            for x in ['\\', '?']:
                input = input.replace(x, '')

        query_words = input.strip().split()

        if FTS5_AVAILABLE:
            # MINUS SIGN MARKS PHRASES THAT MUST NOT APPEAR IN RESULTS
            words_no_minus = []
            excluded_words = []
            for x in query_words:
                if x.startswith('-'):
                    if len(x) > 1:
                        excluded_words.append(x[1:])
                else:
                    words_no_minus.append(x)

            if not words_no_minus:
                words_no_minus.append('1')

            # QUOTED PHRASES ARE SEARCHED WITHOUT WILD CARD * AT THE END
            final_query = ''
            words_quoted = []
            for x in words_no_minus:
                if '\"' in x:
                    if x.startswith('\"') and x.endswith('\"'):
                        x = x.replace('\"', '')
                        final_query += '"{}" '.format(x)
                        words_quoted.append(x)
                        continue
                    x = x.replace('\"', '')
                if '\'' in x:
                    if x.startswith('\'') and x.endswith('\''):
                        x = x.replace('\'', '')
                        final_query += '"{}" '.format(x)
                        words_quoted.append(x)
                        continue
                    x = x.replace('\'', '')
                final_query += '"{}"* '.format(x)

            if len(excluded_words) > 0:
                exclude_query_part = ''
                for x in excluded_words:
                    x_is_quoted = False
                    if '\"' in x:
                        if x.startswith('\"') and x.endswith('\"'):
                            x_is_quoted = True
                        x = x.replace('\"', '')
                    if '\'' in x:
                        if x.startswith('\'') and x.endswith('\''):
                            x_is_quoted = True
                        x = x.replace('\'', '')
                    if x_is_quoted:
                        if len(x) > 1:
                            exclude_query_part += 'NOT {} '.format(x)
                    else:
                        exclude_query_part += 'NOT {}* '.format(x)

                final_query = '{} {}'.format(final_query, exclude_query_part)

            self.words_quoted = words_quoted
            return final_query

        if not FTS5_AVAILABLE:
            final_query = ''
            words_quoted = []
            for x in query_words:
                if '\"' in x:
                    if x.startswith('\"') and x.endswith('\"'):
                        x = x.replace('\"', '')
                        final_query += '"{}" '.format(x)
                        words_quoted.append(x)
                        continue
                    x = x.replace('\"', '')
                if '\'' in x:
                    if x.startswith('\'') and x.endswith('\''):
                        x = x.replace('\'', '')
                        final_query += '"{}" '.format(x)
                        words_quoted.append(x)
                        continue
                    x = x.replace('\'', '')

                final_query += '{}* '.format(x)

            self.words_quoted = words_quoted
            return final_query


# THREAD FOR PREVENTING DATABASE QUERY BEING DONE ON EVERY SINGLE KEYPRESS
# SHORT WAIT TIME LETS USER FINISH TYPING, OFF BY DEFAULT
class Thread_delay_db_query(Qc.QThread):
    delay_signal = Qc.pyqtSignal(str)

    def __init__(self, input, parent=None):
        super().__init__()
        self.input = input

    def run(self):
        time.sleep(0.2)
        self.delay_signal.emit(self.input)


# THREAD FOR UPDATING THE DATABASE
# PREVENTS LOCKING UP THE GUI AND ALLOWS TO SHOW PROGRESS
# NEW DATABASE IS CREATED IN /tmp AND REPLACES ONE IN /.cache/angrysearch
class Thread_database_update(Qc.QThread):
    db_update_signal = Qc.pyqtSignal(str, str)
    crawl_signal = Qc.pyqtSignal(str)

    def __init__(self, lite, dirs_excluded, parent=None):
        super().__init__()
        self.lite = lite
        self.table = []
        self.prep_excluded = []
        self.crawl_time = ''
        self.database_time = ''

        for x in dirs_excluded:
            y = [k.encode() for k in x.split('/') if k]
            z = ''

            # IF FULL PATH
            if x.startswith('/'):
                up = b'/' + b'/'.join(y[:-1])
                z = {'case': 1, 'ign': y[-1], 'up': up}
            # IF ONLY SINGLE DIRECTORY NAME
            elif len(y) == 1:
                z = {'case': 2, 'ign': y[-1], 'up': ''}
            # IF PARENT/TARGET
            elif len(y) == 2:
                z = {'case': 3, 'ign': y[-1], 'up': y[-2]}

            if z:
                self.prep_excluded.append(z)

        self.directories_timestamp = {}

    def run(self):
        self.db_update_signal.emit('label_1', '0')
        self.crawling_drives()

        self.db_update_signal.emit('label_2', self.crawl_time)
        self.new_database()

        self.db_update_signal.emit('label_3', self.database_time)
        self.replace_old_db_with_new()

        self.db_update_signal.emit('the_end_of_the_update', '0')

    def crawling_drives(self):
        def error(err):
            print(err)

        root_dir = b'/'
        tstart = datetime.now()

        dir_list = []
        file_list = []

        if SCANDIR_AVAILABLE:
            modul_var = scandir
        else:
            modul_var = os

        for root, dirs, files in modul_var.walk(root_dir, onerror=error):
            dirs.sort()
            files.sort()

            if root == b'/' and b'proc' in dirs:
                dirs.remove(b'proc')
            # SLICING WITH [:] SO THAT THE LIST ID STAYS THE SAME
            dirs[:] = self.remove_excluded_dirs(dirs, root, self.prep_excluded)

            self.crawl_signal.emit(
                root.decode(encoding='utf-8', errors='ignore'))

            if self.lite is True:
                for dname in dirs:
                    dir_list.append(('1', os.path.join(root, dname).decode(
                        encoding='UTF-8', errors='ignore')))
                for fname in files:
                    file_list.append(('0', os.path.join(root, fname).decode(
                        encoding='UTF-8', errors='ignore')))
            else:
                for dname in dirs:
                    path = os.path.join(root, dname)
                    utf_path = path.decode(encoding='utf-8', errors='ignore')
                    try:
                        stats = os.lstat(path)
                        epoch_time = stats.st_mtime.__trunc__()
                    except:
                        print('Cant access: ' + str(path))
                        epoch_time = 0
                    dir_list.append(('1', utf_path, '', epoch_time))
                for fname in files:
                    path = os.path.join(root, fname)
                    utf_path = path.decode(encoding='utf-8', errors='ignore')
                    try:
                        stats = os.lstat(path)
                        size = stats.st_size
                        epoch_time = stats.st_mtime.__trunc__()
                    except:
                        print('Cant access: ' + str(path))
                        size = 0
                        epoch_time = 0
                    file_list.append(
                        ('0', utf_path, size, epoch_time))

        self.table = dir_list + file_list
        self.crawl_time = self.time_difference(tstart)

    def new_database(self):
        global con
        temp_db_path = '/tmp/angry_database.db'
        tstart = datetime.now()

        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

        con = sqlite3.connect(temp_db_path, check_same_thread=False)
        cur = con.cursor()

        if self.lite is True:
            if self.fts5_pragma_check() is True:
                cur.execute('''CREATE VIRTUAL TABLE angry_table
                                USING fts5(directory UNINDEXED, path)''')
                cur.execute('''PRAGMA user_version = 2;''')
            else:
                cur.execute('''CREATE VIRTUAL TABLE angry_table
                                USING fts4(directory, path,
                                           notindexed=directory)''')
                cur.execute('''PRAGMA user_version = 1;''')

            for x in self.table:
                cur.execute('''INSERT INTO angry_table VALUES (?, ?)''',
                            (x[0], x[1]))
        else:
            if self.fts5_pragma_check() is True:
                cur.execute('''CREATE VIRTUAL TABLE angry_table
                                USING fts5(directory UNINDEXED,
                                           path,
                                           size UNINDEXED, date UNINDEXED)''')
                cur.execute('''PRAGMA user_version = 2;''')
            else:
                cur.execute('''CREATE VIRTUAL TABLE angry_table
                                USING fts4(directory, path, size, date,
                                           notindexed=directory,
                                           notindexed=size,
                                           notindexed=date)''')
                cur.execute('''PRAGMA user_version = 1;''')

            for x in self.table:
                cur.execute('''INSERT INTO angry_table VALUES (?, ?, ?, ?)''',
                            (x[0], x[1], x[2], x[3]))

        con.commit()
        self.database_time = self.time_difference(tstart)

    def replace_old_db_with_new(self):
        global con

        home = os.path.expanduser('~')
        db_path = home + '/.cache/angrysearch/angry_database.db'
        temp_db_path = '/tmp/angry_database.db'

        dir_path = os.path.dirname(db_path)

        if not os.path.exists(temp_db_path):
            return
        if not os.path.exists(dir_path):
            cmd = ['install', '-d', dir_path]
            p = subprocess.Popen(cmd)
            p.wait()

        cmd = ['mv', '-f', temp_db_path, db_path]
        p = subprocess.Popen(cmd,
                             stderr=subprocess.PIPE)
        p.wait()

        con = sqlite3.connect(db_path, check_same_thread=False)
        con.create_function("regexp", 2, regexp)

    def time_difference(self, tstart):
        time_diff = datetime.now() - tstart
        mins, secs = divmod(time_diff.seconds, 60)
        return '{:0>2d}:{:0>2d}'.format(mins, secs)

    def remove_excluded_dirs(self, dirs, root, to_ignore):
        after_exclusion = []

        for x in dirs:
            for z in to_ignore:
                if x == z['ign']:
                    if z['case'] == 1:
                        if root == z['up']:
                            self.show_ignored(root, z['ign'])
                            break
                    elif z['case'] == 2:
                        self.show_ignored(root, z['ign'])
                        break
                    elif z['case'] == 3:
                        y = [k for k in root.split(b'/') if k]
                        if y[-1] == z['up']:
                            self.show_ignored(root, z['ign'])
                            break
            else:
                after_exclusion.append(x)
        return after_exclusion

    def show_ignored(self, root, item):
        r = root.decode(encoding='utf-8', errors='ignore')
        i = item.decode(encoding='utf-8', errors='ignore')
        if r == '/':
            print('Ignoring directory: /{}'.format(i))
        else:
            print('Ignoring directory: {}/{}'.format(r, i))

    # FTS5 IS A NEW EXTENSION OF SQLITE
    # SQLITE NEEDS TO BE COMPILED WITH FTS5 ENABLED
    def fts5_pragma_check(self):
        with sqlite3.connect(':memory:') as conn:
            cur = conn.cursor()
            cur.execute('pragma compile_options;')
            available_pragmas = cur.fetchall()

        if ('ENABLE_FTS5',) in available_pragmas:
            return True
        else:
            return False


# THREAD FOR GETTING MIMETYPE OF A FILE CURRENTLY SELECTED
class Thread_get_mimetype(Qc.QThread):
    mime_signal = Qc.pyqtSignal(str, str)

    def __init__(self, path, parent=None):
        super().__init__()
        self.path = path

    def run(self):
        mimetype = ''
        if not os.path.exists(self.path):
            mimetype = 'NOT FOUND'
        else:
            mime = subprocess.Popen(['xdg-mime', 'query',
                                     'filetype', self.path],
                                    stdout=subprocess.PIPE)
            mime.wait()
            if mime.returncode == 0:
                mimetype = str(mime.communicate()[0].decode('latin-1').strip())
            elif mime.returncode == 5:
                mimetype = 'NO PERMISSION'
            else:
                mimetype = 'NOPE'

        self.mime_signal.emit(self.path, mimetype)


# CUSTOM TABLE MODEL TO HAVE FINE CONTROL OVER THE CONTENT AND PRESENTATION
class Custom_table_model(Qc.QAbstractTableModel):
    def __init__(self, table_data=[[]], lite=True, parent=None):
        super().__init__()
        self.table_data = self.data_backup = table_data
        self.sort_ed = False
        if lite is True:
            self.headers = ['Name', 'Path']
        else:
            self.headers = ['Name', 'Path', 'Size', 'Date Modified']

    def rowCount(self, parent):
        return len(self.table_data)

    def columnCount(self, parent):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qc.Qt.DisplayRole and orientation == Qc.Qt.Horizontal:
            return self.headers[section]

    def data(self, index, role):
        if role == Qc.Qt.DisplayRole:
            row = index.row()
            column = index.column()
            value = self.table_data[row][column]
            if column == 3:
                return value
            else:
                return value.text()

        if role == Qc.Qt.DecorationRole and index.column() == 0:
            row = index.row()
            column = index.column()
            value = self.table_data[row][column]
            return value.icon()

    def sort(self, column, order):
        if column == 0:
            self.sort_ed = True
            self.layoutAboutToBeChanged.emit()
            self.table_data = sorted(self.table_data, key=lambda z: z[0]._name)
            self.table_data = sorted(self.table_data,
                                     key=lambda z: z[0]._is_dir, reverse=True)
            if order == Qc.Qt.DescendingOrder:
                self.table_data.reverse()
                self.table_data = sorted(self.table_data,
                                         key=lambda z: z[0]._is_dir,
                                         reverse=True)
            self.layoutChanged.emit()
        elif column == 1:
            if self.sort_ed:
                self.layoutAboutToBeChanged.emit()
                self.table_data = self.data_backup
                self.sort_ed = False
                self.layoutChanged.emit()
        elif column == 2:
            self.sort_ed = True
            self.layoutAboutToBeChanged.emit()
            self.table_data = sorted(self.table_data,
                                     key=lambda z: z[2]._bytes)
            self.table_data = sorted(self.table_data,
                                     key=lambda z: z[0]._is_dir,
                                     reverse=True)
            if order == Qc.Qt.DescendingOrder:
                self.table_data = sorted(self.table_data,
                                         key=lambda z: z[2]._bytes,
                                         reverse=True)
                self.table_data = sorted(self.table_data,
                                         key=lambda z: z[0]._is_dir,
                                         reverse=True)
            self.layoutChanged.emit()
        elif column == 3:
            self.sort_ed = True
            self.layoutAboutToBeChanged.emit()
            self.table_data = sorted(self.table_data, key=lambda z: z[3])
            self.table_data = sorted(self.table_data,
                                     key=lambda z: z[0]._is_dir, reverse=True)
            if order == Qc.Qt.DescendingOrder:
                self.table_data.reverse()
                self.table_data = sorted(self.table_data,
                                         key=lambda z: z[0]._is_dir,
                                         reverse=True)
            self.layoutChanged.emit()

    def itemFromIndex(self, row, col):
        return self.table_data[row][col]


# CUSTOM TABLE VIEW TO EASILY ADJUST ROW HEIGHT AND COLUMN WIDTH
class My_table_view(Qw.QTableView):
    def __init__(self, lite=True, row_height=0, parent=None):
        super().__init__()
        self.lite = lite
        if row_height and row_height != 0:
            self.verticalHeader().setDefaultSectionSize(row_height)

    def resizeEvent(self, event):
        width = event.size().width()
        if self.lite is True:
            self.setColumnWidth(0, width * 0.40)
            self.setColumnWidth(1, width * 0.60)
        else:
            self.setColumnWidth(0, width * 0.30)
            self.setColumnWidth(1, width * 0.38)
            self.setColumnWidth(2, width * 0.10)
            self.setColumnWidth(3, width * 0.22)

    # ROW IS HIGHLIGHTED THE MOMENT THE TABLE IS FOCUSED
    def focusInEvent(self, event):
        Qw.QTableView.focusInEvent(self, event)
        row = self.currentIndex().row()
        if row != -1:
            self.selectRow(row)

    def keyPressEvent(self, event):
        # ENTER KEY AND NUMPAD ENTER, AND WITH SHIFT
        if event.key() == 16777220 or event.key() == 16777221:
            index = self.currentIndex()
            if event.modifiers() == Qc.Qt.ShiftModifier:
                self.parent().parent().key_press_Enter(index, shift=True)
                return
            self.parent().parent().key_press_Enter(index, shift=False)
            return

        # TAB KEY GOES TO NEXT WIDGET NOT NEXT ROW IN THE TABLE
        if event.key() == 16777217:
            self.clearSelection()
            self.parent().focusNextChild()
            return

        # SHIFT + TAB KEY
        if event.key() == 16777218:
            self.clearSelection()
            self.parent().focusPreviousChild()
            return

        Qw.QTableView.keyPressEvent(self, event)

    def contextMenuEvent(self, event):
        right_click_menu = Qw.QMenu(self)

        act_open = right_click_menu.addAction('Open')
        act_open.triggered.connect(self.parent().parent().right_clk_open)

        act_open_path = right_click_menu.addAction('Open Path')
        act_open_path.triggered.connect(self.parent().parent().right_clk_path)

        right_click_menu.addSeparator()

        act_copy_path = right_click_menu.addAction('Copy Path')
        act_copy_path.triggered.connect(self.parent().parent().right_clk_copy)

        right_click_menu.exec_(event.globalPos())


# THE PRIMARY GUI DEFINING INTERFACE WIDGET, THE WIDGET WITHIN THE MAINWINDOW
class Center_widget(Qw.QWidget):
    def __init__(self, set={}):
        super().__init__()
        self.set = set
        self.initUI()

    def initUI(self):
        self.search_input = Qw.QLineEdit()
        self.table = My_table_view(self.set['angrysearch_lite'],
                                   self.set['row_height'])
        self.upd_button = Qw.QPushButton('update')
        self.fts_checkbox = Qw.QCheckBox()

        grid = Qw.QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.fts_checkbox, 1, 3)
        grid.addWidget(self.upd_button, 1, 4)
        grid.addWidget(self.table, 2, 1, 4, 4)
        self.setLayout(grid)

        self.setTabOrder(self.search_input, self.table)
        self.setTabOrder(self.table, self.upd_button)


# THE MAIN APPLICATION WINDOW WITH THE STATUS BAR AND LOGIC
# LOADS AND SAVES QSETTINGS FROM ~/.config/angrysearch
# INITIALIZES AND SETS GUI, WAITING FOR USER INPUTS
class Gui_MainWindow(Qw.QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.settings = Qc.QSettings('angrysearch', 'angrysearch')
        self.set = {'angrysearch_lite': True,
                    'fts': True,
                    'typing_delay': False,
                    'darktheme': False,
                    'fm_path_doubleclick_selects': False,
                    'icon_theme': 'adwaita',
                    'file_manager': 'xdg-open',
                    'row_height': 0,
                    'number_of_results': 500,
                    'directories_excluded': [],
                    'conditional_mounts_for_autoupdate': [],
                    'notifications': True,
                    'regex_mode': False,
                    'close_on_open': False}
        self.read_settings()
        self.init_GUI()

    def keyPressEvent(self, event):
        if type(event) == Qg.QKeyEvent:
            # ESC
            if event.key() == 16777216:
                self.close()
            # CTRL + Q
            if event.key() == 81:
                if event.modifiers() == Qc.Qt.ControlModifier:
                    self.close()
            # F6 KEY
            if event.key() == 16777269:
                self.center.search_input.selectAll()
                self.center.search_input.setFocus()
            # ALT + D
            if event.key() == 68 and event.modifiers() == Qc.Qt.AltModifier:
                self.center.search_input.selectAll()
                self.center.search_input.setFocus()
            # CTRL + L
            if event.key() == 76:
                if event.modifiers() == Qc.Qt.ControlModifier:
                    self.center.search_input.selectAll()
                    self.center.search_input.setFocus()
            # F8 FOR REGEX SEARCH MODE
            if event.key() == 16777271:
                self.set['regex_mode'] = not self.set['regex_mode']
                self.settings.setValue('regex_mode', self.set['regex_mode'])
                self.regex_mode_color_indicator()
                if self.set['regex_mode'] is True:
                    self.status_bar.showMessage('REGEX MODE ENABLED')
                else:
                    self.status_bar.showMessage('REGEX MODE DISABLED')
            # CTRL + W
            if event.key() == 87:
                if event.modifiers() == Qc.Qt.ControlModifier:
                    input_text = self.center.search_input.text().split()
                    if not input_text:
                        return
                    last_removed = ' '.join(input_text[:-1])
                    if len(input_text) > 1:
                        last_removed = last_removed + ' '
                    self.center.search_input.setText(last_removed)

            event.accept()
        else:
            event.ignore()

    def regex_mode_color_indicator(self):
        if self.set['regex_mode'] is True:
            self.center.search_input.setStyleSheet(
               'background: #FF6A00; color: #000000;')
        else:
            self.center.search_input.setStyleSheet('')

    def read_settings(self):
        if self.settings.value('Last_Run/geometry'):
            self.restoreGeometry(self.settings.value('Last_Run/geometry'))
        else:
            self.resize(720, 540)
            qr = self.frameGeometry()
            cp = Qw.QDesktopWidget().availableGeometry().center()
            qr.moveCenter(cp)
            self.move(qr.topLeft())

        if self.settings.value('Last_Run/window_state'):
            self.restoreState(self.settings.value('Last_Run/window_state'))

        self.read_qsettings_item('angrysearch_lite', 'bool')
        self.read_qsettings_item('fast_search_but_no_substring', 'bool')
        self.read_qsettings_item('typing_delay', 'bool')
        self.read_qsettings_item('darktheme', 'bool')
        self.read_qsettings_item('fm_path_doubleclick_selects', 'bool')
        self.read_qsettings_item('icon_theme', 'str')
        self.read_qsettings_item('row_height', 'int')
        self.read_qsettings_item('number_of_results', 'int')
        self.read_qsettings_item('directories_excluded', 'list')
        self.read_qsettings_item('file_manager', 'fm')
        self.read_qsettings_item('conditional_mounts_for_autoupdate', 'list')
        self.read_qsettings_item('notifications', 'bool')
        self.read_qsettings_item('regex_mode', 'bool')
        self.read_qsettings_item('close_on_open', 'bool')

    def read_qsettings_item(self, item, type):
        if self.settings.value(item):
            k = self.settings.value(item)
            if type == 'bool':
                if k.lower() in ['false', 'no', '0', 'n', 'none']:
                    if item == 'fast_search_but_no_substring':
                        item = 'fts'
                    self.set[item] = False
                else:
                    self.set[item] = True
            if type == 'str':
                self.set[item] = k
            if type == 'int':
                if k.isdigit():
                    self.set[item] = int(k)
            if type == 'list':
                self.set[item] = shlex.split(k.strip())
            if type == 'fm':
                if k in ['', 'xdg-open']:
                    self.set[item] = self.detect_file_manager()
                else:
                    self.set[item] = k
        else:
            if type == 'fm':
                self.set[item] = self.detect_file_manager()

    def detect_file_manager(self):
        try:
            fm = subprocess.check_output(['xdg-mime', 'query',
                                          'default', 'inode/directory'])
            detected_fm = fm.decode('utf-8').strip().lower()
            known_fm = ['dolphin', 'nemo', 'nautilus', 'doublecmd',
                        'thunar', 'pcmanfm', 'spacefm']
            for x in known_fm:
                if x in detected_fm:
                    print('autodetected file manager: ' + x)
                    return x
            else:
                return 'xdg-open'
        except Exception as err:
            print(err)
            return 'xdg-open'

    def closeEvent(self, event):
        self.settings.setValue('Last_Run/geometry', self.saveGeometry())
        self.settings.setValue('Last_Run/window_state', self.saveState())
        if not self.settings.contains('angrysearch_lite'):
            self.settings.setValue('angrysearch_lite', True)
        if not self.settings.contains('fast_search_but_no_substring'):
            self.settings.setValue('fast_search_but_no_substring', True)
        if not self.settings.contains('typing_delay'):
            self.settings.setValue('typing_delay', False)
        if not self.settings.contains('darktheme'):
            self.settings.setValue('darktheme', False)
        if not self.settings.contains('fm_path_doubleclick_selects'):
            self.settings.setValue('fm_path_doubleclick_selects', False)
        if not self.settings.contains('icon_theme'):
            self.settings.setValue('icon_theme', 'adwaita')
        if not self.settings.contains('file_manager'):
            self.settings.setValue('file_manager', '')
        if not self.settings.contains('row_height'):
            self.settings.setValue('row_height', 0)
        if not self.settings.contains('number_of_results'):
            self.settings.setValue('number_of_results', 500)
        if not self.settings.contains('directories_excluded'):
            self.settings.setValue('directories_excluded', '')
        if not self.settings.contains('conditional_mounts_for_autoupdate'):
            self.settings.setValue('conditional_mounts_for_autoupdate', '')
        if not self.settings.contains('notifications'):
            self.settings.setValue('notifications', True)
        if not self.settings.contains('regex_mode'):
            self.settings.setValue('regex_mode', False)
        if not self.settings.contains('close_on_open'):
            self.settings.setValue('close_on_open', False)

        # TRAY ICON NEEDS TO BE HIDDEN
        # SO THAT THE MAIN WINDOW INSTANCE AUTOMATICALLY DELETES IT ON CLOSING
        self.tray_icon.hide()
        event.accept()

    def init_GUI(self):
        self.icon = self.get_tray_icon()
        self.setWindowIcon(self.icon)

        if self.set['darktheme'] is True:
            self.style_data = ''
            if os.path.isfile('qdarkstylesheet.qss'):
                f = open('qdarkstylesheet.qss', 'r')
                self.style_data = f.read()
                f.close()
                self.setStyleSheet(self.style_data)
            elif os.path.isfile('/usr/share/angrysearch/qdarkstylesheet.qss'):
                f = open('/usr/share/angrysearch/qdarkstylesheet.qss', 'r')
                self.style_data = f.read()
                f.close()
                self.setStyleSheet(self.style_data)
            elif os.path.isfile('/opt/angrysearch/qdarkstylesheet.qss'):
                f = open('/opt/angrysearch/qdarkstylesheet.qss', 'r')
                self.style_data = f.read()
                f.close()
                self.setStyleSheet(self.style_data)

        self.queries_threads = []
        self.waiting_threads = []
        self.mime_type_threads = []
        self.last_keyboard_input = {'time': 0, 'input': ''}
        self.last_number_of_results = 500
        self.file_list = []
        self.icon_dictionary = self.get_mime_icons()

        self.center = Center_widget(self.set)
        self.setCentralWidget(self.center)

        self.setWindowTitle('ANGRYsearch')
        self.status_bar = Qw.QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.center.fts_checkbox.setToolTip(
            'check = fast search but no substrings\n'
            'uncheck = slower but substrings work')

        if self.set['fts'] is True:
            self.center.fts_checkbox.setChecked(True)
        self.center.fts_checkbox.stateChanged.connect(self.checkbox_fts_click)

        self.center.table.setGridStyle(0)
        self.center.table.setSortingEnabled(True)
        self.center.table.sortByColumn(1, 0)
        self.center.table.setEditTriggers(Qw.QAbstractItemView.NoEditTriggers)
        self.center.table.setSelectionBehavior(Qw.QAbstractItemView.SelectRows)
        self.center.table.horizontalHeader().setStretchLastSection(True)
        self.center.table.setAlternatingRowColors(True)
        self.center.table.verticalHeader().setVisible(False)
        self.center.table.setVerticalScrollBarPolicy(Qc.Qt.ScrollBarAlwaysOn)
        self.center.table.setSelectionMode(
                                       Qw.QAbstractItemView.SingleSelection)

        self.center.table.setItemDelegate(self.HTMLDelegate())

        self.center.table.activated.connect(self.double_click_enter)

        self.center.search_input.textChanged[str].connect(
            self.wait_for_finishing_typing)
        self.center.upd_button.clicked.connect(self.clicked_button_updatedb)

        self.database_age()

        self.show()
        self.show_first_500()
        self.make_sys_tray()

        self.center.search_input.setFocus()
        self.center.search_input.returnPressed.connect(self.focusNextChild)

        self.regex_mode_color_indicator()

    def make_sys_tray(self):
        if Qw.QSystemTrayIcon.isSystemTrayAvailable():
            menu = Qw.QMenu()
            menu.addAction('v1.0.1')
            menu.addSeparator()
            exitAction = menu.addAction('Quit')
            exitAction.triggered.connect(self.close)

            self.tray_icon = Qw.QSystemTrayIcon()
            self.tray_icon.setIcon(self.icon)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
            self.tray_icon.setToolTip('ANGRYsearch')
            self.tray_icon.activated.connect(self.sys_tray_clicking)

    def sys_tray_clicking(self, reason):
        if (reason == Qw.QSystemTrayIcon.DoubleClick or
                reason == Qw.QSystemTrayIcon.Trigger):
            self.show()
        elif (reason == Qw.QSystemTrayIcon.MiddleClick):
            self.close()

    def get_tray_icon(self):
        base64_data = '''iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAABHN
                         CSVQICAgIfAhkiAAAAQNJREFUOI3t1M9KAlEcxfHPmP0xU6Ogo
                         G0teoCiHjAIfIOIepvKRUE9R0G0KNApfy0c8hqKKUMrD9zVGc4
                         9nPtlsgp5n6qSVSk7cBG8CJ6sEX63UEcXz4jE20YNPbygPy25Q
                         o6oE+fEPXFF7A5yA9Eg2sQDcU3sJd6k89O4iiMcYKVol3rH2Mc
                         a1meZ4hMdNPCIj+SjHHfFZU94/0Nwlv4rWoY7vhrdeLNoO86bG
                         lym/ge3lsHDdI2fojbBG6sUtzOiQ1wQOwk6GwWKHeJyHtxOcFi
                         0TpFaxmnhNcyIW45bQ6RS3Hq4MeB7Ltyahki9Gd2xidWiwG9va
                         nCZqi7xlZGVHfwN6+5nU/ccBUYAAAAASUVORK5CYII='''

        pm = Qg.QPixmap()
        pm.loadFromData(base64.b64decode(base64_data))
        i = Qg.QIcon()
        i.addPixmap(pm)
        return i

    # OFF BY DEFAULT
    # 0.2 SEC DELAY TO LET USER FINISH TYPING BEFORE INPUT BECOMES A DB QUERY
    def wait_for_finishing_typing(self, input):
        if self.set['typing_delay'] is False:
            self.new_query_new_thread(input)
            return
        self.last_keyboard_input = input
        self.waiting_threads.append(Thread_delay_db_query(input))
        self.waiting_threads[-1].delay_signal.connect(
            self.waiting_done, Qc.Qt.QueuedConnection)
        self.waiting_threads[-1].start()

    def waiting_done(self, waiting_data):
        if self.last_keyboard_input == waiting_data:
            self.new_query_new_thread(waiting_data)
            if len(self.waiting_threads) > 100:
                del self.waiting_threads[0:80]

    # NEW DATABASE QUERY ADDED TO LIST OF RECENT RUNNING THREADS
    def new_query_new_thread(self, input):
        global REGEX_QUERY_READY
        if self.set['fts'] is False or self.set['regex_mode'] is True:
            self.status_bar.showMessage(' ...')

        if input == '' and REGEX_QUERY_READY is True:
            self.show_first_500()
            return

        if self.set['regex_mode'] is True:
            try:
                re.compile(input)
                is_valid = True
            except re.error:
                is_valid = False

            if is_valid is False:
                self.status_bar.showMessage('regex not valid')
                return

            self.queries_threads.append(
                                {'input': input,
                                 'thread': Thread_db_query(input, self.set)})

            self.queries_threads[-1]['thread'].db_query_signal.connect(
                self.database_query_done, Qc.Qt.QueuedConnection)
            if REGEX_QUERY_READY is True:
                self.queries_threads[-1]['thread'].start()
                REGEX_QUERY_READY = False
        else:
            self.queries_threads.append(
                                {'input': input,
                                 'thread': Thread_db_query(input, self.set)})

            self.queries_threads[-1]['thread'].db_query_signal.connect(
                self.database_query_done, Qc.Qt.QueuedConnection)
            self.queries_threads[-1]['thread'].start()

        if len(self.queries_threads) > 100:
            del self.queries_threads[0:80]

    # CHECK IF THE RESULTS COME FROM THE LAST ONE OR THERE ARE SOME STILL GOING
    def database_query_done(self, db_query, db_query_result, words_quoted):
        global REGEX_QUERY_READY
        REGEX_QUERY_READY = True
        if self.set['regex_mode'] is True:
            if db_query != self.queries_threads[-1]['input']:
                self.new_query_new_thread(self.queries_threads[-1]['input'])

        if db_query == self.queries_threads[-1]['input']:
            self.process_q_resuls(db_query, db_query_result, words_quoted)

    # FORMAT DATA FOR THE MODEL
    def process_q_resuls(self, db_query, db_query_result, words_quoted=[]):
        model_data = []

        if self.set['regex_mode'] is True:
            rx = '({})'.format(db_query)
        else:
            # INSTEAD OF re.escape() PROBLEMATIC CHARACTERS ARE REMOVED
            for x in ['\"', '\'', '\\', '?', '+', '[', ']', '*']:
                db_query = db_query.replace(x, '')

            strip_and_split = db_query.strip().split()
            preparation_list = []

            for x in strip_and_split:
                if x in words_quoted:
                    z = '(?<![0-9a-zA-Z]){}(?![0-9a-zA-Z])'.format(x)
                    preparation_list.append(z)
                else:
                    preparation_list.append(x)
            joined_by_pipe = '|'.join(preparation_list)
            rx = '({})'.format(joined_by_pipe)

        self.regex_queries = re.compile(rx, re.IGNORECASE)

        for tup in db_query_result:
            split_by_slash = tup[1].split('/')

            name = _name = split_by_slash[-1]
            path = _path = '/'.join(split_by_slash[:-1]) or '/'

            if db_query != '':
                name = self.bold_text(name)
                path = self.bold_text(path)

            # NAME ITEM IN THE FIRST COLUMN
            n = Qg.QStandardItem(name)
            n._name = _name.lower()
            n._parent_dir = _path
            n._fullpath = tup[1]
            n._is_dir = tup[0]

            if tup[0] == '1':
                n.setIcon(self.icon_dictionary['folder'])
            else:
                short_mime = mimetypes.guess_type(_name)[0]
                if short_mime:
                    short_mime = short_mime.split('/')
                    if short_mime[0] in self.icon_dictionary:
                        n.setIcon(self.icon_dictionary[short_mime[0]])
                    elif short_mime[1] in self.icon_dictionary:
                        n.setIcon(self.icon_dictionary[short_mime[1]])
                    else:
                        n.setIcon(self.icon_dictionary['file'])
                else:
                    n.setIcon(self.icon_dictionary['file'])

            # PATH ITEM IN THE SECOND COLUMN
            m = Qg.QStandardItem(path)
            m._parent_dir = _path
            m._fullpath = tup[1]
            m._name = n._name
            m._is_dir = tup[0]

            if self.set['angrysearch_lite'] is True:
                item = [n, m]
            else:
                # FILE SIZE ITEM IN THE THIRD COLUMN
                file_size = ''
                bytesize = 0
                if tup[2] != '':
                    bytesize = int(tup[2])
                    file_size = self.readable_filesize(bytesize)
                o = Qg.QStandardItem(file_size)
                o._bytes = bytesize

                # DATE IN THE FOURTH COLUMN
                p = datetime.fromtimestamp(tup[3])

                item = [n, m, o, str(p)]

            model_data.append(item)

        self.model = Custom_table_model(model_data,
                                        self.set['angrysearch_lite'])

        self.center.table.setModel(self.model)
        self.center.table.selectionModel().selectionChanged.connect(
            self.selection_happens)

        total = locale.format('%d', len(db_query_result), grouping=True)
        self.last_number_of_results = total
        self.status_bar.showMessage(total)

    def bold_text(self, line):
        return re.sub(self.regex_queries, '<b>\\1</b>', line)

    # CREATES DICTIONARY WITH 6 MIME TYPES ICONS DEPENDING ON THEME
    def get_mime_icons(self):
        icon_dic = {}
        iconed_mimes = ['folder', 'file', 'image', 'audio',
                        'video', 'text', 'pdf']

        if RESOURCE_AVAILABLE is True:
            for x in iconed_mimes:
                r = ':/mimeicons/{}/{}.png'.format(self.set['icon_theme'], x)
                icon_dic[x] = Qg.QIcon(r)
        else:
            for x in iconed_mimes:
                dir_icon = self.style().standardIcon(Qw.QStyle.SP_DirIcon)
                file_icon = self.style().standardIcon(Qw.QStyle.SP_FileIcon)
                icon_dic[x] = Qg.QIcon(file_icon)
            icon_dic['folder'] = Qg.QIcon(dir_icon)

        return icon_dic

    def readable_filesize(self, nbytes):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if nbytes == 0:
            return '0 B'
        i = 0
        while nbytes >= 1024 and i < len(suffixes)-1:
            nbytes /= 1024.
            i += 1
        f = ('{:.2f}'.format(nbytes)).rstrip('0').rstrip('.')
        return '{} {}'.format(f, suffixes[i])

    # RUNS ON START OR ON EMPTY INPUT, SHOWS TOP OF THE FILESYSTEM
    # CHECKS THE DATABASE AGAINST SETTINGS AND IF ITS NOT EMPTY
    def show_first_500(self):
        global FTS5_AVAILABLE
        cur = con.cursor()

        cur.execute('''PRAGMA user_version;''')
        pragma_user_version = cur.fetchone()[0]
        if pragma_user_version == 2:
            FTS5_AVAILABLE = True
        if pragma_user_version == 0:
            self.tutorial()
            return

        cur.execute('''PRAGMA table_info(angry_table);''')
        d = len(cur.fetchall())

        if d == 0:
            self.tutorial()
            return

        if self.set['angrysearch_lite'] is True and d == 4:
            self.tutorial()
            return

        if self.set['angrysearch_lite'] is False and d == 2:
            self.tutorial()
            return

        self.center.table.setDisabled(False)
        cur.execute('''SELECT * FROM angry_table LIMIT ?''',
                    (self.set['number_of_results'],))
        tuppled_500 = cur.fetchall()

        self.process_q_resuls('', tuppled_500)

        cur.execute('''SELECT COALESCE(MAX(rowid), 0) FROM angry_table''')
        total_rows_numb = cur.fetchone()[0]
        total = locale.format('%d', total_rows_numb, grouping=True)
        self.status_bar.showMessage(total)

    def key_press_Enter(self, QModelIndex, shift=False):
        if shift:
            self.double_click_enter(QModelIndex, True, True)
        else:
            self.double_click_enter(QModelIndex, True, False)

    def right_clk_open(self):
        qmodel_index = self.center.table.currentIndex()
        self.double_click_enter(qmodel_index, True, False)

    def right_clk_path(self):
        qmodel_index = self.center.table.currentIndex()
        self.double_click_enter(qmodel_index, True, True)

    def right_clk_copy(self):
        qmodel_index = self.center.table.currentIndex()
        path = self.model.itemFromIndex(qmodel_index.row(), 0)._fullpath
        clipboard = Qw.QApplication.clipboard()
        clipboard.setText(path)

    # WHEN A ROW IS SELECTED IN TABLE VIEW, BY MOUSE OR KEYBOARD
    # MIMETYPE IS GET IN A THREAD TO KEEP THE INTERFACE RESPONSIVE
    def selection_happens(self, selected_item, deselected_item):
        if selected_item.indexes():
            row = selected_item.indexes()[0].row()
            path = self.model.itemFromIndex(row, 0)._fullpath

            self.mime_type_threads.append(
                {'path': path,
                 'thread': Thread_get_mimetype(path)})

            self.mime_type_threads[-1]['thread'].mime_signal.connect(
                self.mime_type_thread_done, Qc.Qt.QueuedConnection)
            self.mime_type_threads[-1]['thread'].start()
        else:
            self.status_bar.showMessage(self.last_number_of_results)
            return

    def mime_type_thread_done(self, path, selections_mimetype):
        if (path != self.mime_type_threads[-1]['path']):
            return
        self.status_bar.showMessage(selections_mimetype)

        if len(self.mime_type_threads) > 100:
            del self.mime_type_threads[0:80]

    # THE FIRST COLUMN DOUBLECLICK OPENS THE FILE IN ASSOCIATED PROGRAM
    # THE SECOND COLUMN OPENS THE LOCATION, ATTEMPTING HIGHLIGHTING FILE
    def double_click_enter(self, QModelIndex, from_enter=False, shift=False):
        column = QModelIndex.column()
        row = QModelIndex.row()
        if column == 0:
            item = self.model.itemFromIndex(row, 0)
        else:
            item = self.model.itemFromIndex(row, 1)

        path = item._fullpath
        parent_dir = item._parent_dir
        last_item = item._name
        is_dir = (True if item._is_dir == '1' else False)

        if from_enter:
            column = 0
            if shift:
                column = 1

        self.center.table.timeout = Qc.QTimer()
        self.center.table.timeout.setSingleShot(True)
        self.center.table.timeout.timeout.connect(self.row_color_back)

        if not os.path.exists(path):
            self.status_bar.showMessage('NOT FOUND')
            if platform.linux_distribution()[0].lower() == 'ubuntu':
                self.center.table.setStyleSheet('selection-color:red;')
            else:
                self.center.table.setStyleSheet(
                                            'selection-background-color:red;')
            self.center.table.timeout.start(150)
            return
        else:
            self.center.table.setStyleSheet('selection-color:blue;')
            self.center.table.timeout.start(150)

        fm = self.set['file_manager']
        if column == 0:
            if is_dir is True:
                if fm != 'xdg-open':
                    subprocess.Popen([fm, path])
                else:
                    subprocess.Popen(['xdg-open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        else:
            if is_dir is True:
                if 'dolphin' in fm:
                    cmd = ['dolphin', '--select', path]
                elif 'nemo' in fm:
                    cmd = ['nemo', parent_dir]
                elif 'nautilus' in fm:
                    cmd = ['nautilus', parent_dir]
                elif 'doublecmd' in fm:
                    cmd = ['doublecmd', parent_dir]
                else:
                    cmd = [fm, parent_dir]
                subprocess.Popen(cmd)
            else:
                if 'dolphin' in fm:
                    cmd = ['dolphin', '--select', path]
                    subprocess.Popen(cmd)
                elif 'nemo' in fm:
                    cmd = ['nemo', path]
                    subprocess.Popen(cmd)
                elif 'nautilus' in fm:
                    cmd = ['nautilus', path]
                    subprocess.Popen(cmd)
                elif 'doublecmd' in fm:
                    cmd = ['doublecmd', path]
                    subprocess.Popen(cmd)
                elif 'thunar' in fm:
                    self.fm_highlight('thunar', parent_dir, last_item)
                elif 'pcmanfm' in fm:
                    self.fm_highlight('pcmanfm', parent_dir, last_item)
                elif 'spacefm' in fm:
                    self.fm_highlight_spacefm('spacefm', parent_dir, last_item)
                else:
                    cmd = [fm, parent_dir]
                    subprocess.Popen(cmd)

        if self.set['close_on_open'] is True:
            self.close()

    # FOR THUNAR AND PCMANFM SO THAT THEY SELECT THE FILE/FOLDER
    # NOT JUST OPEN ITS PARENT FOLDER
    def fm_highlight(self, fm, parent_dir, last_item):
        if self.set['fm_path_doubleclick_selects'] is False:
            cmd = [fm, parent_dir]
            subprocess.Popen(cmd)
            return
        cmd = [fm, parent_dir]
        subprocess.Popen(cmd)
        time.sleep(0.5)
        cmd = ['xdotool', 'key', 'ctrl+f', 'type', last_item]
        subprocess.Popen(cmd)
        time.sleep(0.5)
        cmd = ['xdotool', 'key', 'Escape']
        subprocess.Popen(cmd)

    # FOR SPACEFM
    def fm_highlight_spacefm(self, fm, parent_dir, last_item):
        if self.set['fm_path_doubleclick_selects'] is False:
            cmd = [fm, parent_dir]
            subprocess.Popen(cmd)
            return
        cmd = [fm, parent_dir]
        subprocess.Popen(cmd)
        time.sleep(0.5)
        cmd = ['spacefm', '-s', 'set', 'selected_filenames', last_item]
        subprocess.Popen(cmd)

    def row_color_back(self):
        self.center.table.setStyleSheet('')

    # USE OR DO NOT USE FTS EXTENSION TABLES IN THE DATABASE
    # FAST SEARCH OR SEARCH WITH SUBSTRINGS
    def checkbox_fts_click(self, state):
        if state == Qc.Qt.Checked:
            self.set['fts'] = True
            self.settings.setValue('fast_search_but_no_substring', True)
        else:
            self.set['fts'] = False
            self.settings.setValue('fast_search_but_no_substring', False)
        current_search = self.center.search_input.text()
        self.new_query_new_thread(current_search)
        self.center.search_input.setFocus()

    # SHOWN WHEN THERES NO DATABASE OR LITE SETTINGS CHANGED
    def tutorial(self):
        self.center.search_input.setDisabled(True)
        chat = [
            '   • config file is in ~/.config/angrysearch/angrysearch.conf',
            '   • database is in ~/.cache/angrysearch/angry_database.db',
            '   • one million files can take ~300MB and ~3 min to index',
            '',
            '   • double-click on name opens it in associated application',
            '   • double-click on path opens the location in file manager',
            '',
            '   • checkbox in the right top corner changes search behavior',
            '   • by default checked, it provides very fast searching',
            '   • drawback is that it can\'t do word bound substrings',
            '   • it would not find "Pi<b>rate</b>s", or Whip<b>lash</b>"',
            '   • it would find "<b>Pir</b>ates", or "The-<b>Fif</b>th"',
            '   • unchecking it provides substring searches, but slower',
            ]

        self.center.table.setModel(Qc.QStringListModel(chat))
        self.center.table.setDisabled(True)
        self.status_bar.showMessage(
            'Press the update button in the top right corner')

    # CREATE INSTANCE OF UPDATE THE DATABASE DIALOG WINDOW
    def clicked_button_updatedb(self):
        self.center.search_input.setDisabled(False)
        self.u = Update_dialog_window(self)
        self.u.window_close_signal.connect(
            self.update_window_close, Qc.Qt.QueuedConnection)
        self.u.icon_theme_signal.connect(
            self.theme_change_icon, Qc.Qt.QueuedConnection)
        self.u.exec_()
        self.center.search_input.setFocus()

    def update_window_close(self, text):
        if text == 'update_win_ok':
            self.center.search_input.setText('')
            self.show_first_500()
            self.database_age()

    def theme_change_icon(self, text):
        self.set['icon_theme'] = text
        self.settings.setValue('icon_theme', text)
        self.icon_dictionary = self.get_mime_icons()
        self.new_query_new_thread(self.center.search_input.text())

    # SHOW AGE OF DATABASE IN TOOLTIP OF THE UPDATE BUTTON
    def database_age(self):
        home = os.path.expanduser('~')
        path = home + '/.cache/angrysearch/angry_database.db'

        def readable_time():
            if os.path.exists(path):
                seconds = int(time.time() - os.path.getmtime(path))

                if seconds < 3600:
                    rounded = round(seconds / 60)
                    if rounded == 1:
                        return '1 minute old'
                    else:
                        return '{} minutes old'.format(rounded)
                if seconds < 172800:
                    rounded = round(seconds / 3600)
                    if rounded == 1:
                        return '1 hour old'
                    else:
                        return '{} hours old'.format(rounded)
                else:
                    rounded = round(seconds / 86400)
                    if rounded == 1:
                        return '1 day old'
                    else:
                        return '{} days old'.format(rounded)
            else:
                return 'No Database Age'

        self.center.upd_button.setToolTip(readable_time())

    # CUSTOM DELEGATE TO GET HTML RICH TEXT IN LISTVIEW
    # ALLOWS USE OF <b></b> TAGS TO HIGHLIGHT SEARCHED PHRASE IN RESULTS
    class HTMLDelegate(Qw.QStyledItemDelegate):
        def __init__(self, parent=None):
            super().__init__()
            self.doc = Qg.QTextDocument(self)

        def paint(self, painter, option, index):
            painter.save()

            options = Qw.QStyleOptionViewItem(option)

            self.initStyleOption(options, index)
            self.doc.setHtml(options.text)
            options.text = ''

            style = Qw.QApplication.style() if options.widget is None \
                else options.widget.style()
            style.drawControl(Qw.QStyle.CE_ItemViewItem, options, painter)

            ctx = Qg.QAbstractTextDocumentLayout.PaintContext()

            if option.state & Qw.QStyle.State_Selected:
                ctx.palette.setColor(Qg.QPalette.Text, option.palette.color(
                    Qg.QPalette.Active, Qg.QPalette.HighlightedText))
            else:
                ctx.palette.setColor(Qg.QPalette.Text, option.palette.color(
                    Qg.QPalette.Active, Qg.QPalette.Text))

            textRect = style.subElementRect(
                Qw.QStyle.SE_ItemViewItemText, options, None)

            if index.column() != 0:
                textRect.adjust(5, 0, 0, 0)

            thefuckyourshitup_constant = 4
            margin = (option.rect.height() - options.fontMetrics.height()) // 2
            margin = margin - thefuckyourshitup_constant
            textRect.setTop(textRect.top() + margin)

            painter.translate(textRect.topLeft())
            painter.setClipRect(textRect.translated(-textRect.topLeft()))
            self.doc.documentLayout().draw(painter, ctx)

            painter.restore()

        def sizeHint(self, option, index):
            return Qg.QSize(self.doc.idealWidth(), self.doc.size().height())


# UPDATE DATABASE DIALOG WITH PROGRESS SHOWN
class Update_dialog_window(Qw.QDialog):
    icon_theme_signal = Qc.pyqtSignal(str)
    window_close_signal = Qc.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.values = dict()
        self.last_signal = ''
        self.settings = Qc.QSettings('angrysearch', 'angrysearch')
        self.initUI()

    def __setitem__(self, k, v):
        self.values[k] = v

    def __getitem__(self, k):
        return None if k not in self.values else self.values[k]

    def initUI(self):
        self.setWindowTitle('Database Update')

        self.exclud_dirs = ' '.join(self.parent().set['directories_excluded'])
        combobox_text = self.parent().set['icon_theme']

        self.icon_theme_label = Qw.QLabel('icon theme:')
        self.icon_theme_combobox = Qw.QComboBox(self)
        self.icon_theme_combobox.addItems(
            ['adwaita', 'elementary', 'faenza', 'numix',
             'oxygen', 'paper', 'ubuntu'])
        self.icon_theme_combobox.setEditable(True)
        self.icon_theme_combobox.lineEdit().setReadOnly(True)
        self.icon_theme_combobox.lineEdit().setAlignment(Qc.Qt.AlignCenter)
        for x in range(self.icon_theme_combobox.count()):
            self.icon_theme_combobox.setItemData(
                x, Qc.Qt.AlignCenter, Qc.Qt.TextAlignmentRole)

        self.icon_theme_combobox.activated[str].connect(self.combo_box_change)

        index = self.icon_theme_combobox.findText(combobox_text)
        if index >= 0:
            self.icon_theme_combobox.setCurrentIndex(index)

        self.excluded_label = Qw.QLabel('ignored directories:')
        self.excluded_dirs_btn = Qw.QPushButton(self.exclud_dirs)
        self.crawl0_label = Qw.QLabel('progress:')
        self.crawl_label = Qw.QLabel('')
        self.label_1 = Qw.QLabel('• crawling the file system')
        self.label_2 = Qw.QLabel('• creating new database')
        self.label_3 = Qw.QLabel('• replacing old database')
        self.OK_button = Qw.QPushButton('Update')
        self.cancel_button = Qw.QPushButton('Cancel')

        if self.exclud_dirs == '':
            self.excluded_dirs_btn.setText('none')
            self.excluded_dirs_btn.setStyleSheet('color:#888;font: italic;')

        if FTS5_AVAILABLE:
            self.label_2.setToolTip('FTS5 Available')
        else:
            self.label_2.setToolTip('FTS4 Available')

        self.label_1.setIndent(70)
        self.label_2.setIndent(70)
        self.label_3.setIndent(70)

        self.crawl_label.setMinimumWidth(170)
        self.excluded_dirs_btn.setMaximumWidth(170)

        self.excluded_dirs_btn.clicked.connect(self.exclude_dialog)

        # TO MAKE SQUARE BRACKETS NOTATION WORK LATER ON
        # ALSO THE REASON FOR CUSTOM __getitem__ & __setitem__
        self['label_1'] = self.label_1
        self['label_2'] = self.label_2
        self['label_3'] = self.label_3

        grid = Qw.QGridLayout()
        grid.setSpacing(7)
        grid.addWidget(self.icon_theme_label, 0, 0)
        grid.addWidget(self.icon_theme_combobox, 0, 1)
        grid.addWidget(self.excluded_label, 1, 0)
        grid.addWidget(self.excluded_dirs_btn, 1, 1)
        grid.addWidget(self.crawl0_label, 2, 0)
        grid.addWidget(self.crawl_label, 2, 1)
        grid.addWidget(self.label_1, 3, 0, 1, 2)
        grid.addWidget(self.label_2, 4, 0, 1, 2)
        grid.addWidget(self.label_3, 5, 0, 1, 2)
        grid.addWidget(self.OK_button, 6, 0)
        grid.addWidget(self.cancel_button, 6, 1)
        self.setLayout(grid)

        self.OK_button.clicked.connect(self.clicked_OK_update_db)
        self.cancel_button.clicked.connect(self.clicked_cancel)

        self.OK_button.setFocus()

    def combo_box_change(self, text):
        self.icon_theme_signal.emit(text)

    def exclude_dialog(self):
        text, ok = Qw.QInputDialog.getText(self, '~/.config/angrysearch/',
                                           'Directories to be ignored:',
                                           Qw.QLineEdit.Normal,
                                           self.exclud_dirs)
        if ok:
            text = text.strip()
            self.exclud_dirs = text
            self.settings.setValue('directories_excluded', text)
            self.parent().set['directories_excluded'] = text.strip().split()
            if text == '':
                self.excluded_dirs_btn.setText('none')
                self.excluded_dirs_btn.setStyleSheet('color:#888;'
                                                     'font:italic;')
            else:
                self.excluded_dirs_btn.setText(text)
                self.excluded_dirs_btn.setStyleSheet('')
            self.OK_button.setFocus()

    def clicked_cancel(self):
        self.window_close_signal.emit('update_win_cancel')
        self.accept()

    def clicked_OK_update_db(self):
        self.OK_button.setDisabled(True)

        mounts_needed = self.parent().set['conditional_mounts_for_autoupdate']

        missing_mount = False
        missing_mounts_list = []

        for x in mounts_needed:
            if not os.path.ismount(x):
                missing_mount = True
                missing_mounts_list.append(x)

        if missing_mount:
            m = ''
            for x in missing_mounts_list:
                m = m + '&nbsp;&nbsp;&nbsp;&nbsp;<b>' + x + '</b><br>'
            n = 'Mounts missing:<br>' + m + 'Do You want to update anyway?'
            reply = Qw.QMessageBox.question(
                        self, 'Message', n,
                        Qw.QMessageBox.Yes | Qw.QMessageBox.No)

            if reply == Qw.QMessageBox.No:
                self.accept()
                return

        self.thread_updating = Thread_database_update(
            self.parent().set['angrysearch_lite'],
            self.parent().set['directories_excluded'])

        self.thread_updating.db_update_signal.connect(
            self.upd_dialog_receives_signal, Qc.Qt.QueuedConnection)

        self.thread_updating.crawl_signal.connect(
            self.upd_dialog_receives_crawl, Qc.Qt.QueuedConnection)

        self.thread_updating.start()

    def upd_dialog_receives_signal(self, message, time):
        if message == 'the_end_of_the_update':
            self.window_close_signal.emit('update_win_ok')
            self.accept()
            return

        label = self[message]
        label_alt = '➔{}'.format(label.text()[1:])
        label.setText(label_alt)

        if self.last_signal:
            prev_label = self[self.last_signal]
            prev_label_alt = '✔{} - {}'.format(prev_label.text()[1:], time)
            prev_label.setText(prev_label_alt)

        self.last_signal = message

    def upd_dialog_receives_crawl(self, message):
        self.crawl_label.setText(message)


def open_database():
    home = os.path.expanduser('~')
    path = home + '/.cache/angrysearch/angry_database.db'
    temp = '/tmp/angry_database.db'
    if os.path.exists(path):
        return sqlite3.connect(path, check_same_thread=False)
    else:
        if os.path.exists(temp):
            os.remove(temp)
        return sqlite3.connect(temp, check_same_thread=False)


# CUSTOM REGEX FUNCTION FOR SQLITE TO ALLOW REGEX SEARCH MODE
def regexp(expr, item):
    name = item.split('/')[-1]
    r = re.compile(expr, re.IGNORECASE)
    return r.search(name) is not None


if __name__ == '__main__':
    with open_database() as con:
        con.create_function("regexp", 2, regexp)
        app = Qw.QApplication(sys.argv)
        ui = Gui_MainWindow()
        sys.exit(app.exec_())
