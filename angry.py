#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import sqlite3
from PySide.QtCore import *
from PySide.QtGui import *
import tempfile
from datetime import datetime


class thread_db_query(QThread):
    progress = Signal(list)

    def __init__(self, db_query, parent=None):
        super(thread_db_query, self).__init__(parent)
        self.db_query = db_query
        self.exiting = False

    def run(self):
        cur = con.cursor()
        cur.execute('SELECT file_path FROM vt_locate_data WHERE\
                     file_path MATCH ? LIMIT 500', ('%'+self.db_query+'%',))
        result = cur.fetchall()
        self.progress.emit([i[0] for i in result])


class center_widget(QWidget):
    def __init__(self):
        super(center_widget, self).__init__()
        self.initUI()

    def initUI(self):
        self.label_filter = QLabel('Filter:')
        self.search_input = QLineEdit()
        self.main_list = QListView()
        self.total_label = QLabel('0')
        self.upd_button = QPushButton('updatedb')
        self.upd_button.setToolTip('run sudo updated & update local database')

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.label_filter, 1, 0)
        grid.addWidget(self.search_input, 1, 1)
        grid.addWidget(self.upd_button, 1, 2)
        grid.addWidget(self.main_list, 2, 1, 4, 2)
        grid.addWidget(self.total_label, 5, 0)
        self.setLayout(grid)


class GUI_MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super(GUI_MainWindow, self).__init__(parent)
        self.init_GUI()

    def init_GUI(self):
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
        self.center.main_list.clicked.connect(self.clicked)

        self.center.search_input.textChanged[str].connect(self.on_text_change)
        self.center.upd_button.clicked.connect(self.button_updatedb)

        self.show()
        self.initialisation()

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
        self.threads[-1].progress.connect(self.update_GUI, Qt.QueuedConnection)

    def update_list(self, data):
        if data is None:
            return
        model = QStringListModel(data)
        self.center.main_list.setModel(model)

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
        self.center.total_label.setText(str(rows_qu))

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

    # for KDE dolphin currently
    def double_click(self, QModelIndex):
        p = QModelIndex.data()
        if os.path.exists(p):
            if os.path.isdir(p):
                subprocess.Popen(['dolphin', p])
            else:
                subprocess.Popen(['dolphin', '--select', p])
        # p = os.path.abspath(os.path.join(p, os.pardir))

    def clicked(self, QModelIndex):
        p = QModelIndex.data()
        print(p)
        mime = subprocess.check_output(['xdg-mime', 'query', 'filetype', p])
        mime = mime.decode("utf-8").strip()
        defautl_app = subprocess.check_output(['xdg-mime', 'query',
                                              'default', mime])
        defautl_app = defautl_app.decode("utf-8").strip()
        self.status_bar.showMessage(str(mime) + '   ' + str(defautl_app))

    def button_updatedb(self):
        sudo_passwd = self.dialogue_window_sudo_passwd()
        if sudo_passwd is False:
            return
        cmd = ['sudo', '-S', 'updatedb']
        p1 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE)
        p1.stdin.write(bytes(sudo_passwd+'\n', 'ASCII'))
        p1.stdin.flush()
        p1.wait()
        print('UPDATEDB DONE')

        cmd = ['sudo', '-S', 'locate', '.']
        with open("aaaaa.txt", 'w') as f:
            p2 = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                                  stdin=subprocess.PIPE, stdout=f)
            p2.stdin.write(bytes(sudo_passwd+'\n', 'ASCII'))
            p2.stdin.flush()
            p2.wait()

        print('EXPORT TO A TXT FILE')

        self.database_from_a_file()
        self.initialisation()

    def database_from_a_file(self):

        # DELETE PREVIOUS DATABASE DATA
        cur = con.cursor()
        cur.execute('PRAGMA writable_schema = 1')
        cur.execute('DELETE FROM SQLITE_MASTER WHERE TYPE IN '
                    '("table", "index", "trigger")')
        cur.execute('PRAGMA writable_schema = 0')
        print('done delete')
        cur.execute('VACUUM')
        cur.execute('PRAGMA INTEGRITY_CHECK')
        print(cur.fetchone()[0])
        print('done delete of the database')

        # NEW DATABASE
        cur.execute('CREATE TABLE locate_data(file_path TEXT)')
        with open("aaaaa.txt") as txt:
            for x in txt:
                line = x.strip()
                cur.execute('INSERT INTO locate_data VALUES (?)', (line,))

        print('done creating of the database')
        con.execute('CREATE VIRTUAL TABLE vt_locate_data '
                    'USING fts4(file_path TEXT)')
        con.execute('INSERT INTO vt_locate_data SELECT * FROM locate_data')
        con.commit()
        print('done indexing')

    def dialogue_window_sudo_passwd(self):
        text, ok = QInputDialog.getText(self, 'Input Dialog',
                                        'Your sudo password:')
        if ok:
            return(text)
        else:
            return False

    def list_from_tuples(self, list):
        return([i[0] for i in list])


if __name__ == "__main__":
    con = sqlite3.connect('database.db', check_same_thread=False)
    with con:
        app = QApplication(sys.argv)
        ui = GUI_MainWindow()
        sys.exit(app.exec_())
