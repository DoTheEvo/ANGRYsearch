#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Index the drives and create new database replacing the old one.

It respects ignored directories.

Use crontab to run this update periodically, 2 times a day sounds about right
crontab example that executes at noon and at midnight

00 00,12 * * * /usr/share/angrysearch/angrysearch_update_database.py
"""

# pylama:ignore=D103  ## Hide docstring warnings

import os
import sqlite3
import subprocess
import sys
from datetime import datetime

from PyQt5.QtCore import QSettings, QStandardPaths

TEMP_PATH = QStandardPaths.standardLocations(QStandardPaths.TempLocation)[0]
CACHE_PATH = QStandardPaths.standardLocations(QStandardPaths.CacheLocation)[0]
DATABASE_PATH = CACHE_PATH + '/angrysearch/angry_database.db'

# CHECK SCANDIR AVAILABILITY
try:
    import scandir
    SCANDIR_AVAILABLE = True
except ImportError:
    SCANDIR_AVAILABLE = False

# CHECK IF NOTIFICATIONS CAN BE MADE
try:
    from gi import require_version
    require_version('Gtk', '3.0')
    require_version('Notify', '0.7')
    from gi.repository import Notify, GdkPixbuf
    NOTIFY_AVAILABLE = True
except ImportError:
    NOTIFY_AVAILABLE = False

# FIX FOR CRONTAB
if 'DISPLAY' not in os.environ:
    os.environ['DISPLAY'] = ':0'

# MORE GLOBAL VARIABLES
LITE = True
PREP_EXCLUDED = []
MOUNTS_NEEDED = []
NOTIFICATIONS_ENABLED = True
START_TIME = datetime.now()


def load_settings():
    global LITE
    global PREP_EXCLUDED
    global MOUNTS_NEEDED
    global NOTIFICATIONS_ENABLED

    settings = QSettings('angrysearch', 'angrysearch')

    if settings.value('angrysearch_lite'):
        q = settings.value('angrysearch_lite')
        if q.lower() in ['false', 'no', '0', 'n', 'none', 'nope']:
            LITE = False

    if settings.value('directories_excluded'):
        dirs_excluded = settings.value('directories_excluded').strip().split()

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
                PREP_EXCLUDED.append(z)

    if settings.value('conditional_mounts_for_autoupdate'):
        q = settings.value('conditional_mounts_for_autoupdate').strip().split()
        MOUNTS_NEEDED = [x for x in q]

    if settings.value('notifications'):
        q = settings.value('notifications')
        if q.lower() in ['false', 'no', '0', 'n', 'none', 'nope']:
            NOTIFICATIONS_ENABLED = False


def test_conditional_mounts_for_autoupdate():
    missing_mount = False
    missing_mounts_list = []

    for x in MOUNTS_NEEDED:
        if not os.path.ismount(x):
            missing_mount = True
            missing_mounts_list.append(x)

    if missing_mount is True:
        notify_text = 'aborting automatic update'

        for x in missing_mounts_list:
            notify_text = notify_text + '\n<b>{}</b> missing'.format(x)

        show_notification(notify_text)
        print('angrysearch: ' + ', '.join(notify_text.split('\n')))

        sys.exit(0)


def show_notification(text):
    global NOTIFY_AVAILABLE
    global NOTIFICATIONS_ENABLED

    if NOTIFY_AVAILABLE is False or NOTIFICATIONS_ENABLED is False:
        print('angrysearch: Desktop notifications disabled or unavailable')
        return

    Notify.init('angrysearch')
    n = Notify.Notification.new('ANGRYsearch:', text)

    possible_image_locations = [
        'angrysearch.svg',
        '/usr/share/pixmaps/angrysearch.svg',
        '/usr/share/angrysearch/angrysearch.svg',
        '/opt/angrysearch/angrysearch.svg'
    ]
    for x in possible_image_locations:
        if os.path.exists(x):
            icon = GdkPixbuf.Pixbuf.new_from_file(x)
            n.set_image_from_pixbuf(icon)
            break
    else:
        n.set_property('icon-name', 'drive-harddisk')

    n.show()


def crawling_drives():
    def error(err):
        print(err)

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

        if root == b'/' and b'proc' in dirs:
            dirs.remove(b'proc')
        dirs[:] = remove_excluded_dirs(dirs, root, PREP_EXCLUDED)

        for dname in dirs:
            path = os.path.join(root, dname)
            utf_path = path.decode(encoding='utf-8', errors='ignore')
            try:
                stats = os.lstat(path)
                epoch_time = stats.st_mtime.__trunc__()
            except:
                print('Can\'t access: ' + str(path))
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
                print('Can\'t access: ' + str(path))
                size = 0
                epoch_time = 0
            file_list.append(('0', utf_path, size, epoch_time))

    table = dir_list + file_list
    new_database(table)


def crawling_drives_lite():
    def error(err):
        print(err)

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

        if root == b'/' and b'proc' in dirs:
            dirs.remove(b'proc')
        dirs[:] = remove_excluded_dirs(dirs, root, PREP_EXCLUDED)

        for dname in dirs:
            dir_list.append(('1', os.path.join(root, dname).decode(
                encoding='UTF-8', errors='ignore')))
        for fname in files:
            file_list.append(('0', os.path.join(root, fname).decode(
                encoding='UTF-8', errors='ignore')))

    table = dir_list + file_list
    new_database_lite(table)


def remove_excluded_dirs(dirs, root, to_ignore):
    after_exclusion = []

    for x in dirs:
        for z in to_ignore:
            if x == z['ign']:
                if z['case'] == 1:
                    if root == z['up']:
                        break
                elif z['case'] == 2:
                    break
                elif z['case'] == 3:
                    y = [k for k in root.split(b'/') if k]
                    if y[-1] == z['up']:
                        break
        else:
            after_exclusion.append(x)
    return after_exclusion


def new_database(table):
    temp_db_path = TEMP_PATH + '/angry_database.db'

    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    con = sqlite3.connect(temp_db_path, check_same_thread=False)
    cur = con.cursor()

    if fts5_pragma_check():
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts5(directory, path, size, date)''')
        cur.execute('''PRAGMA user_version = 4;''')
    else:
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts4(directory, path, size, date)''')
        cur.execute('''PRAGMA user_version = 3;''')

    cur.executemany('''INSERT INTO angry_table VALUES (?, ?, ?, ?)''', table)

    con.commit()
    replace_old_db_with_new()


def new_database_lite(table):
    temp_db_path = TEMP_PATH + '/angry_database.db'

    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    con = sqlite3.connect(temp_db_path, check_same_thread=False)
    cur = con.cursor()

    if fts5_pragma_check():
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts5(directory, path)''')
        cur.execute('''PRAGMA user_version = 4;''')
    else:
        cur.execute('''CREATE VIRTUAL TABLE angry_table
                        USING fts4(directory, path)''')
        cur.execute('''PRAGMA user_version = 3;''')

    cur.executemany('''INSERT INTO angry_table VALUES (?, ?)''', table)

    con.commit()
    replace_old_db_with_new()


def replace_old_db_with_new():
    global DATABASE_PATH
    temp_db_path = TEMP_PATH + '/angry_database.db'

    dir_path = os.path.dirname(DATABASE_PATH)

    if not os.path.exists(temp_db_path):
        return
    if not os.path.exists(dir_path):
        cmd = ['install', '-d', dir_path]
        p = subprocess.Popen(cmd)
        p.wait()

    cmd = ['mv', '-f', temp_db_path, DATABASE_PATH]
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    p.wait()


def time_difference(nseconds):
    mins, secs = divmod(nseconds, 60)
    return '{:0>2d}:{:0>2d}'.format(mins, secs)


def fts5_pragma_check():
    with sqlite3.connect(':memory:') as conn:
        cur = conn.cursor()
        cur.execute('pragma compile_options;')
        available_pragmas = cur.fetchall()

    if ('ENABLE_FTS5', ) in available_pragmas:
        return True
    else:
        return False


if __name__ == '__main__':
    load_settings()
    test_conditional_mounts_for_autoupdate()
    if LITE is True:
        crawling_drives_lite()
    else:
        crawling_drives()
    total_time = datetime.now() - START_TIME
    noti_text = '{} | database updated'.format(
        time_difference(total_time.seconds))
    try:
        show_notification(noti_text)
    except Exception as err:
        print(err)
        log_path = TEMP_PATH + '/angrysearch_cron.log'
        with open(log_path, 'a') as log:
            t = '{:%Y-%b-%d | %H:%M | } '.format(datetime.now())
            log.write(t + str(err) + os.linesep)
