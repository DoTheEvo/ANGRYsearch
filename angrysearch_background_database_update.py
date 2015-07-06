#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
RUNNING THIS PYTHON SCRIPT WILL INDEX THE DRIVES AND CREATE NEW DATABASE
REPLACING THE OLD ONE, IT RESPECTS directories_excluded SETTINGS

RECOMMENDING USING CRONTAB TO RUN THIS FILE, 2 TIMES A DAY SOUNDS ABOUT RIGHT
CRONTAB EXAMPLE THAT EXECUTES AT MIDNIGHT AND NOON:

00 00,12 * * * /opt/angrysearch/angrysearch_background_database_update.py
'''

from datetime import datetime
import os
from PyQt5.QtCore import QSettings
import sqlite3
import subprocess

try:
    import scandir
    SCANDIR_AVAILABLE = True
except ImportError:
    SCANDIR_AVAILABLE = False


def ignored_directories():
    exclude = []
    settings = QSettings('angrysearch', 'angrysearch')
    print(settings)
    print(settings.value('directories_excluded'))

    if settings.value('directories_excluded'):
        q = settings.value('directories_excluded').strip().split()
        exclude = [x.encode() for x in q]

    exclude.append(b'proc')

    return exclude


def crawling_drives():
    def error(err):
        print(err)

    global SCANDIR_AVAILABLE

    exclude = ignored_directories()

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
        dirs[:] = [d for d in dirs if d not in exclude]

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
            size = readable_filesize(stats.st_size)
            readable_date = datetime.fromtimestamp(
                stats.st_mtime.__trunc__())
            file_list.append(
                ('0', utf_path, size, readable_date))

    table = dir_list + file_list
    new_database(table)


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


def readable_filesize(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if nbytes == 0:
        return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('{:.2f}'.format(nbytes)).rstrip('0').rstrip('.')
    return '{} {}'.format(f, suffixes[i])


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
        crawling_drives()
