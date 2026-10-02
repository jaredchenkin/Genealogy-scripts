import sys
from pathlib import Path
from sqlite3 import Connection, Cursor, Row
from collections import defaultdict
from datetime import date
import logging

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore

logger = logging.getLogger(__name__)

class Place:
    def __init__(
        self, name: str, rmid: int = 0, start_date: str = None, end_date: str = None
    ):
        """
        A date-specific standardized place

        Args:
            name (str): Standardized place name
            rmid (int): ID of the place in the RM database that corresponds to the given place
            start_date (str|None): [Optional] Date to start considering the place valid in YYYY-mm-dd format
                Month and day are optional, but if you provide a day you must provide a month as well
                (The 4th of 2005 doesn't make sense anyway...).
            end_date (str|None): [Optional] See start_date
        """
        def date_normalize(date_string, end=False):
            if date_string != None:
                parts = date_string.split('-')
                defaults = ['13', '32'] if end else ['00', '00']
                return '-'.join(parts + defaults[len(parts) - 1:])

        self.name = name
        self.rmid = rmid

        if not start_date and not end_date:
            logger.warning(f"{name} has no start or end year, will be used for all time/events.")
        self.start_date = date_normalize(start_date)
        self.end_date = date_normalize(end_date, True)


class PlaceGroup:
    def __init__(
        self,
        places: list[Place],
        search_strings: list[str],
        exclude_strings: list[str] = list(),
    ):
        """
        A group of standardized Places to update in RootsMagic

        Args:
            places (list[Place]): All the places to process for this group
            search_strings (list[str]): [Optional] Strings to use when finding places in RM to standardize
            exclude_strings (list[str]): [Optional] Strings to exclude from search results
        
        """
        self.places = places
        self.search_strings = search_strings
        self.exclude_strings = exclude_strings

    def fix_events(
        self, conn: Connection, search_strings=list(), exclude_strings=list()
    ):
        """
        Processes the places in this PlaceGroup according to the dates of each place and strings provided
        Note: It does not consider if the event date has any qualifiers or is a range, it simply works off the 
            first (left most) date in the date field (so "between 1800 and 1830" will use 1800 as the comparison date)

        Args:
            conn (sqlite3.Connection): Connection open sqlite3.Connection object
            search_strings: list[str] Optional list of strings to override the strings defined
                in this PlaceGroup
            exclude_strings: list[str] Optional list of strings to override the exclude strings
                defined in this place group.
        """

        # Override search_strings in function call
        if len(search_strings) == 0:
            search_strings = self.search_strings
        # place.exclude_strings is optional, so could override, define, or do nothing
        if len(exclude_strings) == 0:
            exclude_strings = self.exclude_strings

        for place in self.places:
            (old_names, named_events) = self._find_events(conn, place, search_strings, exclude_strings)

            if (len(old_names)) > 0:
                (event_ids, old_place_ids) = self._pick_events(old_names, named_events)
                self._update_events(conn, place.rmid, event_ids)
                self._delete_old_places(conn, old_place_ids)


    def _find_events(self, conn, place, search_strings, exclude_strings):

        def build_date_query(place: Place):
            sql = "    AND "
            if place.start_date and place.end_date:
                sql += f'eventdate >= "{place.start_date}"\n' 
                sql += f'    AND eventdate <= "{place.end_date}"\n'
            elif place.start_date:
                sql += f'eventdate >= "{place.start_date}"\n'
            elif place.end_date:
                sql += f'eventdate <= "{place.end_date}"\n'
            else:
                sql = ""
            return sql

        def add_filter_strings(search_strings, exclude_strings):
            sql = "    AND ("
            sql += " OR ".join(["pt.Name LIKE ?"] * len(search_strings))
            sql += ")"

            if exclude_strings:
                sql += (
                    "\n    AND ("
                    + " AND ".join(["pt.Name NOT LIKE ?"] * len(exclude_strings))
                    + ")"
                )

            return sql
        
        sql_base = """\
SELECT et.EventID, pt.Name, et.PlaceID,
    SUBSTR(et.Date, 4, 4) || "-" || SUBSTR(et.Date, 8, 2) || "-" || SUBSTR(et.Date, 10, 2) as eventdate
FROM EventTable as et
INNER JOIN PlaceTable as pt USING (PlaceID)
WHERE et.PlaceID != ? 
    AND et.Date != '.'
    AND SUBSTR(et.Date, 1,1) NOT IN ("Q", "T")
"""
        sql = sql_base + build_date_query(place) + add_filter_strings(search_strings, exclude_strings)

        params = (
            [place.rmid]                           # et.Place = ?
            + [f"%{s}%" for s in search_strings]   # pt.Name like ? ..
            + [f"%{s}%" for s in exclude_strings]  # pt.Name not like ? ..
        )

        cur: Cursor = conn.execute(sql, params)
        rows: list[Row] = cur.fetchall()
        
        old_names = {}
        named_events = defaultdict(list)
        for r in rows:
            named_events[r["Name"]].append(r["EventID"])
            old_names[r["Name"]] = r["PlaceID"]

        if (len(rows) > 0):
            print(f"Found {len(rows)} events {self._date_string(place)} with the following places for converting to '{place.name}':")
        else:
            print(f"No events found {self._date_string(place)} for {place.name}")

        return (old_names, named_events)


    def _date_string(self, place: Place):
        def denormalize(s):
            parts = s.split('-')

            if parts[-1] == '00' or parts[-1] == '32':
                parts.pop()

            if parts[-1] == '00' or parts[-1] == '13':
                parts.pop()

            return '-'.join(parts)

        dates = (place.start_date, place.end_date)
        match dates:
            case (None, e):
                return f"before {denormalize(e)}"
            case (s, None):
                return f"after {denormalize(s)}"
            case (s, e):
                return f"between {denormalize(s)} and {denormalize(e)}"

    def _pick_events(self, old_names, named_events):
        for i, n in enumerate(named_events.keys()):
            print(f"{i+1}. {n}")
        resp = input(
            "Any locations to skip (comma separated list) [Enter to fix all/0 to fix none] ? "
        )
        if resp == "0":
            print(f"Skipping...")
            return ([], [])

        skiplist = [
            int(t) - 1 for t in resp.split(",") if t.strip().isdigit() and int(t) >= 1
        ]
        for i in skiplist:
            on = list(old_names.keys())
            if i < len(on):
                del named_events[on[i]]
                del old_names[on[i]]

        # Because python doesn't have list.flatten()
        event_ids = [x for xs in list(named_events.values()) for x in xs]
        return (event_ids, old_names.keys())


    def _update_events(self, conn, place_id, event_ids):
        sql = f"""\
UPDATE EventTable
    SET PlaceID = ?
    WHERE EventID in ({','.join(['?'] * len(event_ids))})
"""
        cur: Cursor = conn.execute(sql, [place_id] + event_ids)
        print(f"Update {cur.rowcount} events.")

    def _delete_old_places(self, conn: Connection, place_ids: list[int]):
        delete = input("Delete original places [y/N]? ")
        if delete.lower() == "y":
            sql = f"DELETE FROM PlaceTable WHERE PlaceID in ({','.join(['?'] * len(place_ids))})"
            conn.execute(sql, place_ids)

    # TODO
    def __get_place_ids__(self, conn: Connection):
        placeholders = ", ".join(["(?)"] * len(self.places))
        sql = f"""\
            WITH names(name) AS (
                VALUES {placeholders}
            )
            SELECT pt.id
            FROM names
            LEFT JOIN PlaceTable pt ON pt.name = names.name
            WHERE pt.Note != ''
            """
        rows = conn.execute(sql, [p.name for p in self.places])
        for place, row in zip(self.places, rows):
            if row[0] is None:
                pass
            else:
                place.id = row[0]
