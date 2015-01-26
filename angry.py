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


class thread_db_query(QThread):
    db_query_signal = Signal(list)

    def __init__(self, db_query, parent=None):
        super(thread_db_query, self).__init__(parent)
        self.db_query = db_query
        self.exiting = False

    def run(self):
        cur = con.cursor()
        cur.execute('SELECT file_path FROM vt_locate_data WHERE\
                     file_path MATCH ? LIMIT 500', ('%'+self.db_query+'%',))
        result = cur.fetchall()
        self.db_query_signal.emit([i[0] for i in result])


class thread_database_update(QThread):
    db_update_signal = Signal(str)

    def __init__(self, sudo_passwd, parent=None):
        super(thread_database_update, self).__init__(parent)
        self.sudo_passwd = sudo_passwd
        self.exiting = False

    def run(self):
        # SUDO UPDATEDB
        self.db_update_signal.emit('label_1')
        cmd = ['sudo', '-S', 'updatedb']
        p1 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE)
        p1.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
        p1.stdin.flush()
        p1.wait()
        self.db_update_signal.emit('label_1')

        # SUDO LOCATE . > TEMPFILE
        self.db_update_signal.emit('label_2')
        the_temp_file = '/tmp/angry_{}'.format(os.getpid())
        cmd = ['sudo', '-S', 'locate', '.']
        with open(the_temp_file, 'w+', encoding="latin-1") as temp_file:
            p2 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                                  stdin=subprocess.PIPE, stdout=temp_file)
            p2.stdin.write(bytes(self.sudo_passwd+'\n', 'ASCII'))
            p2.stdin.flush()
            p2.wait()
            self.db_update_signal.emit('label_2')
            self.new_database(temp_file)
        os.remove(the_temp_file)
        self.db_update_signal.emit('the_end_of_the_update')

    def new_database(self, temp_file):
        # DELETE PREVIOUS DATABASE
        self.db_update_signal.emit('label_3')
        cur = con.cursor()
        cur.execute('PRAGMA writable_schema = 1')
        cur.execute('DELETE FROM SQLITE_MASTER WHERE TYPE IN '
                    '("table", "index", "trigger")')
        cur.execute('PRAGMA writable_schema = 0')
        cur.execute('VACUUM')
        cur.execute('PRAGMA INTEGRITY_CHECK')
        # print(cur.fetchone()[0])
        self.db_update_signal.emit('label_3')

        # NEW DATABASE
        self.db_update_signal.emit('label_4')
        cur.execute('CREATE TABLE locate_data(file_path TEXT)')
        temp_file.seek(0)
        for text_line in temp_file:
            line = text_line.strip()
            cur.execute('INSERT INTO locate_data VALUES (?)', (line,))
        self.db_update_signal.emit('label_4')

        # INDEXING OF THE NEW DATABASE
        self.db_update_signal.emit('label_5')
        con.execute('CREATE VIRTUAL TABLE vt_locate_data '
                    'USING fts4(file_path TEXT)')
        con.execute('INSERT INTO vt_locate_data SELECT * FROM locate_data')
        con.commit()
        self.db_update_signal.emit('label_5')


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

        self.center.search_input.textChanged[str].connect(self.on_text_change)
        self.center.upd_button.clicked.connect(self.button_updatedb)

        self.show()
        self.initialisation()

    # CALLED AFTER DATABASE QUERY IS COMPLETED
    # CHECKS IF THE QUERY WAS THE LAST ONE BEFORE SHOWING DATA
    def update_GUI(self, db_query_result):
        print(str(datetime.now() - self.tstart)[6:])
        if self.threads[-1].isRunning():
            return
        self.update_list(db_query_result)

    def set_up_new_thread(self, input):
        if len(self.threads) > 30:
            del self.threads[0:9]
        self.threads.append(thread_db_query(input))
        self.threads[-1].start()
        self.threads[-1].db_query_signal.connect(self.update_GUI,
                                                 Qt.QueuedConnection)

    def update_list(self, data):
        # FOR SOME REASON THIS FUNCTION IS CALLED AGAIN WITH NO DATA
        if data is None:
            return
        model = QStringListModel(data)
        self.center.main_list.setModel(model)
        total = str(locale.format("%d", len(data), grouping=True))
        self.status_bar.showMessage(total)

    # RUNS ON START OR ON EMPTY INPUT
    def initialisation(self):
        cur = con.cursor()
        cur.execute('SELECT name FROM sqlite_master WHERE '
                    'type="table" AND name="locate_data"')
        z = cur.fetchone()
        if z is None:
            return
        cur.execute('SELECT file_path FROM locate_data LIMIT 500')
        file_list = cur.fetchall()
        cur.execute('SELECT Count() FROM locate_data')
        rows_qu = cur.fetchone()[0]

        l = self.list_from_tuples(file_list)
        self.update_list(l)
        total = str(locale.format("%d", rows_qu, grouping=True))
        self.status_bar.showMessage(str(total))
        self.center.search_input.setFocus()

    def on_text_change(self, input):
        if input == '':
            self.initialisation()
            return
        self.tstart = datetime.now()
        search_terms = input.split(' ')
        t = '*'
        for x in search_terms:
            t += x + '*'
        self.set_up_new_thread(t)

    # FOR KDE DOLPHIN CURRENTLY, CAUSE ITS BUGGY ON MY MACHINE WITH XDG-OPEN
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

    def list_from_tuples(self, list):
        return([i[0] for i in list])

    def button_updatedb(self):
        self.sud = sudo_dialog(self)
        self.sud.exec_()
        self.initialisation()


class sudo_dialog(QDialog):
    def __init__(self, parent):
        self.values = dict()
        self.labels_checked = []
        super(sudo_dialog, self).__init__(parent)
        self.initUI()

    def __setitem__(self, k, v):
        self.values[k] = v

    def __getitem__(self, k):
        return None if k not in self.values else self.values[k]

    def initUI(self):
        self.label_0 = QLabel('sudo password:')
        self.passwd_input = QLineEdit()
        # self.passwd_input.echoMode()
        self.label_1 = QLabel('• sudo updatedb')
        self.label_2 = QLabel('• sudo locate . > /tmp/tempfile')
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

        # TO MAKE BRACKET NOTATION WORK LATER ON
        # ALSO REASON FOR CUSTOM __getitem__ & __setitem__
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
        self.thread_updating.db_update_signal.connect(self.receive_signal,
                                                      Qt.QueuedConnection)

    def receive_signal(self, message):
        if message == 'the_end_of_the_update':
            self.accept()
            return

        label = self[message]
        text = label.text()
        altered = ''
        if message in self.labels_checked:
            altered = '✔' + text[1:]
        else:
            altered = '➔' + text[1:]

        label.setText(altered)
        self.labels_checked.append(message)


if __name__ == "__main__":
    con = sqlite3.connect('angry_database.db', check_same_thread=False)
    with con:
        app = QApplication(sys.argv)
        ui = GUI_MainWindow()
        sys.exit(app.exec_())
