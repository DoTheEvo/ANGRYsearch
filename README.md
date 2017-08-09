# ANGRYsearch
Linux file search, instant results as you type

Attempt at making Linux version of [Everything Search Engine](https://www.voidtools.com/) because no one else bothered.  
Everyone seems to be damn content with searches that are slow, populating results as they go; or are cli based, making it difficult to comfortably make use of the results; or are heavily integrated with a file manager, often limiting search to just home; or are trying to be everything with full-text file's content search.

*A similar project worth attention* - [FSearch](https://github.com/cboxdoerfer/fsearch)

![demonstration gif](http://i.imgur.com/BsjGoYz.gif)

Done in python 3 using PyQt5 for GUI

### Lite mode vs Full mode

angrysearch can be set to two different modes in its config, default being `lite`
* **lite mode** shows only name and path
* **full mode** shows also size and date of the last modification, the drawback is that crawling through drives takes roughly twice as long since every file and directory gets additional stats calls

in `~/.config/angrysearch/angrysearch.conf` you control the mode with `angrysearch_lite` being set to true or false

![lite version png](http://i.imgur.com/TS1fgTr.png)

### Search modes

there are 3 search modes, default being `fast`
* **fast mode** - enabled when the checkbox next to the input field is checked  
extremely fast, but no substrings, meaning it would not find "Pi<b>rate</b>s" or "Whip<b>lash</b>", but it would "<b>Pir</b>ates" or "The-<b>Fif</b>th"
* **slow mode** - enabled when the checkbox is unchecked, slightly slower but can find substrings, also very litteral with non typical characters
* **regex mode** - activated by the **F8** key, indicated by orange color background  
slowest search, used for very precise searches using [regular expressions](http://www.aivosto.com/vbtips/regex.html), set to case insensitive,  
unlike the previous search modes not entire path is searched, only the filenames/directory names

regex example:

![regex in action gif](http://i.imgur.com/6dEFvat.gif)


### What you should know:

* the database is in `~/.cache/angrysearch/angry_database.db`  
  the config file is in `~/.config/angrysearch/angrysearch.conf`  
* it can take ~2 min to index ~1 mil files, depending on hdd/ssd and filesystem - ntfs on linux being much slower. The database might be ~200MB
* it is **not recommended** to run as root, there's no reason for it and you might crawl where you would rather not, like Btrfs users going in to snapshots
* [xdg-open](https://wiki.archlinux.org/index.php/Default_applications#xdg-open) is used to open the files based on their mimetype, [default applications](http://i.imgur.com/u8jbi4e.png) can be set in `~/.local/share/applications/mimeapps.list` or `~/.config/mimeapps.list` 

### Installation:

* Arch Linux - [AUR package](https://aur.archlinux.org/packages/angrysearch/)
* openSUSE & Fedora [package](https://software.opensuse.org/package/angrysearch) (courtesy of [alanbortu](https://github.com/alanbortu))

![xubuntu installation demonstration](http://i.imgur.com/H9Uuxvp.png)

Manual installation is easy as there's no compilation with python, process consists of having dependencies, copying files somewhere and setting execution permissions  

**dependencies** - `python3-pyqt5`, `xdg-utils`  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;you need **PyQt5 for python3**, for example ubuntu based distros: `sudo apt install python3-pyqt5`  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;most distros have **xdg-utils** out of the box  

Now that you have the dependencies, download the latest [release of angrysearch](https://github.com/DoTheEvo/ANGRYsearch/releases) and unpack it somewhere. Along the files there's one called `install.sh`, it will copy files where they belong and sets correct permissions.

* open terminal in the directory with the release files
* set `install.sh` as executable and run it

        chmod +x install.sh
        sudo ./install.sh

* DONE, if you want to see more detailed instruction, [here](https://github.com/DoTheEvo/ANGRYsearch/tree/bf43e4e59da33ee3242d84074b0b4b3c9a6c9486#installation) is older version of this readme

**optional-dependencies**
  * [python3-gobject](https://wiki.gnome.org/Projects/PyGObject) - desktop notifications for automatic update, most DEs have it
  * [xdotool](https://www.semicomplete.com/projects/xdotool/xdotool.xhtml) - needed if using Thunar or PCmanFM and making use of the config option `fm_path_doubleclick_selects`

### Automatic update in the background

![notifications png](http://i.imgur.com/dudkCvZ.png)

Among the files there's `angrysearch_update_database.py`  
When this file is run there's no interface, it just crawls through drives and updates the database

Using [crontab](https://www.youtube.com/watch?v=UlVqobmcPuM) you can set this file to be executed periodically at chosen intervals,
keeping angrysearch up to date with the changes on your system

* `crontab -l` - list cronjobs
* `crontab -e` - open text editor so you can enter new cronjob

this cronjob will execute the update every 6 hours

    0 */6 * * * /usr/share/angrysearch/angrysearch_update_database.py

crontab does not try to catch up on a job if the PC has been off during scheduled time

`notifications` setting turns on/off desktop notifications informing about automatic update finishing  
`conditional_mounts_for_autoupdate` can prevent autoupdate from running if set mount points are not present

*Desktop notifications from cronjob not always work, so on your distro you might be without them*

### How it works & additional details:

![look in to the database](http://i.imgur.com/LuHZa3g.png)


* On update angrysearch crawls through your file system and creates its database.  
The database has a column containing full path to every file and directory found, another column indicates if the path is to a file or a directory. If `full mode` is enabled then there are also columns for the last modification date and for the size of files in bytes.
* When typing in to the search input the path column is searched for the occurrences of typed text and the rows containing them are shown.  
This is unlike other searches which usually look only through names of files/directories not their entire paths. This means that writing `books` will show all the items with the term "books" somewhere on their path instead of just in the name.  
On typical slow searches this would be too broad of a search with too many results, but the instantaneous nature of angrysearch allows to continue typing until the search is narrow enough.
* The database uses [FTS](https://sqlite.org/fts3.html) extension of sqlite for indexing to dramatically improve search speed and get the instantaneous feel - results as you type - `fast mode`  
Drawback of this indexing is inability to do substring searches, but the checkbox in the top right corner can change this. If it's unchecked it will not use FTS tables and just do regular slower database search query - `slow mode`
* In the `fast mode` quotation marks can be used to make exact searches: `'torrent'` would not include "torrents" in the results.
* `angrysearch.py` file alone is all that is needed for full functionality. But no special icons or dark theme.
* Hovering mouse over the update button will show how old is the database.
* **double-click** on the items in search results:
  * `Name` - the first column, opens the file in the application associated with its mimetype using xdg-open
  * `Path` - the second column, opens the item's location in the file manager
* Results can be sorted by clicking on column's headers, only the presented results will be sorted, meaning that by default max 500 items. To return to the default sort, sort by path column.
* Hotkeys
    * `F6` `ctrl+L` `alt+D` - focus search input
    * `Enter` in search input- jump to results
    * `Enter` in search results - open selected item in associated application
    * `shift+Enter` - open items location
    * `Tab` - cycle through UI elements
    * `shift-Tab` - cycle backward through UI elements
    * `arrow up` `arrow down` - navigate through search results
    * `Esc` `ctrl+Q` - exit the application
* FTS5 is the new version of the indexing extension of sqlite, most distros don't have it yet and are on FTS4. The systems that do have it get two additional benefits in the `fast mode`
    * can exclude from search results by using the minus sign: search `wav -home` would show all paths containing the word `wav` except the ones also containing `home`
    * ignorance of diacritic, search for `oko` would also show results like `ôko` `ókö` `Okǒ`  

  To check if FTS5 is available on your system - in update dialog window, hover mouse over the text `• creating new database`

### Configuration:

* **config file** location: `~/.config/angrysearch/angrysearch.conf`  
  You can delete the config file whenever you wish, on the next run/close a new one will be created with the default values.

![config file screenshot](http://i.imgur.com/dubEjtc.png)

  * `angrysearch_lite` By default set to true. In the lite mode theres only file name and path, no file size and no last modification date. Less informations but faster crawling through the drives
  * `close_on_execute` By default set to false. Closes angrysearch after opening a file or a path in a file manager
  * `conditional_mounts_for_autoupdate` By default empty. Purpose is to hold mount points that should be present when the database is being updated. If a mount is missing, automatic update through crontab will not run, but use system notification dialog to inform that paths set in this settings are not mounted. This prevents overwriting the database when not all drives are present. Values are system mount points, space separated.
  * `darktheme` By default set to false. If set true dark theme is used for the applications interface, as defined in the qdarkstylesheet.qss, also resource_file.py contains icons for dark theme
  *   `directories_excluded` By default empty. Which directories to be ignored. Just name of the directory will ignore every directory of that name, full path like `/var/cache/pacman/pkg/` ignores exactly that single folder, or parent/target for more easily targeting specific folder `pacman/pkg`. Can be set through program's interface, in the update window. Directory `/proc` is hard coded to be ignored
  *   `fast_search_but_no_substring` By default set to true. It holds the last set value of the checkbox affecting the speed of search and substrings, see FTS4 in the section above
  *   `file_manager` By default empty. Whatever application/script is put there, it receives the path when the path column is double-clicked. If left empty angrysearch will try to autodetect default file manager using xdg-utils. If one of the following file managers are set/detected: ['dolphin', 'nemo', 'nautilus', 'doublecmd'], the behavior will change slightly, sending to those file managers full path to the file, highlighting the target file when opened in a file manager.
  *   `fm_path_doubleclick_selects` By default set to false. Needs `xdotool` package, and preferably manually set file manager in config. When set to true, Thunar, PCmanFM and SpaceFM file managers will be able to open containing directory with the file selected
  *   `icon_theme` By default set to adwaita. Which icon theme to use, can be set from program's interface in the update window. There are 6 icon types - folder, file, audio, image, video, text. Did not yet figure out how to get theme of the distro and reliably icon from file's mimetype, so packing icons with the angrysearch is the way
  *   `notifications` By default set to true. Automatic periodic updates that are run on background using crontab will use desktop notification system to inform when crawling is done or if it was aborted because of missing mount points
  *   `number_of_results` By default set to 500. Limit set for searches in the database. Lower number means search results come faster
  *   `regex_mode` By default set to false. Enables regex search mode. F8 key toggles between true/false when running the application
  *   `row_height` By default set to 0 which means default system height. Sets height of the rows in pixels
  *   `typing_delay` By default set to false. If enabled, it introduces 0.2 second delay between the action of typing and searching the database. This will prevent unnecessary database queries when user is typing fast as there is waiting to finish typing. This can improve performance on slower machines, but on modern ones it might negatively affect the feel of instant responsiveness
  *   `[Last_Run]` The applications properties from the last time at the moment when it was closed - window size, position, state

![dark theme screenshot](http://i.imgur.com/E3Bs5fx.png)
