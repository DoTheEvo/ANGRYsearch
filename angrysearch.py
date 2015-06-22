#!/usr/bin/python
# -*- coding: utf-8 -*-

import base64
from datetime import datetime
import locale
import mimetypes
import os
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import re
import sqlite3
import subprocess
import sys

try:
    import scandir
    SCANDIR_AVAILABLE = True
except ImportError:
    SCANDIR_AVAILABLE = False


# THREAD FOR ASYNC SEARCHES IN THE DATABASE
# CALLED ON EVERY KEYPRESS
# RETURNS FIRST 500(numb_results) RESULTS MATCHING THE QUERY
class Thread_db_query(QThread):
    db_query_signal = pyqtSignal(dict)

    def __init__(self, db_query, numb_results, parent=None):
        super().__init__()
        self.numb_results = numb_results
        self.db_query = db_query
        self.sql_query = self.query_adjustment_for_sqlite(db_query)

    def run(self):
        cur = con.cursor()
        cur.execute('''SELECT * FROM angry_table WHERE path MATCH ? LIMIT ?''',
                    (self.sql_query, self.numb_results))
        tuppled_500 = cur.fetchall()
        signal_message = {'input': self.db_query, 'results': tuppled_500}
        self.db_query_signal.emit(signal_message)

    def query_adjustment_for_sqlite(self, input):
        joined = '*'.join(input.split())
        return '*{0}*'.format(joined)


# THREAD FOR UPDATING THE DATABASE
# PREVENTS LOCKING UP THE GUI AND ALLOWS TO SHOW STEPS PROGRESS
class Thread_database_update(QThread):
    db_update_signal = pyqtSignal(str)
    crawl_signal = pyqtSignal(str)

    def __init__(self, sudo_passwd, settings, parent=None):
        super().__init__()
        self.db_path = '/var/lib/angrysearch/angry_database.db'
        self.temp_db_path = '/tmp/angry_database.db'
        self.sudo_passwd = sudo_passwd
        self.settings = settings
        self.table = []

    def run(self):
        self.db_update_signal.emit('label_1')
        self.crawling_drives()

        self.db_update_signal.emit('label_2')
        self.new_database()

        self.db_update_signal.emit('label_3')
        self.replace_old_db_with_new()

        self.db_update_signal.emit('the_end_of_the_update')

    def crawling_drives(self):
        def error(err):
            print(err)

        global SCANDIR_AVAILABLE

        exclude = []
        if self.settings.value('directories_excluded'):
            q = self.settings.value('directories_excluded').strip().split()
            exclude = [x.encode() for x in q]

        exclude.append(b'proc')

        root_dir = b'/'
        self.tstart = datetime.now()

        self.table = []
        dir_list = []
        file_list = []

        if SCANDIR_AVAILABLE:
            ror = scandir
        else:
            ror = os

        for root, dirs, files in ror.walk(root_dir, onerror=error):
            dirs.sort()
            files.sort()
            dirs[:] = [d for d in dirs if d not in exclude]
            self.crawl_signal.emit(root.decode(encoding='utf-8',
                                               errors='ignore'))
            for dname in dirs:
                path = os.path.join(root, dname)
                utf_path = path.decode(encoding='utf-8', errors='ignore')
                stats = os.lstat(path)
                readable_date = datetime.fromtimestamp(stats.st_mtime.__trunc__())
                dir_list.append(('1', utf_path, '', readable_date))
            for fname in files:
                path = os.path.join(root, fname)
                utf_path = path.decode(encoding='utf-8', errors='ignore')
                stats = os.lstat(path)
                size = self.readable_filesize(stats.st_size)
                readable_date = datetime.fromtimestamp(stats.st_mtime.__trunc__())
                file_list.append(
                    ('0', utf_path, size, readable_date))

        self.table = dir_list + file_list

        print(str(datetime.now() - self.tstart))

    def new_database(self):
        global con

        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

        con = sqlite3.connect(self.temp_db_path, check_same_thread=False)
        cur = con.cursor()
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts4(directory, path, size, date)''')

        self.tstart = datetime.now()

        for x in self.table:
            cur.execute('''INSERT INTO angry_table VALUES (?, ?, ?, ?)''',
                        (x[0], x[1], x[2], x[3]))

        con.commit()
        print(str(datetime.now() - self.tstart))

    def replace_old_db_with_new(self):
        global con

        if not os.path.exists(self.temp_db_path):
            return
        if not os.path.exists('/var/lib/angrysearch/'):
            cmd = ['sudo', 'mkdir', '/var/lib/angrysearch/']
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 stdin=subprocess.PIPE)
            p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
            p.stdin.flush()
            p.wait()

        cmd = ['sudo', '-S', 'mv', '-f', self.temp_db_path, self.db_path]
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p.stdin.flush()
        p.wait()

        con = sqlite3.connect(self.db_path, check_same_thread=False)

    def readable_filesize(self, nbytes):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if nbytes == 0: return '0 B'
        i = 0
        while nbytes >= 1024 and i < len(suffixes)-1:
            nbytes /= 1024.
            i += 1
        f = ('{:.2f}'.format(nbytes)).rstrip('0').rstrip('.')
        return '{} {}'.format(f, suffixes[i])


# MODEL FOR TABLE DATA
class Model_table(QAbstractTableModel):
    def __init__(self, table_data=[[]], parent=None):
        super().__init__()
        self.table_data = table_data
        self.headers = ['Name', 'Path', 'Size', 'Date Modified']

    def rowCount(self, parent):
        return len(self.table_data)

    def columnCount(self, parent):
        return 4

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return self.headers[section]

    def data(self, index, role):
        if role == Qt.DisplayRole:
            row = index.row()
            column = index.column()
            value = self.table_data[row][column]
            if column == 0:
                return value.text()
            else:
                return value

        if role == Qt.DecorationRole and index.column() == 0:
            row = index.row()
            column = index.column()
            value = self.table_data[row][column]
            return value.icon()

    def itemFromIndex(self, index):
        row = index.row()
        column = index.column()
        value = self.table_data[row][column]
        if index.column() == 0:
            return value


class My_table(QTableView):
    def __init__(self, parent=None):
        super().__init__()
        #rowHeight = self.fontMetrics().height()
        self.verticalHeader().setDefaultSectionSize(24)

    def resizeEvent(self, event):
        width = event.size().width()
        self.setColumnWidth(0, width * 0.30)
        self.setColumnWidth(1, width * 0.40)
        self.setColumnWidth(2, width * 0.10)
        self.setColumnWidth(3, width * 0.20)


# THE PRIMARY GUI, THE WIDGET WITHIN THE MAINWINDOW
class Center_widget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.search_input = QLineEdit()
        self.main_table = My_table()
        self.upd_button = QPushButton('update')

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.upd_button, 1, 4)
        grid.addWidget(self.main_table, 2, 1, 4, 4)
        self.setLayout(grid)

        self.setTabOrder(self.search_input, self.main_table)
        self.setTabOrder(self.main_table, self.upd_button)


# THE MAIN APPLICATION WINDOW WITH THE STATUS BAR AND LOGIC
class Gui_MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.settings = QSettings('angrysearch', 'angrysearch')
        self.set = {'icon_theme': 'adwaita',
                    'file_manager': 'xdg-open',
                    'number_of_results': '500',
                    'directories_excluded': []}
        self.read_settings()
        self.init_GUI()

    def read_settings(self):
        if self.settings.value('Last_Run/geometry'):
            self.restoreGeometry(self.settings.value('Last_Run/geometry'))
        else:
            self.resize(640, 480)
            qr = self.frameGeometry()
            cp = QDesktopWidget().availableGeometry().center()
            qr.moveCenter(cp)
            self.move(qr.topLeft())

        if self.settings.value('Last_Run/window_state'):
            self.restoreState(self.settings.value('Last_Run/window_state'))

        if self.settings.value('icon_theme'):
            self.set['icon_theme'] = self.settings.value('icon_theme')

        if self.settings.value('file_manager'):
            if self.settings.value('file_manager') not in ['', 'xdg-open']:
                self.set['file_manager'] = self.settings.value('file_manager')
            else:
                self.detect_file_manager()
        else:
            self.detect_file_manager()

        if self.settings.value('number_of_results'):
            if ((self.settings.value('number_of_results')).isdigit()):
                self.set['number_of_results'] = \
                    self.settings.value('number_of_results')

        if self.settings.value('directories_excluded'):
            self.set['directories_excluded'] = \
                self.settings.value('directories_excluded').strip().split()

    def closeEvent(self, event):
        self.settings.setValue('Last_Run/geometry', self.saveGeometry())
        self.settings.setValue('Last_Run/window_state', self.saveState())
        if not self.settings.value('icon_theme'):
            self.settings.setValue('icon_theme', 'adwaita')
        if not self.settings.value('file_manager'):
            self.settings.setValue('file_manager', 'xdg-open')
        if not self.settings.value('number_of_results'):
            self.settings.setValue('number_of_results', '500')
        if not self.settings.value('directories_excluded'):
            self.settings.setValue('directories_excluded', '')
        event.accept()

    def init_GUI(self):
        self.icon = self.get_icon()
        self.setWindowIcon(self.icon)
        self.model = Model_table()

        self.threads = []
        self.file_list = []

        self.center = Center_widget()
        self.setCentralWidget(self.center)

        self.setWindowTitle('ANGRYsearch')
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.center.main_table.setGridStyle(0)
        self.center.main_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.center.main_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.center.main_table.horizontalHeader().setStretchLastSection(True)
        self.center.main_table.setAlternatingRowColors(True)
        self.center.main_table.verticalHeader().setVisible(False)
        self.center.main_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.center.main_table.setItemDelegate(HTMLDelegate())

        self.center.main_table.clicked.connect(self.single_click)
        self.center.main_table.activated.connect(self.double_click_enter)

        self.center.search_input.textChanged[str].connect(
            self.new_query_new_thread)
        self.center.upd_button.clicked.connect(self.clicked_button_updatedb)

        self.show()
        self.show_first_500()
        self.make_sys_tray()

        self.center.search_input.setFocus()

    def make_sys_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            menu = QMenu()
            menu.addAction('v0.9.3')
            menu.addSeparator()
            exitAction = menu.addAction('Quit')
            exitAction.triggered.connect(sys.exit)

            self.tray_icon = QSystemTrayIcon()
            self.tray_icon.setIcon(self.icon)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
            self.tray_icon.setToolTip('ANGRYsearch')
            self.tray_icon.activated.connect(self.sys_tray_clicking)

    def sys_tray_clicking(self, reason):
        if (reason == QSystemTrayIcon.DoubleClick or
                reason == QSystemTrayIcon.Trigger):
            self.show()
        elif (reason == QSystemTrayIcon.MiddleClick):
            QCoreApplication.instance().quit()

    def get_icon(self):
        base64_data = '''iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAABHN
                         CSVQICAgIfAhkiAAAAQNJREFUOI3t1M9KAlEcxfHPmP0xU6Ogo
                         G0teoCiHjAIfIOIepvKRUE9R0G0KNApfy0c8hqKKUMrD9zVGc4
                         9nPtlsgp5n6qSVSk7cBG8CJ6sEX63UEcXz4jE20YNPbygPy25Q
                         o6oE+fEPXFF7A5yA9Eg2sQDcU3sJd6k89O4iiMcYKVol3rH2Mc
                         a1meZ4hMdNPCIj+SjHHfFZU94/0Nwlv4rWoY7vhrdeLNoO86bG
                         lym/ge3lsHDdI2fojbBG6sUtzOiQ1wQOwk6GwWKHeJyHtxOcFi
                         0TpFaxmnhNcyIW45bQ6RS3Hq4MeB7Ltyahki9Gd2xidWiwG9va
                         nCZqi7xlZGVHfwN6+5nU/ccBUYAAAAASUVORK5CYII='''

        pm = QPixmap()
        pm.loadFromData(base64.b64decode(base64_data))
        i = QIcon()
        i.addPixmap(pm)
        return i

    # QUERY THE DATABASE, LIST OF QUERIES TO KNOW THE LAST ONE
    def new_query_new_thread(self, input):
        if input == '':
            self.show_first_500()
            return

        if len(self.threads) > 30:
            del self.threads[0:9]

        self.threads.append({'input': input,
                            'thread': Thread_db_query(
                                input, self.set['number_of_results'])})

        self.threads[-1]['thread'].db_query_signal.connect(
            self.database_query_done, Qt.QueuedConnection)
        self.threads[-1]['thread'].start()

    # CHECK IF THE RESULTS COME FROM THE LAST ONE OR THERE ARE SOME STILL GOING
    def database_query_done(self, db_query_result):
        if (db_query_result['input'] != self.threads[-1]['input']):
            return
        self.process_database_resuls(db_query_result)

    # FORMAT DATA FOR THE MODEL
    def process_database_resuls(self, data):
        typed_text = data['input']
        results = data['results']
        model_data = []

        strip_and_split = typed_text.strip().split()
        rx = '('+'|'.join(map(re.escape, strip_and_split))+')'
        self.regex_queries = re.compile(rx, re.IGNORECASE)

        dir_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.SP_FileIcon)

        icon_dictionary = self.get_icons()

        for tup in results:
            split_by_slash = tup[1].split('/')

            name = name_ = split_by_slash[-1]
            path = '/'.join(split_by_slash[:-1]) or '/'

            if typed_text:
                name = self.bold_text(name)
                path = self.bold_text(path)

            n = QStandardItem(name)
            n.path = tup[1]
            if tup[0] == '1':
                n.setIcon(icon_dictionary['directory'])
            else:
                short_mime = mimetypes.guess_type(name_)
                if short_mime[0] and short_mime[0][:5] in icon_dictionary:
                    n.setIcon(icon_dictionary[short_mime[0][:5]])
                else:
                    n.setIcon(icon_dictionary['file'])
            item = [n, path, tup[2], tup[3]]

            model_data.append(item)

        self.model = Model_table(model_data)
        dir_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.SP_FileIcon)

        self.center.main_table.setModel(self.model)
        total = locale.format('%d', len(data), grouping=True)
        self.status_bar.showMessage(total)

    def bold_text(self, line):
        return re.sub(self.regex_queries, '<b>\\1</b>', line)

    def get_icons(self):
        theme = self.set['icon_theme']

        icon_dictionary = {
            'directory': QIcon(os.path.join('icons', theme, 'folder.png')),
            'file': QIcon(os.path.join('icons', theme, 'file.png')),
            'image': QIcon(os.path.join('icons', theme, 'image.png')),
            'audio': QIcon(os.path.join('icons', theme, 'audio.png')),
            'video': QIcon(os.path.join('icons', theme, 'video.png')),
            'text/': QIcon(os.path.join('icons', theme, 'text.png'))
        }

        return icon_dictionary

    # RUNS ON START OR ON EMPTY INPUT
    def show_first_500(self):
        cur = con.cursor()
        cur.execute('''SELECT name FROM sqlite_master WHERE
                        type="table" AND name="angry_table"''')
        if cur.fetchone() is None:
            self.status_bar.showMessage('0')
            self.tutorial()
            return

        cur.execute('''SELECT * FROM angry_table LIMIT ?''',
                    (self.set['number_of_results'],))
        tuppled_500 = cur.fetchall()

        self.process_database_resuls({'input': '', 'results': tuppled_500})

        cur.execute('''SELECT COALESCE(MAX(rowid), 0) FROM angry_table''')
        total_rows_numb = cur.fetchone()[0]
        total = locale.format('%d', total_rows_numb, grouping=True)
        self.status_bar.showMessage(total)

    def detect_file_manager(self):
        try:
            fm = subprocess.check_output(['xdg-mime', 'query',
                                          'default', 'inode/directory'])
            detected_fm = fm.decode('utf-8').strip().lower()

            known_fm = ['dolphin', 'nemo', 'nautilus', 'doublecmd']
            if any(item in detected_fm for item in known_fm):
                self.set['file_manager'] = detected_fm
                print('autodetected file manager: ' + detected_fm)
            else:
                self.set['file_manager'] = 'xdg-open'
        except Exception as err:
            self.set['file_manager'] = 'xdg-open'
            print(err)

    def single_click(self, QModelIndex):
        path = self.model.itemFromIndex(
            QModelIndex.child(QModelIndex.row(), 0)).path

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

    def double_click_enter(self, QModelIndex):

        column = QModelIndex.column()
        path = self.model.itemFromIndex(
            QModelIndex.child(QModelIndex.row(), 0)).path

        if not os.path.exists(path):
            self.status_bar.showMessage('NOT FOUND')
            return

        if column == 0:
            subprocess.Popen(['xdg-open', path])
        if column == 1:
            fm = self.set['file_manager']
            if 'dolphin' in fm:
                cmd = ['dolphin', '--select', path]
            elif 'nemo' in fm:
                cmd = ['nemo', path]
            elif 'nautilus' in fm:
                cmd = ['nautilus', path]
            elif 'doublecmd' in fm:
                cmd = ['doublecmd', path]
            else:
                parent_dir = os.path.abspath(os.path.join(path, os.pardir))
                cmd = [fm, parent_dir]
            subprocess.Popen(cmd)

    def tutorial(self):
        chat = ['   • config file is in ~/.config/angrysearch/',
                '',
                '   • ignored directories are space separated names',
                '   • e.g. - "dev proc .snapshots"',
                '   • Btrfs users really want to exclude snapshots',
                '   • you can set file manager manually in the config',
                '   • otherwise xdg-open is used which might have few hickups',
                '',
                '   • the database is in /var/lib/angrysearch/',
                '   • with ~1 mil files indexed it\'s size is roughly 200MB',
                ]

        self.center.main_table.setModel(QStringListModel(chat))
        self.status_bar.showMessage(
            'READ, then press the update button in the top right corner')

    def clicked_button_updatedb(self):
        self.sud = Sudo_dialog(self)
        self.sud.icon_theme_signal.connect(
            self.theme_change_icon, Qt.QueuedConnection)
        self.sud.exec_()
        self.show_first_500()
        self.center.search_input.setFocus()

    def theme_change_icon(self, text):
        self.settings.setValue('icon_theme', text)
        self.set['icon_theme'] = text
        self.show_first_500()

    def string_to_boolean(self, str):
        if str in ['true', 'True', 'yes', 'y', '1']:
            return True
        else:
            return False


# UPDATE DATABASE DIALOG WITH PROGRESS SHOWN
class Sudo_dialog(QDialog):
    icon_theme_signal = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.values = dict()
        self.last_signal = ''
        self.settings = QSettings('angrysearch', 'angrysearch')
        self.initUI()

    def __setitem__(self, k, v):
        self.values[k] = v

    def __getitem__(self, k):
        return None if k not in self.values else self.values[k]

    def initUI(self):
        self.excluded_dirs = ''
        if self.settings.value('directories_excluded'):
            self.excluded_dirs = \
                self.settings.value('directories_excluded').strip()

        self.setWindowTitle('Database Update')

        self.icon_theme_label = QLabel('icon theme:')
        self.icon_theme_combobox = QComboBox(self)
        self.icon_theme_combobox.addItem("adwaita")
        self.icon_theme_combobox.addItem("numix")
        self.icon_theme_combobox.addItem("oxygen")
        self.icon_theme_combobox.activated[str].connect(self.combo_box_change)

        self.excluded_label = QLabel('ignored directories:')
        self.excluded_dirs_btn = QPushButton(self.excluded_dirs)
        self.label_0 = QLabel('sudo password:')
        self.passwd_input = QLineEdit()
        self.passwd_input.setEchoMode(QLineEdit.Password)
        self.label_1 = QLabel('• crawling the file system')
        self.label_2 = QLabel('• creating new database')
        self.label_3 = QLabel('• replacing old database')
        self.OK_button = QPushButton('OK')
        self.OK_button.setEnabled(False)
        self.cancel_button = QPushButton('Cancel')

        if self.excluded_dirs == '':
            self.excluded_dirs_btn.setText('none')
            self.excluded_dirs_btn.setStyleSheet("color:#7700AA;font: italic;")

        self.label_1.setIndent(70)
        self.label_2.setIndent(70)
        self.label_3.setIndent(70)

        self.passwd_input.setMinimumWidth(170)

        self.excluded_dirs_btn.clicked.connect(self.exclude_dialog)

        # TO MAKE SQUARE BRACKETS NOTATION WORK LATER ON
        # ALSO THE REASON FOR CUSTOM __getitem__ & __setitem__
        self['label_1'] = self.label_1
        self['label_2'] = self.label_2
        self['label_3'] = self.label_3

        grid = QGridLayout()
        grid.setSpacing(7)
        grid.addWidget(self.icon_theme_label, 0, 0)
        grid.addWidget(self.icon_theme_combobox, 0, 1)
        grid.addWidget(self.excluded_label, 1, 0)
        grid.addWidget(self.excluded_dirs_btn, 1, 1)
        grid.addWidget(self.label_0, 2, 0)
        grid.addWidget(self.passwd_input, 2, 1)
        grid.addWidget(self.label_1, 3, 0, 1, 2)
        grid.addWidget(self.label_2, 4, 0, 1, 2)
        grid.addWidget(self.label_3, 5, 0, 1, 2)
        grid.addWidget(self.OK_button, 6, 0)
        grid.addWidget(self.cancel_button, 6, 1)
        self.setLayout(grid)

        self.OK_button.clicked.connect(self.clicked_OK_update_db)
        self.cancel_button.clicked.connect(self.clicked_cancel)
        self.passwd_input.textChanged[str].connect(self.password_typed)

        self.passwd_input.setFocus()

    def combo_box_change(self, text):
        self.icon_theme_signal.emit(text)

    def password_typed(self, input):
        if len(input) > 0:
            self.OK_button.setEnabled(True)

    def exclude_dialog(self):
        text, ok = QInputDialog.getText(self, '~/.config/angrysearch/',
                                        'Directories to be ignored:',
                                        QLineEdit.Normal, self.excluded_dirs)
        if ok:
            text = text.strip()
            self.settings.setValue('directories_excluded', text)
            self.excluded_dirs = text
            if text == '':
                self.excluded_dirs_btn.setText('none')
                self.excluded_dirs_btn.setStyleSheet('color:#7700AA;'
                                                     'font:italic;')
            else:
                self.excluded_dirs_btn.setText(text)
                self.excluded_dirs_btn.setStyleSheet("color:#000;")

    def clicked_cancel(self):
        self.accept()

    def clicked_OK_update_db(self):
        sudo_passwd = self.passwd_input.text()
        self.thread_updating = Thread_database_update(
            sudo_passwd, self.settings)
        self.thread_updating.db_update_signal.connect(
            self.sudo_dialog_receive_signal, Qt.QueuedConnection)
        self.thread_updating.crawl_signal.connect(
            self.sudo_dialog_receive_crawl, Qt.QueuedConnection)

        self.label_0.setText('crawling in:')
        self.passwd_input.setEchoMode(QLineEdit.Normal)

        self.thread_updating.start()

    def sudo_dialog_receive_signal(self, message):
        if message == 'the_end_of_the_update':
            self.accept()
            return

        label = self[message]
        label_alt = '➔' + label.text()[1:]
        label.setText(label_alt)

        if self.last_signal:
            prev_label = self[self.last_signal]
            prev_label_alt = '✔' + prev_label.text()[1:]
            prev_label.setText(prev_label_alt)

        self.last_signal = message

    def sudo_dialog_receive_crawl(self, message):
        self.passwd_input.setText(message[:19])


# CUSTOM DELEGATE TO GET HTML RICH TEXT IN LISTVIEW
class HTMLDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__()
        self.doc = QTextDocument(self)

    def paint(self, painter, option, index):
        painter.save()

        options = QStyleOptionViewItem(option)

        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        options.text = ""

        style = QApplication.style() if options.widget is None \
            else options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                                 QPalette.Active, QPalette.HighlightedText))

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)

        if index.column() != 0:
            textRect.adjust(5, 0, 0, 0)
        #textRect.adjust(0, 0, 0, 0)

        thefuckyourshitup_constant = 4
        margin = (option.rect.height() - options.fontMetrics.height()) // 2
        margin = margin - thefuckyourshitup_constant
        textRect.setTop(textRect.top() + margin)

        painter.translate(textRect.topLeft())
        painter.setClipRect(option.rect.translated(-option.rect.topLeft()))
        self.doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(self.doc.idealWidth(), self.doc.size().height())


def open_database():
    path = '/var/lib/angrysearch/angry_database.db'
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
        app = QApplication(sys.argv)
        ui = Gui_MainWindow()
        sys.exit(app.exec_())
