# ANGRYsearch
Linux file search, instant results as you type

Attempt at making Linux version of Everything Search Engine, or MasterSeeker, or Hddb File Search, because no one else bothered.
Everyone seems to be damn content with linux file searches which are slow, populating results as they go, cli based only, heavily integrated with a file manager, limited to home directory, or are trying to be everything with full-text content search.

![alt tag](http://i.imgur.com/6SciMhk.gif)

Done in python, using PyQt5 for GUI

How it works:

* source for the data are [locate](http://linux.die.net/man/1/locate) and [updatedb](http://linux.die.net/man/1/updatedb) commands
* configuration for updatedb is in `/etc/updatedb.conf` where paths can be excluded from indexing
* if you use **Btrfs** file system, you really want to **exclude** your **snapshots**
* if you for example use snapper to manage your snapshots you add [.snapshots to PRUNENAMES](http://i.imgur.com/I8Vq4go.png)
* ANGRYsearch exports all locate data in to a temp file `locate * > /tmp/tempfile`
* from the tempfile a database is build and indexed
* then its available for querys, returning 500 results per search
* config file location: `~/.config/angrysearch/angrysearch.conf`
* [file manager](http://i.imgur.com/Vpi2csT.png) with which to open results can be set there
* on double-click or enter the `file_manager` gets executed with path as parameter
  * if its a directory it gets path directly to that directory
  * if its a file, path by default leads to the containing directory, not the file
* this behaviour can be changed in config by setting `file_manager_receives_file_path` to `true`
* there are exceptions ignoring this setting because they can select/highlight the file
* currently it's dolhpin, nemo, nautilus, doublecmd
* without any changes to the config, `xdg-open` is used to detect default file manager
* `number_of_results` sets how many items are retrieved from the database per key press, 500 default
