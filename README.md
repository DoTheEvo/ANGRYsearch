# ANGRYsearch
Linux file search, instant results as you type

Attempt at making Linux version of Everything Search Engine, or MasterSeeker, or Hddb File Search, because no one else bothered.
Everyone seems to be damn content with linux file searches which are slow, populating results as they go, cli based only, heavily integrated with a file manager, limited to home directory, or are trying to be everything with full-text content search.

![demonstration gif](http://i.imgur.com/nQO5yVM.gif)

Done in python 3, using PyQt5/PySide for GUI

### What you should know:

* unfortunately search results are bound to the beginning of the words present in the name, **no substring search**
* so a search for the word - "finite" would not include the results that have in the path word - "infinite"
* previous versions used data from the linux "locate" command, now the data are gathered by python itself
* it's slower, but allows to differentiate between file vs directory

### Install scandir for much faster indexing of your drives

* it will be part of python 3.5 by default but we are not there yet
* get python-pip, its a package manager for python
  * for arch: `sudo pacman -S python-pip`
  * for ubuntu based distros: `sudo apt-get install python3-pip`
  * for fedora and such: `yum -y install python3-pip`
* then install scandir through pip
  * `sudo pip install scandir`
  * maybe `sudo pip3 install scandir`
* if you want to test if its installed correctly
* write `python` or `python3` in to terminal
* you will enter python enviroment informing you of the version
* write `import scandir`
* you should just get moved to a new line, if you get error something is wrong
* ctrl+D to exit python

### How to make it work on your system:

* Arch has [AUR package](https://aur.archlinux.org/packages/angrysearch/), so you can install it from there
* for other distros
* we will be using `install` command because in a single line it can copy, create directories and set permissions
* download the latest release, unpack it, go in to the containing directory
* copy angrysearch.py in to /usr/share/angrysearch/angrysearch.py and make it executable
* `install -Dm755 angrysearch.py "/usr/share/angrysearch/angrysearch.py"`
* copy the icon - angrysearch.svg in to /usr/share/pixmaps/
* `install -Dm644 angrysearch.svg "/usr/share/pixmaps/angrysearch.svg"`
* now is the time to check your python version, since ANGRYsearch is done in python 3
  * `python --version` if the answer is Python 2.7.6 or similar check python3
  * `python3 --version` this should give you Python 3.4.0 or such, if thats the case we need to edit angrysearch.desktop file
* open angrysearch.desktop in editor of your choice find the line: `Exec=python /usr/share/angrysearch/angrysearch.py`
* change it to `Exec=python3 /usr/share/angrysearch/angrysearch.py`
* this edit was only needed to be done if `python --version` returned 2.7.6 or similar
* copy the desktop file - angrysearch.desktop in to /usr/share/applications/
* `install -Dm644 angrysearch.desktop "/usr/share/applications/angrysearch.desktop"`
* allright, all 3 files are positioned, now for dependencies
* PyQt5 is needed, so get it, for example ubuntu, mint and other debian based distros
* `sudo apt-get install python3-pyqt5`
* after this you should be able to run ANGRYsearch from your application launcher

### How it works:

* on update it crawls through your file system and creates database in /var/lib/angrysearch/
* then its available for search, returning 500 results per query
* config file location: `~/.config/angrysearch/angrysearch.conf`
* [file manager](http://i.imgur.com/KDjbqOW.png) with which to open results can be set there
* on double-click or enter the `file_manager` gets executed with path as parameter
  * if its a directory it gets path directly to that directory
  * if its a file, path by default leads to the containing directory, not the file
* this behavior can be changed in the config by setting `file_manager_receives_file_path` to `true`
* now whatever program you have set as the file manager will get executed with the full path
* there are exceptions ignoring this setting because they can select/highlight the file
* currently it's dolhpin, nemo, nautilus, doublecmd
* without any changes to the config, `xdg-open` is used to detect the default file manager
* `number_of_results` sets how many items are retrieved from the database per key press, 500 default

### KDE visual issues:

Since introducing the bold text highlighting searched phrase in the results, KDE is causing some trouble with the correct text positioning.
Will try to solve this eventually, but for now just a way to fix it individually on KDE user's machines

* as root open in editor of your choice: `/usr/share/angrysearch/angrysearch.py`
* path might be different if you just downloaded package and run it from wherever
* search for `textRect`
* you will find this line of code: `#textRect.adjust(0, 0, 0, 0)`
* delete `#` to allow that line to influence the program
* change the second zero to value `-3` or whatever looks correct to you
* after you are done it should be `textRect.adjust(0, -3, 0, 0)`
* save and run ANGRYsearch to check if it helped

![KDE text irregularity example](http://i.imgur.com/7XysGGY.gif)
