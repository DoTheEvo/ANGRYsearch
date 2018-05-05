#!/bin/bash

install -Dm755 angrysearch.py "/usr/share/angrysearch/angrysearch.py"
install -Dm755 angrysearch_update_database.py "/usr/share/angrysearch/angrysearch_update_database.py"
install -Dm644 angrysearch.desktop "/usr/share/angrysearch/angrysearch.desktop"
install -Dm644 angrysearch.svg "/usr/share/angrysearch/angrysearch.svg"
install -Dm644 scandir.py "/usr/share/angrysearch/scandir.py"
install -Dm644 resource_file.py "/usr/share/angrysearch/resource_file.py"
install -Dm644 qdarkstylesheet.qss "/usr/share/angrysearch/qdarkstylesheet.qss"

ln -sf "/usr/share/angrysearch/angrysearch.py" "/usr/bin/angrysearch"
ln -sf "/usr/share/angrysearch/angrysearch.svg" "/usr/share/pixmaps"
ln -sf "/usr/share/angrysearch/angrysearch.desktop" "/usr/share/applications"
