#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# File name: setup.py

"""
ANGRYsearch - file search, instant results as you type.

Attempt of making multiplatform version of Everything Search Engine
https://www.voidtools.com/
"""

from distutils.core import setup

LONG_DESCRIPTION = "Attempt at making Linux version of Everything Search " \
                   "Engine. " \
                   "This simple file search crawls available disks " \
                   "creating a database that can be searched using " \
                   "quick and responsive graphical interface. " \
                   "Notable difference is that by default, the entire paths "\
                   "are searched, not just files and folders names."


if __name__ == '__main__':
    setup(name='ANGRYsearch',
          version='1.0.4',
          description='Linux file search, instant results as you type',
          long_description=LONG_DESCRIPTION,
          author='DoTheEvo',
          author_email='DoTheEvo@gmail.com',
          maintainer='DoTheEvo',
          maintainer_email='DoTheEvo@gmail.com',
          url='https://github.com/DoTheEvo/ANGRYsearch',
          license='GNU GENERAL PUBLIC LICENSE, Version 2, June 1991',
          platforms=['linux'],
          scripts=['angrysearch'],
          py_modules=['angrysearch',
                      'angrysearch_update_database',
                      'scandir',
                      'resource_file'],
          data_files=[('/usr/share/angrysearch/', ['angrysearch.svg',
                                                   'qdarkstylesheet.qss']),
                      ('/usr/share/applications/', ['angrysearch.desktop']),
                      ('/usr/share/pixmaps/', ['angrysearch.svg']),
                      ]
          )
