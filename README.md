# ANGRYsearch
Linux file search, instant results as you type

Attempt at making Linux version of Everything Search Engine, or MasterSeeker, or Hddb File Search, because no one else bothered.
Everyone seems to be damn content with linux file searches which are slow, populating results as they go, cli based only, heavily integrated with a file manager, limited to home directory, or are trying to be everything with full-text file's content search.

![demonstration gif](http://i.imgur.com/nQO5yVM.gif)

Done in python 3, using PyQt5 for GUI, theres a PyQt4 branch

### What you should know:

* by default the search results are bound to the beginning of the words presented in the names
* it would not find "Pi<b>rate</b>s" or Whip<b>lash</b>", but it would "<b>Pir</b>ates" or "The-<b>Fif</b>th"
* unchecking the checkbox in the top right corner fixes this, but searching gets slower
* database is in ~/.cache/angrysearch/angry_database.db
* it can take ~4 min to index ~1 mil files and the database might be ~300MB in size
* do not recommend to run as root, there's no reason for it and you might crawl where you would rather not, like Btrfs users going in to snapshots

### How to make it work on your system:

* Arch has [AUR package](https://aur.archlinux.org/packages/angrysearch/), so we are done here

for other distros:

**dependencies** - `python-pyqt5`, `libxkbcommon-x11`, `sudo`, `xdg-utils`
  * most of these you very likely have, except PyQt5, so get it
  * for example for ubuntu based ditros: `sudo apt-get install python3-pyqt5`

**download the latest release** of ANGRYsearch, unpack it, go in to the containing directory
* **if you just want to test it, you can run it right away**
  * `python3 angrysearch.py`
  * once you are done testing, remember to remove the database that is created in
    `~/.cache/angrysearch/angry_database.db`

for a long term installation on your system for every day use we need to place the files somewhere,
long story short, all the files and the icons-folder go in to `/opt/angrysearch`, set two of them executable
and make some links to these files to integrate ANGRYsearch in to your system well.

* create angrysearch folder in /opt

        sudo mkdir /opt/angrysearch

* go where you downloaded latest release, go deeper inside, copy all the files and the icons folder to /opt/angrysearch

        sudo cp -r * /opt/angrysearch

* make the main python file and the desktop file executable

        cd /opt/angrysearch
        sudo chmod +x angrysearch.py angrysearch.desktop

* make a link in /usr/share/applications to the desktop file so that angrysearch appears in your launchers and start menus

        sudo ln -s /opt/angrysearch/angrysearch.desktop /usr/share/applications

* would be nice if it would have some distinguishable icon, make a link to the icon

        sudo ln -s /opt/angrysearch/icons/angrysearch.svg /usr/share/pixmaps

* to be able to run angrysearch from terminal anywhere by just writing `angrysearch` , make this link

        sudo ln -s /opt/angrysearch/angrysearch.py /usr/bin/angrysearch


### How it works & additional details:

* on update it crawls through your file system and creates database in `~/.cache/angrysearch/angry_database.db`
* database uses FTS4 for indexing to provide instantaneous feel - results as you type
* drawback of this indexing is inability to do substring searches, but the checkbox in the top right corner can change this. If it's unchecked it will not use FTS4 tables and just do regular slow database search query with substrings as well
* **double-click** on items in search results:
  * `Name` - the first column, opens the file in application associated with its mimetype in xdg-open
  * `Path` - the second column, open the item's location in the file manager
* **config file** location: `~/.config/angrysearch/angrysearch.conf`. You can delete the config file whenever you wish, on the next run/close a new one will be created with default values.
  *   `directories_excluded=` By default empty. Which directories to be ignored, directory names(not slashes) separated by space are valid value there. Can be set through program's interface, in the update window. Directory `proc` is hardcoded to ignore
  *   `fast_search_but_no_substring=true` By default set to true. It holds the last set value of the checkbox affecting the speed of search and substrings, see FTS4 in the section above
  *   `file_manager=xdg-open` By default set to xdg-open, meaning xdg-open tests which program is associated with inode/directory mime type and on double clicking the path of files/folders is send to that application. Can be set to any program. If it detects one of the following file managers ['dolphin', 'nemo', 'nautilus', 'doublecmd'], it will change behaviour slightly, sending to those file managers full path to the file, making it highlighted - selected when opened in the filemanager. For other programs it just send path to the containing foler.
  *   `icon_theme=adwaita` By default set to adwaita. Which icon theme to use, can be set from program's interface in the update window. There are 6 icon types - folder, file, audio, image, video, text. Did not yet figured out how to get theme of the distro and reliably icon from file's mimetype, so packing icons with the angrysearch is the way.
  *   `number_of_results=500` By default set to 500. Limit set in the database query. Lower number means search results would be faster.
  *   `row_height=0` By default set to 0 which means auto-detect. Sets height of the row in pixels.
  *   `[Last_Run]` The applications properties from the last time it was launched. Window size, position, state.

* results can be sorted by clicking on columns, only the presented results will be sorted, meaning that by default max 500 items. To return to the default sort, sort by path column.

