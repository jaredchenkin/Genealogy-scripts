# FamilySearch sources

## Getting Sources from Family Search

[`get_fs_source.py`](./get_fs_source.py) has a dependency on a python project called `getmyancestors`, which has FamilySearch login and a great data model for managing most important objects.
Since most of my work currently entails replicating the work I've been doing in FamilySearch over the past 8 or so years into my own personal tree and database,
I found that I wanted to customize some aspects of how RM imported things from FS and pushed to Ancestry, and how I wanted to handle various sources. This script pulls all the sources from FS for a person already synced in RM and prompts for which sources to copy over and what facts to attach them to. It's following conventions that I decided
I wanted to hold by that fit my needs for both capturing the information in my tree and pushing to Ancestry.

To use the script, then, I recommend setting up a [virtual environment](https://docs.python.org/3/library/venv.html):

```bash
$ pyton3 -m venv .venv
$ source .venv/bin/activate  # or activate.ps1 for PowerShell
$ pip install -U -r requirements.txt
```

After that, you only need to do the second step to access the dependencies. The other option is to manage the pip package globally (run the third command once), but python tends to discourage that.

## Creating a source linking back to FamilySearch

[`make_fs_person_sources`](./make_fs_person_sources.py) makes sure that everyone in the database who is associated
with a FamilySearch ID/person has a source attached to the Person with the link back to FS. This is so that I
(and any one else interested) can easily go to the FS person for potentially more information than what I have here.
I'm not going to keep my Ancestry subscription forever, so at some point FS might be where the best sources are.
Like I said, a lot of this is me migrating my work from FS over to a personal tree in Ancestry.
