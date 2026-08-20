# Genealogy-scripts and utilities

Hi 👋 I'm Jared and I've forked Richard's repo so I can make some customized workflows for my RM database.
Having all of this work to use as inspiration is immensely helpful. Cheers! 🍻

I have done some small reorganizating to make things a bit more DRY and reusable for me.
A major organization change revolves around the fact that my first script was [`Lump-FS-Sources.py`](./Lump%20sources/Misc%20specific%20sources/Lump-FS-Sources.py),
which I modeled after the other Lump sources scripts in that directory.
Those scripts just run the main() function directly and bypass launcher.
That led me to move more connection handling and configuration logic into [`common.py`](./RMpy%20package/RMpy/common.py).
Now, the `create_db_connection` wraps the sqlite file handling directly, and utilizes python's context manager, so you can do:

```python
with create_db_connection(db_path, [RMNOCASE_Path]) as conn:
    do_stuff(conn, *other_args)
```

My scripts aren't as polished, and they aren't meant to be. Some are very specific with hardcoded stuff and not meant to be reused for anything else. Other's are maybe good for inspiration. Here is a current list of scripts I've written or files I've worked on:

```sh
📁 External_Sources
├─📄 make_website_citation.py
📁 FS_Person_Source
├─📄 get_fs_source.py
├─📄 make_fs_person_sources.py
📁 Location_standardizer
├─📄 place.py
├─📄 README.md
├─📄 standardize_locations.py
📁 Lump sources
├─📁 Misc specific sources
| ├─📄 Lump-FS-Sources.py
| └─📄 ReadMe-FS.md
📁 RMpy package
├─📁 RMpy
| ├─📄 common.py
| ├─📄 customizations.py
| └─📄 familysearch.py
├─📄 config.ini
└─📄 requirements.txt
```

## Config

One thing about the original setup was having config files in each directory, and having to change the database location
if you moved between folders. I made a helper method `get_config()` in `common.py` that looks for a `config.ini` in the repository root and returns the `ConfigParser` of that. After that, it looks for any .ini file in the directory of the running
script and merges that in. For ConfigParser, subsequent file reads overwrite prior configurations, so the local directory .ini
will have priority over the `$root/config.ini`. In my setup, since I'm on linux I have `prod.ini` and `test.ini` that I symlink to `config.ini`.

Now, back to @RichardOtter...

---

updated: 2025-11-21

These are scripts I've written to help my work with RootsMagic genealogy software.
They directly access the SQLite database used by RootsMagic (RM) to store its data.

Some are simple SQL in .sql txt files and there are several Python scripts.

The are tested only on Windows 11 x64 OS with Python 3.n Most have been tested only with RM v11 databases.
I don't have a MacOS computer to test with, but I'd guess that most could easily be ported. Let me know if you have any results.

"Released" scripts means that-

* The ReadMe file has enough guidance for even a novice user.
* All configuration is done through a configuration file so the python code does not need to be changed.
* All needed files are in a single zip archive for easy download.
* I've done significant amounts of testing.
* The release is version numbered.

The Release zip file is found in the Releases page, here on Github (https://github.com/ricko2001/Genealogy-scripts/releases)

If any of the other scripts are of interest, I may be persuaded to make them release-ready.
Let me know. I'm always interested in feedback.

## RELEASED

### Test external files

A utility to check status of external files linked to a RootsMagic file.\
This only reads the RM file. No changes are made.\
I find use of this app invaluable as part of my backup routine.

### Group from SQL

A utility to quickly update a RM group by running an SQL query.\
Makes changes only to GroupTable.

This includes-
RM -SQL for creating useful groups

As the name says, contains SQL that can be used by the GroupFromSQL utility.

### Color from Group

A utility to quickly update a the color coding of people in specified RM groups.\
Makes changes only to PersonTable.

### Change source for a Citation

A simple utility to fix a particular kind of data entry mistake. It moves a citation from one master source to another. It does lots of error checking to prevent further errors.

The fix that this utility makes is trivial in SQL, but this app takes information that is available in the RootsMagic user interface and does all of the look ups for you.

### Change source template

A utility to switch the source template used by one or a set of sources.\
Preserves all linkages and allows remapping of field data.\
This is the solution for modifying a SourceTemplate in use.

My process is to always run the script on a copy of the main database.
Then after iterating through fixes to the configuration file and I'm satisfied with
the results, I backup the main database and then move the copy with the changes done
by the script to the main database file location.

### Run SQL

This utility is meant to help the novice SQL user get the task done.
It attempts to eliminate most of the complications found using more
sophisticated off the shelf software.

This utility will run one or two SQL statements on a database and display the
results in a report file. It will also run a SQL command script. 

### Modify citation list

A utility to allow the user to hide citations both in the list of citations
attached to Persons, Names, or Facts and in reports generated.
Now that RM has direct support for changing the order of citations, that feature
in this app is less useful.
However the ability to hide citations (say a citation to a birth certificate index
when the actual birth certificate is cited) is still useful.
These hidden citations may be restored using this same app.
See [SQLiteTools site](https://sqlitetoolsforrootsmagic.com/forum/topic/sorting-the-order-of-rm9-citations/)
for a compatible SQL script that will update a  citations ordering in one step based on selected criteria.

### Convert Fact

Utility to change the fact type for a set of facts. For instance, convert all
"Census (fam)" facts with date 1940 to "Census" facts. Handles witnesses and Fam->Personal conversions.\
Probably most useful for projects imported from TMG, or when introducing a custom fact.

### Lump sources

I started in TMG as splitting all sources. Now in RM, I am lumping the sources for
which it makes sense to me. So far, Find_a_Grave, Census and Social Security SSDI,
newspaper articles, and all Ancestry collections. These scripts do that.
They will need modification for your circumstances. These are not released and
require Python development to run.

## NOT RELEASED

## Non Python

### Maintenance SQL

Consists of a SQL command file containing SQL updates that fix reoccurring problems
in my database caused by user errors during data entry.
There are parts of the script that are specific to my data entry practices.
Read it before you run it.
The Maintenance SQL has been run on my production database many times.

## NOTE-

I have a Github web site where I have links to these utilities and other RootsMagic related information.\
https://RichardOtter.github.io

# Python Packages used

## Required packages for running the scripts

My later releases use the custom "RMpy" python package located in the "RM -RMpy package" folder.
It is distributed in the zip file.

Those scripts using the package will find it if the folder structure is preserved. If the main
script is moved elsewhere, copy the "RMpy" folder to be in the same directory as the main script.

## Required packages for developing the scripts

NOTE: the following lines substitute "me" for your user name, and NNN for the python ver code.

The new PythonInstallManager handles things that had to be done manually in the past.

Python will be installed to-\
C:\Users\me\AppData\Local\Python\

For a new install or each major upgrade of python, do the following:

confirm pip is working by attempting to run it:/
py -m pip

Install these packages:

```text
py -m pip install --upgrade pip

py -m pip install --upgrade PyYAML

py -m pip install --upgrade wakepy
```

PyYAML is used by build scripts
wakepy is used in some long-running scripts to keep computer awake\

## The following packages are NO LONGER USED  They were used for building frozen executables (exe files)

``` text
pip install --upgrade pyinstaller

pip install --upgrade pyinstaller-versionfile
```

# RM Utilities Release Format Change

News as of 2024-12-10\
A new release format was necessitated by a problem I was not aware of until recently. People who have previously attempted to download the utilities have probably been warned that the zip file contained a virus or malware. I was just told about the problem by a user.

I want to state emphatically that none of the files ever posted on my GitHub site ever posed an actual hazard. A google search for "PyInstaller virus warning" shows the magnitude of the issue. It is clear that malware has been packaged with the same software distribution system I was used (PyInstaller). The anti virus companies then created file signatures that detected these threats. Unfortunately, it seems like every piece of software packaged has the same "signature". The PyInstaller created exe file distribution method was very practical as users did not need to install Python software.

The Internet has gotten to be a dangerous place, and it seems there are fewer and fewer methods for non-corporate software developers to distribute ready-to-run files.

This means that I have removed the "exe" format file from the release zip and the user must now install Python to run the scripts.

## Advantages to the New Release Format

* All apps are now in the same zip file. Perhaps this will encourage users to try an app they didn't know they needed.

* All apps are tested with each other using the same RMPy package (common code).

* Less effort maintaining one release than the previous nine.

* All of the software is human-readable. Each user can read the code and confirm that nothing bad is happening.
