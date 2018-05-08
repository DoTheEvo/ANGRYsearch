#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# File name: setup.py

"""
ANGRYsearch - file search, instant results as you typeself.

Attempt of making multiplatform version of Everything Search Engine
https://www.voidtools.com/
"""

from distutils.core import setup

from scandir import __version__

LONG_DESCRIPTION = "Attempt at making Linux version of Everything Search " \
                   "Engine because no one else bothered." \
                   "Everyone seems to be damn content with searches that " \
                   "are slow, populating results as they go; or are cli " \
                   "based, making it difficult to comfortably make use of " \
                   "the results; or are heavily integrated with a file " \
                   "manager, often limiting search to just home; or are " \
                   "trying to be everything with full-text file’s content " \
                   "search."


if __name__ == '__main__':
    setup(name='ANGRYsearch',
          version=__version__,
          description='Linux file search, instant results as you type',
          long_description=LONG_DESCRIPTION,
          author='',
          author_email='',
          maintainer='',
          maintainer_email='',
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
