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

