#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import locale
import sqlite3
import subprocess
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import base64
import re


# QTHREAD FOR ASYNC SEARCHES IN THE DATABASE
# CALLED ON EVERY KEYPRESS
# RETURNS FIRST 500(numb_results) RESULTS MATCHING THE QUERY
class thread_db_query(QThread):
    db_query_signal = pyqtSignal(dict)

    def __init__(self, db_query, numb_results, parent=None):
        super(thread_db_query, self).__init__(parent)
        self.numb_results = numb_results
        self.db_query = db_query
        strip_and_split = db_query.strip('*').split('*')
        rx = '('+'|'.join(map(re.escape, strip_and_split))+')'
        self.regex_queries = re.compile(rx, re.IGNORECASE)

    def run(self):
        cur = con.cursor()
        cur.execute('SELECT file_path_col FROM vt_locate_data_table WHERE '
                    'file_path_col MATCH ? LIMIT ?',
                    (self.db_query, self.numb_results))
        tuppled_500 = cur.fetchall()
        results_500 = [i[0] for i in tuppled_500]

        bold_results_500 = []
        for line in results_500:
            bold = self.bold_text(line)
            bold_results_500.append(bold)

        signal_message = {'input': self.db_query, 'results': bold_results_500}
        self.db_query_signal.emit(signal_message)

    def bold_text(self, line):
        return re.sub(self.regex_queries, '<b>\\1</b>', line)


# QTHREAD FOR UPDATING THE DATABASE
# PREVENTS LOCKING UP THE GUI AND ALLOWS TO SHOW STEPS PROGRESS
class thread_database_update(QThread):
    db_update_signal = pyqtSignal(str)

    def __init__(self, sudo_passwd, parent=None):
        self.db_path = '/var/lib/angrysearch/angry_database.db'
        self.temp_db_path = '/tmp/angry_database.db'
        super(thread_database_update, self).__init__(parent)
        self.sudo_passwd = sudo_passwd

    def run(self):
        the_temp_file = '/tmp/angry_{}'.format(os.getpid())

        with open(the_temp_file, 'w+', encoding='utf-8') as self.temp_file:
            self.db_update_signal.emit('label_1')
            self.sudo_updatedb()

            self.db_update_signal.emit('label_2')
            self.locate_to_file()

            self.db_update_signal.emit('label_3')
            self.new_database()

            self.db_update_signal.emit('label_4')
            self.indexing_new_database()

            self.db_update_signal.emit('label_5')
            self.replace_old_db_with_new()

        os.remove(the_temp_file)
        self.db_update_signal.emit('the_end_of_the_update')

    def sudo_updatedb(self):
        cmd = ['sudo', '-S', 'updatedb']
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p.stdin.flush()
        p.wait()

    def locate_to_file(self):
        cmd = ['sudo', '-S', 'locate', '*']
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE, stdout=self.temp_file)
        p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p.stdin.flush()
        p.wait()

    def new_database(self):
        global con
        con = sqlite3.connect(self.temp_db_path, check_same_thread=False)
        cur = con.cursor()
        cur.execute('CREATE TABLE locate_data_table(file_path_col TEXT)')
        self.temp_file.seek(0)
        for text_line in self.temp_file:
            line = text_line.strip()
            cur.execute('INSERT INTO locate_data_table VALUES (?)', (line,))

    def indexing_new_database(self):
        con.execute('CREATE VIRTUAL TABLE vt_locate_data_table '
                    'USING fts4(file_path_col TEXT)')
        con.execute('INSERT INTO vt_locate_data_table '
                    'SELECT * FROM locate_data_table')
        con.commit()

    def replace_old_db_with_new(self):
        global con

        if not os.path.exists(self.temp_db_path):
            return
        if not os.path.exists('/var/lib/angrysearch/'):
            cmd = ['sudo', 'mkdir', '/var/lib/angrysearch/']
            p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                                 stdin=subprocess.PIPE)
            p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
            p.stdin.flush()
            p.wait()

        cmd = ['sudo', 'mv', '-f', self.temp_db_path, self.db_path]
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        p.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p.stdin.flush()
        p.wait()
        con = sqlite3.connect(self.db_path, check_same_thread=False)


# THE PRIMARY GUI, THE WIDGET WITHIN THE MAINWINDOW
class center_widget(QWidget):
    def __init__(self):
        super(center_widget, self).__init__()
        self.initUI()

    def initUI(self):
        self.search_input = QLineEdit()
        self.main_list = QListView()
        self.upd_button = QPushButton('updatedb')

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.upd_button, 1, 4)
        grid.addWidget(self.main_list, 2, 1, 4, 4)
        self.setLayout(grid)

        self.setTabOrder(self.search_input, self.main_list)
        self.setTabOrder(self.main_list, self.upd_button)


# THE MAIN APPLICATION WINDOW WITH STATUS BAR AND LOGIC
class GUI_MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(GUI_MainWindow, self).__init__(parent)
        self.settings = QSettings('angrysearch', 'angrysearch')
        self.set = {'file_manager': 'xdg-open',
                    'file_manager_receives_file_path': False,
                    'number_of_results': '500'}
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

        if self.settings.value('file_manager'):
            if self.settings.value('file_manager') not in ['', 'xdg-open']:
                self.set['file_manager'] = self.settings.value('file_manager')

                if self.settings.value('file_manager_receives_file_path'):
                    self.set['file_manager_receives_file_path'] = \
                        self.string_to_boolean(self.settings.value(
                            'file_manager_receives_file_path'))
            else:
                self.detect_file_manager()
        else:
            self.detect_file_manager()

        if self.settings.value('number_of_results'):
            if ((self.settings.value('number_of_results')).isdigit()):
                self.set['number_of_results'] = \
                    self.settings.value('number_of_results')

    def closeEvent(self, event):
        self.settings.setValue('Last_Run/geometry', self.saveGeometry())
        self.settings.setValue('Last_Run/window_state', self.saveState())
        if not self.settings.value('file_manager'):
            self.settings.setValue('file_manager', 'xdg-open')
        if not self.settings.value('file_manager_receives_file_path'):
            self.settings.setValue('file_manager_receives_file_path', 'false')
        if not self.settings.value('number_of_results'):
            self.settings.setValue('number_of_results', '500')
        event.accept()

    def init_GUI(self):
        self.locale_current = locale.getdefaultlocale()
        self.icon = self.get_icon()
        self.setWindowIcon(self.icon)

        self.threads = []
        self.file_list = []

        self.center = center_widget()
        self.setCentralWidget(self.center)

        self.setWindowTitle('ANGRYsearch')
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.center.main_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.center.main_list.clicked.connect(self.single_click)
        self.center.main_list.activated.connect(self.double_click_enter)

        self.center.search_input.textChanged[str].connect(self.on_input_change)
        self.center.upd_button.clicked.connect(self.clicked_button_updatedb)

        self.show()
        self.show_first_500()
        self.make_sys_tray()

    def make_sys_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            menu = QMenu()
            menu.addAction('v0.9.0')
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
        base64_data = 'iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAABHN\
                        CSVQICAgIfAhkiAAAAQNJREFUOI3t1M9KAlEcxfHPmP0xU6Ogo\
                        G0teoCiHjAIfIOIepvKRUE9R0G0KNApfy0c8hqKKUMrD9zVGc4\
                        9nPtlsgp5n6qSVSk7cBG8CJ6sEX63UEcXz4jE20YNPbygPy25Q\
                        o6oE+fEPXFF7A5yA9Eg2sQDcU3sJd6k89O4iiMcYKVol3rH2Mc\
                        a1meZ4hMdNPCIj+SjHHfFZU94/0Nwlv4rWoY7vhrdeLNoO86bG\
                        lym/ge3lsHDdI2fojbBG6sUtzOiQ1wQOwk6GwWKHeJyHtxOcFi\
                        0TpFaxmnhNcyIW45bQ6RS3Hq4MeB7Ltyahki9Gd2xidWiwG9va\
                        nCZqi7xlZGVHfwN6+5nU/ccBUYAAAAASUVORK5CYII='

        pm = QPixmap()
        pm.loadFromData(base64.b64decode(base64_data))
        i = QIcon()
        i.addPixmap(pm)
        return i

    def on_input_change(self, input):
        if input == '':
            self.show_first_500()
            return
        search_terms = input.split(' ')
        t = '*'
        for x in search_terms:
            t += x + '*'
        self.new_query_new_thread(t)

    def new_query_new_thread(self, input):
        n = self.set['number_of_results']
        if len(self.threads) > 30:
            del self.threads[0:9]
        self.threads.append({'input': input,
                            'thread': thread_db_query(input, n)})
        self.threads[-1]['thread'].db_query_signal.connect(
            self.database_query_done, Qt.QueuedConnection)
        self.threads[-1]['thread'].start()

    # CHECK IF THE QUERY IS THE LAST ONE BEFORE SHOWING THE DATA
    def database_query_done(self, db_query_result):
        if (db_query_result['input'] != self.threads[-1]['input']):
            return
        self.update_file_list_results(db_query_result['results'])

    def update_file_list_results(self, data):
        model = QStringListModel(data)
        self.center.main_list.setItemDelegate(HTMLDelegate())
        self.center.main_list.setModel(model)
        total = str(locale.format('%d', len(data), grouping=True))
        self.status_bar.showMessage(total)

    # RUNS ON START OR ON EMPTY INPUT
    def show_first_500(self):
        cur = con.cursor()
        cur.execute('SELECT name FROM sqlite_master WHERE '
                    'type="table" AND name="locate_data_table"')
        if cur.fetchone() is None:
            self.status_bar.showMessage('0')
            self.tutorial()
            return

        cur.execute('SELECT file_path_col FROM locate_data_table LIMIT 500')
        file_list = cur.fetchall()
        cur.execute('SELECT Count() FROM locate_data_table')
        total_rows_numb = cur.fetchone()[0]

        l = [i[0] for i in file_list]
        self.update_file_list_results(l)
        total = str(locale.format('%d', total_rows_numb, grouping=True))
        self.status_bar.showMessage(str(total))

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
        path = QModelIndex.data().replace('<b>', '').replace('</b>', '')

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
            self.status_bar.showMessage(str('NO PERMISSION'))
        else:
            self.status_bar.showMessage(str('NOPE'))

    def double_click_enter(self, QModelIndex):
        path = QModelIndex.data().replace('<b>', '').replace('</b>', '')

        if not os.path.exists(path):
            self.status_bar.showMessage('NOT FOUND')
            return

        fm = self.set['file_manager']

        if os.path.isdir(path):
            known_fm = ['dolphin', 'nemo', 'nautilus', 'doublecmd']
            for x in known_fm:
                if x in fm:
                    subprocess.Popen([x, path])
                    return
            subprocess.Popen([fm, path])
        else:
            if 'dolphin' in fm:
                cmd = ['dolphin', '--select', path]
            elif 'nemo' in fm:
                cmd = ['nemo', path]
            elif 'nautilus' in fm:
                cmd = ['nautilus', path]
            elif 'doublecmd' in fm:
                cmd = ['doublecmd', path]
            else:
                if self.set['file_manager_receives_file_path']:
                    cmd = [fm, path]
                else:
                    parent_dir = os.path.abspath(os.path.join(path, os.pardir))
                    cmd = [fm, parent_dir]
            subprocess.Popen(cmd)

    def tutorial(self):
        chat = ['  ANGRYsearch',
                '   • uses "locate" command to create own database',
                '   • locate uses "updatedb" to update its own database',
                '   • configuration can be find in /etc/updatedb.conf',
                '   • there you can exclude paths from being searched',
                '   • for Btrfs users, you really want to exclude snapshots',
                '   • add ".snapshots" to PRUNENAMES if you use snapper', '',
                '   • learn more about locate on its manpage',
                '   • learn more about updatedb on its manpage', '',
                '   • ANGRYsearch database is in /var/lib/angrysearch/',
                '   • config file is in ~/.config/angrysearch/',
                '   • currently you can set file manager manually there',
                '   • otherwise xdg-open is used which might have few hickups',
                '',
                '  time to press the updatedb button in the top right corner'
                ]
        model = QStringListModel(chat)
        self.center.main_list.setModel(model)

    def clicked_button_updatedb(self):
        self.sud = sudo_dialog(self)
        self.sud.exec_()
        self.show_first_500()

    def string_to_boolean(self, str):
        if str in ['true', 'True', 'yes', 'y', '1']:
            return True
        else:
            return False


# UPDATE DATABASE DIALOG WITH PROGRESS SHOWN
class sudo_dialog(QDialog):
    def __init__(self, parent):
        self.values = dict()
        self.last_signal = ''
        super(sudo_dialog, self).__init__(parent)
        self.initUI()

    def __setitem__(self, k, v):
        self.values[k] = v

    def __getitem__(self, k):
        return None if k not in self.values else self.values[k]

    def initUI(self):
        self.setWindowTitle('Database Update')
        self.label_0 = QLabel('sudo password:')
        self.passwd_input = QLineEdit()
        self.passwd_input.setEchoMode(QLineEdit.Password)
        self.label_1 = QLabel('• sudo updatedb')
        self.label_2 = QLabel('• sudo locate * > /tmp/tempfile')
        self.label_3 = QLabel('• new database from the tempfile')
        self.label_4 = QLabel('• indexing the new databse')
        self.label_5 = QLabel('• replacing  the old database\n  '
                              'with the new one')
        self.OK_button = QPushButton('OK')
        self.OK_button.setEnabled(False)
        self.cancel_button = QPushButton('Cancel')

        self.label_1.setIndent(19)
        self.label_2.setIndent(19)
        self.label_3.setIndent(19)
        self.label_4.setIndent(19)
        self.label_5.setIndent(19)

        # TO MAKE SQUARE BRACKETS NOTATION WORK LATER ON
        # ALSO THE REASON FOR CUSTOM __getitem__ & __setitem__
        self['label_1'] = self.label_1
        self['label_2'] = self.label_2
        self['label_3'] = self.label_3
        self['label_4'] = self.label_4
        self['label_5'] = self.label_5

        grid = QGridLayout()
        grid.setSpacing(5)
        grid.addWidget(self.label_0, 0, 0)
        grid.addWidget(self.passwd_input, 0, 1)
        grid.addWidget(self.label_1, 1, 0, 1, 2)
        grid.addWidget(self.label_2, 2, 0, 1, 2)
        grid.addWidget(self.label_3, 3, 0, 1, 2)
        grid.addWidget(self.label_4, 4, 0, 1, 2)
        grid.addWidget(self.label_5, 5, 0, 1, 2)
        grid.addWidget(self.OK_button, 6, 0)
        grid.addWidget(self.cancel_button, 6, 1)
        self.setLayout(grid)

        self.OK_button.clicked.connect(self.clicked_OK_update_db)
        self.cancel_button.clicked.connect(self.clicked_cancel)
        self.passwd_input.textChanged[str].connect(self.password_typed)

    def password_typed(self, input):
        if len(input) > 0:
            self.OK_button.setEnabled(True)

    def clicked_cancel(self):
        self.accept()

    def clicked_OK_update_db(self):
        sudo_passwd = self.passwd_input.text()
        self.thread_updating = thread_database_update(sudo_passwd)
        self.thread_updating.db_update_signal.connect(
            self.sudo_dialog_receive_signal, Qt.QueuedConnection)
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


# CUSTOM DELEGATE TO GET HTML RICH TEXT IN LISTVIEW
class HTMLDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        style = QApplication.style() if options.widget is None \
            else options.widget.style()

        doc = QTextDocument(self)
        doc.setHtml(options.text)

        options.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                                 QPalette.Active, QPalette.HighlightedText))

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        doc = QTextDocument(self)
        doc.setDocumentMargin(1)
        doc.setHtml(options.text)
        return QSize(doc.idealWidth(), 23)


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
        ui = GUI_MainWindow()
        sys.exit(app.exec_())
