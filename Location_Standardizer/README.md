# Location Standardizer

This module/script will search through your RootsMagic database file for places with
names that match given keywords and change the place to match a set of preconfigured
places based on the year of the event.

## Setup

`place.py` defines two object types, `Place` and `PlaceGroup`.
Place is a definition of a single RM place with standardized name and a range of valid dates.
`PlaceGroup` is the collection of Places that a query would use to sort events into, and has some query parameters.

Example:

```python
from .places import Place, PlaceGroup

brooklyn = PlaceGroup(
    places=[
        Place("Brooklyn, Kings, New York, United States", 5955, 1776, 1898),
        Place("Brooklyn, New York City, New York, United States", 5879, start_year=1898),
    ],
    search_strings=["brooklyn%new york"],
    exclude_strings=["cemetery"]
    )
```

## Place

`Place` takes 4 parameters:

1. A standardized place name (required)
1. ID of the place from the `PlaceTable` in RootsMagic. If missing, try to find or create the place (see below)
1. A start date for the place (optional)
1. An end date for the place (optional)

At least one date is requires.
If either date is missing or None, it means all dates on the opposite side of the given value.

### Find or create a place

If you don't provide an RM ID, Place will attempt to find it in the DB:

1. Looks for a place with the exact name.
1. If there are multiples, pick the one with a note (see below)
1. If none have a note, or more than 1 has a note, raise an exception

If none of those return a place, it will create one with the given place name
and add a note with the dates that this place is considered valid for.
The purpose there is twofold: as a reference for myself when I'm in the application
and as a discriminator if multiple place names exist, since a place name isnt a ubique field.

If it finds a place without a note, it will add it.

## PlaceGroup

Collect all of the places in a PlaceGroup.
The place group constructor also takes a search_string list and an exclude_string list.

search_strings is required and tells the group how to find existing places to sort through.

exclude_strings is an optional list of strings to further filter out places from the found list.

This doesn't have to be all inclusive, as we'll see below.

Each string is wrapped in `%`'s, so sqlite will search the whole field for the string.
But it still just goes into a `Name LIKE ?` clause, so you can add additional `%` or `_` wildcards as needed.
SQLite string queries are also default to case insensitive.
It's your database. No I'm not sanitizing any inputs.

## Using it

Pretty easy. Just pass a sqlite3.Connection object to PlaceGroup's fix_places() method and let it run. If it's using my config setup (Richard's will be different):

```python
config = RM.get_config()
database_Path = config["FILE_PATHS"]["DB_PATH"]
RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
    brooklyn.fix_events(conn)
```

```bash
$ ./bkln_fix.py
No events found between 1776 and 1898 for Brooklyn, Kings, New York, United States
Updating 1138 events after 1898 with the following places to 'Brooklyn, New York City, New York, United States':
1. Brooklyn Ward 26, Kings, New York, USA
2. ED 247 Borough of Brooklyn, Election District 14 New York City Ward 16, Kings, New York, United States
3. Brooklyn, A.D. 15, E.D. 17, Kings, New York
4. Brooklyn Ward 16, , New York
5. Brooklyn Assembly District 13, Kings, New York, United States
6. Brooklyn (Districts 0001-0250), Kings, New York, United States
[...]
Any locations to skip (comma separated list) [Enter to fix all/0 to fix none]? 
```

For each Place in the PlaceGroup, it looks for places that match the search_strings but not the exclude_strings.
Then it presents a list of every place found. This is where the exclude_strings list comes in - it doesn't have
to be exhaustive because you will always get the chance to skip locations at this point. Just maybe a couple
easy one's that you know won't make sense. For Brooklyn, since I have a lot of relatives buried there as well,
skipping anything with "cemetery" in the name seemed like a good idea.

(Maybe Brooklyn wasn't the best example, since I have every ward, district, and other census places...)

Follow the prompt - enter a comma separated list of numbers for places to skip, just hit Enter to do it all,
0 skips the place entirely.

`fix_events()` also takes lists of search_strings and exclude_strings if you want to override the ones 
configured in the PlaceGroup.

[`standardize_locations.py`](./standardize_locations.py) is my working file, examples there.
