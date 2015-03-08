# ANGRYsearch
Linux file search, instant results as you type

Attempt at making Linux version of Everything Search Engine, or MasterSeeker, or Hddb File Search, because no one else bothered.
Everyone seems to be damn content with linux file searches which are slow, populating results as they go, cli based only, heavily integrated with a file manager, limited to home directory, or are trying to be everything with full-text content search.

![alt tag](http://i.imgur.com/TyH60mq.gif)

Done in python, using PyQt5 for GUI

How it works:

* source for the data are [locate](http://linux.die.net/man/1/locate) and [updatedb](http://linux.die.net/man/1/updatedb) commands
* program exports all locate data in to a temp file 'locate * > /tmp/tempfile'
* from the tempfile a database is build and indexed
* then its available for querys, returning 500 results per search
* config file can be find in ~/.config/angrysearch
* [file manager](http://i.imgur.com/mVgU7Bg.png) with which to open results can be set there
* on double-click or enter the file_manager gets executed with path as parameter
* if its a dictionary it gets path to that dictionary
* if its a file, path by default leads to the conatining dictionary
* this behaviour can be changed in config by setting file_manager_receives_file_path to true
* there are exceptions ignoring this settings because they can highlight the file
* currently its dolhpin, nemo, nautilus, doublecmd
* these will on double-click open containing folder, highlight-selecting the file
* without anything set in the config, xdg-open is used to detect default file manager
