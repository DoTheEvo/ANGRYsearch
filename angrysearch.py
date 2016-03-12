#!/usr/bin/python3
# -*- coding: utf-8 -*-

import base64
from datetime import datetime
import locale
import mimetypes
import os
import PyQt5.QtCore as Qc
import PyQt5.QtGui as Qg
import PyQt5.QtWidgets as Qw
import re
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


# THREAD FOR ASYNC SEARCHES IN THE DATABASE
# RETURNS FIRST 500(number_of_results) RESULTS MATCHING THE QUERY
# fts4 VALUE DECIDES IF USE FAST "MATCH" OR SLOWER BUT SUBSTRING AWARE "LIKE"
class Thread_db_query(Qc.QThread):
    db_query_signal = Qc.pyqtSignal(str, list)

    def __init__(self, db_query, set, parent=None):
        super().__init__()
        self.number_of_results = set['number_of_results']
        self.fts4 = set['fts4']
        self.db_query = db_query
        self.sql_query = self.query_adjustment_for_sqlite(db_query)

    def run(self):
        cur = con.cursor()
        if self.fts4 is False:
            cur.execute(
                '''SELECT * FROM angry_table WHERE path LIKE ? LIMIT ?''',
                (self.sql_query, self.number_of_results))
        else:
            cur.execute(
                '''SELECT * FROM angry_table WHERE path MATCH ? LIMIT ?''',
                (self.sql_query, self.number_of_results))
        db_query_result = cur.fetchall()
        self.db_query_signal.emit(self.db_query, db_query_result)

    def query_adjustment_for_sqlite(self, input):
        if self.fts4 is False:
            joined = '%'.join(input.split())
            return '%{0}%'.format(joined)
        else:
            joined = '*'.join(input.split())
            return '*{0}*'.format(joined)


# THREAD FOR PREVENTING DATABASE QUERY BEING DONE ON EVERY SINGLE KEYPRESS
# SHORT WAIT TIME LETS USER FINISH TYPING
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
# TWO CRAWLING FUNCTIONS, FASTER LITE MODE IS WITHOUT FILE-SIZE AND MDATE
# NEW DATABASE IS CREATED IN /tmp AND REPLACES ONE IN /.cache/angrysearch
class Thread_database_update(Qc.QThread):
    db_update_signal = Qc.pyqtSignal(str, str)
    crawl_signal = Qc.pyqtSignal(str)

    def __init__(self, lite, dirs_excluded, parent=None):
        super().__init__()
        self.table = []
        self.tstart = None
        self.crawl_time = None
        self.database_time = None

        self.lite = lite
        self.exclude = [x.encode() for x in dirs_excluded]
        self.exclude.append(b'proc')

        self.directories_timestamp = {}

    def run(self):
        self.db_update_signal.emit('label_1', None)
        if self.lite is True:
            self.crawling_drives_lite()
        else:
            self.crawling_drives()

        self.db_update_signal.emit('label_2', self.crawl_time)
        if self.lite is True:
            self.new_database_lite()
        else:
            self.new_database()

        self.db_update_signal.emit('label_3', self.database_time)
        self.replace_old_db_with_new()

        self.db_update_signal.emit('the_end_of_the_update', None)

    def crawling_drives(self):
        def error(err):
            print(err)

        global SCANDIR_AVAILABLE

        root_dir = b'/'
        self.tstart = datetime.now()

        dir_list = []
        file_list = []

        if SCANDIR_AVAILABLE:
            modul_var = scandir
        else:
            modul_var = os

        for root, dirs, files in modul_var.walk(root_dir, onerror=error):
            dirs.sort()
            files.sort()
            dirs[:] = [d for d in dirs if d not in self.exclude]
            self.crawl_signal.emit(root.decode(encoding='utf-8',
                                               errors='ignore'))
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

        self.crawl_time = datetime.now() - self.tstart
        self.crawl_time = self.time_difference(self.crawl_time.seconds)

    def crawling_drives_lite(self):
        def error(err):
            print(err)

        global SCANDIR_AVAILABLE

        root_dir = b'/'
        self.tstart = datetime.now()

        dir_list = []
        file_list = []

        if SCANDIR_AVAILABLE:
            modul_var = scandir
        else:
            modul_var = os

        for root, dirs, files in modul_var.walk(root_dir, onerror=error):
            dirs.sort()
            files.sort()
            dirs[:] = [d for d in dirs if d not in self.exclude]
            self.crawl_signal.emit(root.decode(encoding='UTF-8',
                                               errors='ignore'))

            for dname in dirs:
                dir_list.append(('1', os.path.join(root, dname).decode(
                    encoding='UTF-8', errors='ignore')))
            for fname in files:
                file_list.append(('0', os.path.join(root, fname).decode(
                    encoding='UTF-8', errors='ignore')))

        self.table = dir_list + file_list

        self.crawl_time = datetime.now() - self.tstart
        self.crawl_time = self.time_difference(self.crawl_time.seconds)

    def new_database(self):
        global con
        temp_db_path = '/tmp/angry_database.db'

        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

        con = sqlite3.connect(temp_db_path, check_same_thread=False)
        cur = con.cursor()
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts4(directory, path, size, date)''')

        cur.execute('''PRAGMA user_version = 1;''')

        self.tstart = datetime.now()

        for x in self.table:
            cur.execute('''INSERT INTO angry_table VALUES (?, ?, ?, ?)''',
                        (x[0], x[1], x[2], x[3]))

        con.commit()
        self.database_time = datetime.now() - self.tstart
        self.database_time = self.time_difference(self.database_time.seconds)

    def new_database_lite(self):
        global con
        temp_db_path = '/tmp/angry_database.db'

        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

        con = sqlite3.connect(temp_db_path, check_same_thread=False)
        cur = con.cursor()
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts4(directory, path)''')

        cur.execute('''PRAGMA user_version = 1;''')

        self.tstart = datetime.now()

        for x in self.table:
            cur.execute('''INSERT INTO angry_table VALUES (?, ?)''',
                        (x[0], x[1]))

        con.commit()
        self.database_time = datetime.now() - self.tstart
        self.database_time = self.time_difference(self.database_time.seconds)

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

    def load_previous_run_directory_mtime_data(self):
        cur = con.cursor()
        cur.execute('''PRAGMA table_info(angry_table);''')
        total_columns = len(cur.fetchall())
        if total_columns != 4:
            return

        cur.execute('''SELECT COALESCE(MAX(rowid), 0) FROM angry_table''')
        total_rows_numb = cur.fetchone()[0]
        if total_rows_numb < 1:
            return

        cur.execute('''SELECT * FROM angry_table WHERE directory="1"''')
        all_directories_tuple = cur.fetchall()

        for x in all_directories_tuple:
            self.directories_timestamp[x[1]] = x[3]

    def time_difference(self, nseconds):
        mins, secs = divmod(nseconds, 60)
        return '{:0>2d}:{:0>2d}'.format(mins, secs)


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

    # ENTER KEY AND SHIFT+ENTER KEY CATCHING
    def keyPressEvent(self, event):
        if event.key() == 16777220:
            index = self.currentIndex()
            if event.modifiers() == Qc.Qt.ShiftModifier:
                self.parent().parent().key_press_Enter(index, shift=True)
                return
            self.parent().parent().key_press_Enter(index, shift=False)
            return

        Qw.QTableView.keyPressEvent(self, event)

    # STRANGE SOLUTION TO GET TAB MOVE NEXT ROW
    def focusNextPrevChild(self, next):
        numb_columns = self.model().columnCount(self)
        for x in range(numb_columns - 1):
            Qw.QTableView.focusNextPrevChild(self, next)
        return False

    def contextMenuEvent(self, event):
        right_click_menu = Qw.QMenu(self)

        act_open = right_click_menu.addAction('Open')
        act_open.triggered.connect(self.parent().parent().right_clk_open)

        act_open_path = right_click_menu.addAction('Open Path')
        act_open_path.triggered.connect(self.parent().parent().right_clk_path)

        act_copy_path = right_click_menu.addAction('Copy Path')
        act_copy_path.triggered.connect(self.parent().parent().right_clk_copy)

        right_click_menu.exec_(event.globalPos())


# THE PRIMARY GUI DEFINING INTERFACE WIDGETS, THE WIDGET WITHIN THE MAINWINDOW
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
        self.fts4_checkbox = Qw.QCheckBox()

        grid = Qw.QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.fts4_checkbox, 1, 3)
        grid.addWidget(self.upd_button, 1, 4)
        grid.addWidget(self.table, 2, 1, 4, 4)
        self.setLayout(grid)

        self.setTabOrder(self.search_input, self.table)
        self.setTabOrder(self.table, self.upd_button)


# THE MAIN APPLICATION WINDOW WITH THE STATUS BAR AND LOGIC
# LOADS AND SAVES QSETTINGS FROM ~/.config/angrysearch
# INITIALIZES AND SETS INTERFACE, WAITING FOR USER INPUTS
class Gui_MainWindow(Qw.QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.settings = Qc.QSettings('angrysearch', 'angrysearch')
        self.set = {'angrysearch_lite': True,
                    'fts4': True,
                    'typing_delay': False,
                    'darktheme': False,
                    'fm_path_doubleclick_selects': False,
                    'icon_theme': 'adwaita',
                    'file_manager': 'xdg-open',
                    'row_height': 0,
                    'number_of_results': 500,
                    'directories_excluded': [],
                    'conditional_mounts_for_autoupdate': [],
                    'notifications': True}
        self.read_settings()
        self.init_GUI()

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

    def read_qsettings_item(self, item, type):
        if self.settings.value(item):
            k = self.settings.value(item)
            if type == 'bool':
                if k.lower() in ['false', 'no', '0', 'n', 'none', 'nope']:
                    if item == 'fast_search_but_no_substring':
                        item = 'fts4'
                    self.set[item] = False
                else:
                    self.set[item] = True
            if type == 'str':
                self.set[item] = k
            if type == 'int':
                if k.isdigit():
                    self.set[item] = int(k)
            if type == 'list':
                self.set[item] = k.strip().split()
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
        self.last_keyboard_input = {'time': 0, 'input': ''}
        self.file_list = []
        self.icon_dictionary = self.get_mime_icons()

        self.center = Center_widget(self.set)
        self.setCentralWidget(self.center)

        self.setWindowTitle('ANGRYsearch')
        self.status_bar = Qw.QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.center.fts4_checkbox.setToolTip(
            'check = fts4 indexing, fast\n'
            'uncheck = substrings work, slower')

        if self.set['fts4'] is True:
            self.center.fts4_checkbox.setChecked(True)
        self.center.fts4_checkbox.stateChanged.connect(self.checkbox_fts_click)

        self.center.table.setGridStyle(0)
        self.center.table.setSortingEnabled(True)
        self.center.table.sortByColumn(1, 0)
        self.center.table.setEditTriggers(Qw.QAbstractItemView.NoEditTriggers)
        self.center.table.setSelectionBehavior(Qw.QAbstractItemView.SelectRows)
        self.center.table.horizontalHeader().setStretchLastSection(True)
        self.center.table.setAlternatingRowColors(True)
        self.center.table.verticalHeader().setVisible(False)
        self.center.table.setVerticalScrollBarPolicy(Qc.Qt.ScrollBarAlwaysOn)

        self.center.table.setItemDelegate(self.HTMLDelegate())

        self.center.table.clicked.connect(self.single_click)
        self.center.table.activated.connect(self.double_click_enter)

        self.center.search_input.textChanged[str].connect(
            self.wait_for_finishing_typing)
        self.center.upd_button.clicked.connect(self.clicked_button_updatedb)

        self.database_age()

        self.show()
        self.show_first_500()
        self.make_sys_tray()

        self.center.search_input.setFocus()

    def make_sys_tray(self):
        if Qw.QSystemTrayIcon.isSystemTrayAvailable():
            menu = Qw.QMenu()
            menu.addAction('v0.9.6')
            menu.addSeparator()
            exitAction = menu.addAction('Quit')
            exitAction.triggered.connect(sys.exit)

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
            Qc.QCoreApplication.instance().quit()

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
            if len(self.waiting_threads) > 40:
                del self.waiting_threads[0:20]

    # NEW DATABASE QUERY ADDED TO LIST OF RECENT RUNNING THREADS
    def new_query_new_thread(self, input):
        if self.set['fts4'] is False:
            self.status_bar.showMessage(' ...')
        if input == '':
            self.show_first_500()
            return

        if len(self.queries_threads) > 40:
            del self.queries_threads[0:20]

        self.queries_threads.append(
            {'input': input, 'thread': Thread_db_query(input, self.set)})

        self.queries_threads[-1]['thread'].db_query_signal.connect(
            self.database_query_done, Qc.Qt.QueuedConnection)
        self.queries_threads[-1]['thread'].start()

    # CHECK IF THE RESULTS COME FROM THE LAST ONE OR THERE ARE SOME STILL GOING
    def database_query_done(self, db_query, db_query_result):
        if (db_query != self.queries_threads[-1]['input']):
            return
        self.process_database_resuls(db_query, db_query_result)

    # FORMAT DATA FOR THE MODEL
    def process_database_resuls(self, db_query, db_query_result):
        model_data = []

        strip_and_split = db_query.strip().split()
        rx = '('+'|'.join(map(re.escape, strip_and_split))+')'
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
        total = locale.format('%d', len(db_query_result), grouping=True)
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
        cur = con.cursor()

        cur.execute('''PRAGMA user_version;''')
        if cur.fetchone()[0] != 1:
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

        self.process_database_resuls('', tuppled_500)

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

    # SHOWS SELECTED ITEMS MIME TYPE
    def single_click(self, QModelIndex):
        path = self.model.itemFromIndex(QModelIndex.row(), 0)._fullpath

        if not os.path.exists(path):
            self.status_bar.showMessage('NOT FOUND')
            return

        mime = subprocess.Popen(['xdg-mime', 'query', 'filetype', path],
                                stdout=subprocess.PIPE)
        mime.wait()
        if mime.returncode == 0:
            mime_type = mime.communicate()[0].decode('latin-1').strip()
            self.status_bar.showMessage(str(mime_type))
        elif mime.returncode == 5:
            self.status_bar.showMessage('NO PERMISSION')
        else:
            self.status_bar.showMessage('NOPE')

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
            self.center.table.setStyleSheet('selection-color:red;')
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
            self.set['fts4'] = True
            self.settings.setValue('fast_search_but_no_substring', True)
        else:
            self.set['fts4'] = False
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
        self.settings.setValue('icon_theme', text)
        self.set['icon_theme'] = text
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
            options.text = ""

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
                Qw.QStyle.SE_ItemViewItemText, options)

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
        self.icon_theme_combobox.addItems(['adwaita', 'elementary', 'faenza',
                                           'numix', 'oxygen', 'ubuntu'])
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
            self.excluded_dirs_btn.setStyleSheet("color:#888;font: italic;")

        self.label_1.setIndent(70)
        self.label_2.setIndent(70)
        self.label_3.setIndent(70)

        self.crawl_label.setMinimumWidth(170)

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

    def upd_dialog_receives_signal(self, message, time=''):
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


if __name__ == '__main__':
    con = open_database()
    with con:
        app = Qw.QApplication(sys.argv)
        ui = Gui_MainWindow()
        sys.exit(app.exec_())
