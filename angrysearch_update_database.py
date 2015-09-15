#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''
THIS SCRIPT WILL INDEX THE DRIVES AND CREATE NEW DATABASE
REPLACING THE OLD ONE, IT RESPECTS IGNORED DIRECTORIES

USE CRONTAB TO RUN THIS UPDATE PERIODICALLY, 2 TIMES A DAY SOUNDS ABOUT RIGHT
CRONTAB EXAMPLE THAT EXECUTES AT NOON AND AT MIDNIGHT

00 00,12 * * * /opt/angrysearch/angrysearch_update_database.py
'''

import os
from PyQt5.QtCore import QSettings
import sqlite3
import subprocess

try:
    import scandir
    SCANDIR_AVAILABLE = True
except ImportError:
    SCANDIR_AVAILABLE = False

EXCLUDE = []
LITE = True


def load_settings():
    global EXCLUDE
    global LITE

    settings = QSettings('angrysearch', 'angrysearch')

    if settings.value('directories_excluded'):
        q = settings.value('directories_excluded').strip().split()
        EXCLUDE = [x.encode() for x in q]
    EXCLUDE.append(b'proc')

    l = settings.value('angrysearch_lite')
    if l.lower() in ['false', 'no', '0', 'n', 'none', 'nope']:
        LITE = False


def crawling_drives():
    def error(err):
        print(err)

    global SCANDIR_AVAILABLE
    global EXCLUDE

    root_dir = b'/'
    table = []
    dir_list = []
    file_list = []

    if SCANDIR_AVAILABLE:
        ror = scandir
    else:
        ror = os

    for root, dirs, files in ror.walk(root_dir, onerror=error):
        dirs.sort()
        files.sort()
        dirs[:] = [d for d in dirs if d not in EXCLUDE]

        for dname in dirs:
            path = os.path.join(root, dname)
            utf_path = path.decode(encoding='utf-8', errors='ignore')
            stats = os.lstat(path)
            epoch_time = stats.st_mtime.__trunc__()
            dir_list.append(('1', utf_path, '', epoch_time))
        for fname in files:
            path = os.path.join(root, fname)
            utf_path = path.decode(encoding='utf-8', errors='ignore')
            stats = os.lstat(path)
            size = stats.st_size
            epoch_time = stats.st_mtime.__trunc__()
            file_list.append(
                ('0', utf_path, size, epoch_time))

    table = dir_list + file_list
    new_database(table)


def crawling_drives_lite():
    def error(err):
        print(err)

    global SCANDIR_AVAILABLE
    global EXCLUDE

    root_dir = b'/'
    table = []
    dir_list = []
    file_list = []

    if SCANDIR_AVAILABLE:
        ror = scandir
    else:
        ror = os

    for root, dirs, files in ror.walk(root_dir, onerror=error):
        dirs.sort()
        files.sort()
        dirs[:] = [d for d in dirs if d not in EXCLUDE]

        for dname in dirs:
            dir_list.append(('1', os.path.join(root, dname).decode(
                encoding='UTF-8', errors='ignore')))
        for fname in files:
            file_list.append(('0', os.path.join(root, fname).decode(
                encoding='UTF-8', errors='ignore')))

    table = dir_list + file_list
    new_database_lite(table)


def new_database(table):
    global con
    temp_db_path = '/tmp/angry_database.db'

    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    con = sqlite3.connect(temp_db_path, check_same_thread=False)
    cur = con.cursor()
    cur.execute('''CREATE VIRTUAL TABLE angry_table
                    USING fts4(directory, path, size, date)''')

    for x in table:
        cur.execute('''INSERT INTO angry_table VALUES (?, ?, ?, ?)''',
                    (x[0], x[1], x[2], x[3]))
    con.commit()
    replace_old_db_with_new()


def new_database_lite(table):
    global con
    temp_db_path = '/tmp/angry_database.db'

    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    con = sqlite3.connect(temp_db_path, check_same_thread=False)
    cur = con.cursor()
    cur.execute('''CREATE VIRTUAL TABLE angry_table
                    USING fts4(directory, path)''')

    for x in table:
        cur.execute('''INSERT INTO angry_table VALUES (?, ?)''',
                    (x[0], x[1]))

    con.commit()
    replace_old_db_with_new()


def replace_old_db_with_new():
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
        load_settings()
        if LITE is True:
            crawling_drives_lite()
        else:
            crawling_drives()
