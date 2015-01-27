#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import locale
import sqlite3
import subprocess
from PySide.QtCore import *
from PySide.QtGui import *
from datetime import datetime


# QTHREAD FOR ASYNC SEARCHES IN THE DATABASE
# RETURNS FIRST 500 RESULTS MATCHING THE QUERY
class thread_db_query(QThread):
    db_query_signal = Signal(list)

    def __init__(self, db_query, parent=None):
        super(thread_db_query, self).__init__(parent)
        self.db_query = db_query
        self.exiting = False

    def run(self):
        cur = con.cursor()
        cur.execute('SELECT file_path_col FROM vt_locate_data_table WHERE '
                    'file_path_col MATCH ? LIMIT 500',
                    ('%'+self.db_query+'%',))
        result = cur.fetchall()
        self.db_query_signal.emit([i[0] for i in result])


# QTHREAD FOR UPDATING THE DATABASE
# PREVENTS LOCKING UP THE GUI AND ALLOWS TO SHOW PROGRESS AS IT GOES
class thread_database_update(QThread):
    db_update_signal = Signal(str)

    def __init__(self, sudo_passwd, parent=None):
        super(thread_database_update, self).__init__(parent)
        self.sudo_passwd = sudo_passwd
        self.exiting = False

    def run(self):
        the_temp_file = '/tmp/angry_{}'.format(os.getpid())
        with open(the_temp_file, 'w+', encoding="utf-8") as self.temp_file:

            self.db_update_signal.emit('label_1')
            self.sudo_updatedb()

            self.db_update_signal.emit('label_2')
            self.locate_to_file()

            self.db_update_signal.emit('label_3')
            self.delete_old_tables()

            self.db_update_signal.emit('label_4')
            self.new_database()

            self.db_update_signal.emit('label_5')
            self.indexing_new_database()

        os.remove(the_temp_file)
        self.db_update_signal.emit('the_end_of_the_update')

    def sudo_updatedb(self):
        cmd = ['sudo', '-S', 'updatedb']
        p1 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE)
        p1.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p1.stdin.flush()
        p1.wait()

    def locate_to_file(self):
        cmd = ['sudo', '-S', 'locate', '*']
        p2 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, stdout=self.temp_file)
        p2.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p2.stdin.flush()
        p2.wait()

    def delete_old_tables(self):
        cur = con.cursor()
        cur.execute('PRAGMA writable_schema = 1')
        cur.execute('DELETE FROM SQLITE_MASTER WHERE TYPE IN '
                    '("table", "index", "trigger")')
        cur.execute('PRAGMA writable_schema = 0')
        cur.execute('VACUUM')
        cur.execute('PRAGMA INTEGRITY_CHECK')
        # print(cur.fetchone()[0])

    def new_database(self):
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


# THE PRIMARY GUI
class center_widget(QWidget):
    def __init__(self):
        super(center_widget, self).__init__()
        self.initUI()

    def initUI(self):
        self.search_input = QLineEdit()
        self.main_list = QListView()
        self.upd_button = QPushButton('updatedb')
        self.upd_button.setToolTip('run sudo updated & update local database')

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.upd_button, 1, 4)
        grid.addWidget(self.main_list, 2, 1, 4, 4)
        self.setLayout(grid)


# THE MAIN APPLICATION WINDOW WITH STATUS BAR AND LOGIC
class GUI_MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super(GUI_MainWindow, self).__init__(parent)
        self.init_GUI()

    def init_GUI(self):
        self.locale_current = locale.getdefaultlocale()
        self.setGeometry(650, 150, 600, 500)

        self.threads = []
        self.file_list = []

        self.center = center_widget()
        self.setCentralWidget(self.center)

        self.setWindowTitle('AngrySEARCH')
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.center.main_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.center.main_list.doubleClicked.connect(self.double_click)
        self.center.main_list.clicked.connect(self.list_item_selected)

        self.center.search_input.textChanged[str].connect(self.on_input_change)
        self.center.upd_button.clicked.connect(self.clicked_button_updatedb)

        self.show()
        self.initialisation()

    def on_input_change(self, input):
        if input == '':
            self.initialisation()
            return
        self.tstart = datetime.now()
        search_terms = input.split(' ')
        t = '*'
        for x in search_terms:
            t += x + '*'
        self.new_thread_new_query(t)

    def new_thread_new_query(self, input):
        if len(self.threads) > 30:
            del self.threads[0:9]
        self.threads.append(thread_db_query(input))
        self.threads[-1].start()
        self.threads[-1].db_query_signal.connect(self.database_query_done,
                                                 Qt.QueuedConnection)

    # CHECKS IF THE QUERY IS THE LAST ONE BEFORE SHOWING DATA
    def database_query_done(self, db_query_result):
        print(str(datetime.now() - self.tstart)[6:])
        if self.threads[-1].isRunning():
            return
        self.update_file_list_results(db_query_result)

    def update_file_list_results(self, data):
        model = QStringListModel(data)
        self.center.main_list.setModel(model)
        total = str(locale.format("%d", len(data), grouping=True))
        self.status_bar.showMessage(total)

    # RUNS ON START OR ON EMPTY INPUT
    def initialisation(self):
        cur = con.cursor()
        cur.execute('SELECT name FROM sqlite_master WHERE '
                    'type="table" AND name="locate_data_table"')
        if cur.fetchone() is None:
            self.status_bar.showMessage('Update the database')
            return

        cur.execute('SELECT file_path_col FROM locate_data_table LIMIT 500')
        file_list = cur.fetchall()
        cur.execute('SELECT Count() FROM locate_data_table')
        total_rows_numb = cur.fetchone()[0]

        l = [i[0] for i in file_list]
        self.update_file_list_results(l)
        total = str(locale.format("%d", total_rows_numb, grouping=True))
        self.status_bar.showMessage(str(total))
        self.center.search_input.setFocus()

    # FOR KDE DOLPHIN CURRENTLY, CAUSE XDG-OPEN IS BUGGY ON MY MACHINE
    def double_click(self, QModelIndex):
        p = QModelIndex.data()
        if os.path.exists(p):
            if os.path.isdir(p):
                subprocess.Popen(['dolphin', p])
            else:
                subprocess.Popen(['dolphin', '--select', p])
        # p = os.path.abspath(os.path.join(p, os.pardir))

    def list_item_selected(self, QModelIndex):
        self.status_bar.showMessage('')
        p = QModelIndex.data()
        mime = subprocess.check_output(['xdg-mime', 'query', 'filetype', p])
        mime = mime.decode("latin-1").strip()
        defautl_app = subprocess.check_output(['xdg-mime', 'query',
                                              'default', mime])
        defautl_app = defautl_app.decode("utf-8").strip()
        self.status_bar.showMessage(str(mime))

    def clicked_button_updatedb(self):
        self.sud = sudo_dialog(self)
        self.sud.exec_()
        self.initialisation()


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
        self.passwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.label_1 = QLabel('• sudo updatedb')
        self.label_2 = QLabel('• sudo locate * > /tmp/tempfile')
        self.label_3 = QLabel('• empty old database')
        self.label_4 = QLabel('• new database from the tempfile')
        self.label_5 = QLabel('• indexing the databse')
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
        self.thread_updating.start()
        self.thread_updating.db_update_signal.connect(
            self.sudo_dialog_receive_signal, Qt.QueuedConnection)

    def sudo_dialog_receive_signal(self, message):
        if message == 'the_end_of_the_update':
            self.accept()
            return

        label = self[message]
        label_alt = '➔' + label.text()[1:]
        label.setText(label_alt)

        if self.last_signal:
            prev_label = self[self.last_signal]
            prev_label_alt = '✔' + label.text()[1:]
            prev_label.setText(prev_label_alt)

        self.last_signal = message


if __name__ == "__main__":
    con = sqlite3.connect('angry_database.db', check_same_thread=False)
    with con:
        app = QApplication(sys.argv)
        ui = GUI_MainWindow()
        sys.exit(app.exec_())
