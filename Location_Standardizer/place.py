import sys
from pathlib import Path
from sqlite3 import Connection, Row
from collections import defaultdict
import logging

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore

logger = logging.getLogger(__name__)

class Place:
    def __init__(
        self, name: str, rmid: int = 0, start_year: int = None, end_year: int = None
    ):
        self.name = name
        self.rmid = rmid
        if not start_year and not end_year:
            logger.warn(f"{name} has no start or end year, will be used for all time/events.")

        self.start_year = start_year
        self.end_year = end_year


class PlaceGroup:
    def __init__(
        self,
        places: list[Place],
        search_strings: list[str],
        exclude_strings: list[str] = list(),
    ):
        self.places = places
        self.search_strings = search_strings
        self.exclude_strings = exclude_strings

    def get_place_ids(self, conn: Connection):
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

    def fix_events(
        self, conn: Connection, search_strings=list(), exclude_strings=list()
    ):
        """
        Args:
            conn: Connection open sqlite3.Connection object
            search_strings: list[str] Optional list of strings to override the strings defined
            in this PlaceGroup
            exclude_strings: list[str] Optional list of strings to override the exclude strings
            defined in this place group.
        """
        sql_base = """\
SELECT et.EventID, pt.Name, et.PlaceID
    FROM EventTable as et
    INNER JOIN PlaceTable as pt USING (PlaceID)
    WHERE et.PlaceID != ? 
    AND et.Date != '.'
    AND cast(substr(et.date, 4, 4) as integer) <cond>
    AND ("""

        def build_date_query(sql, place: Place):
            if place.start_year and place.end_year:
                return sql.replace("<cond>", "between ? and ?")
            elif place.start_year:
                return sql.replace("<cond>", ">= ?")
            elif place.end_year:
                return sql.replace("<cond>", "< ?")
            else:
                logger.warn(f"{place.name} has no start or end year set, will be used for all time")
                return sql.replace("<cond>", "")

        def add_filter_strings(sql, search_strings, exclude_strings):
            sql += " OR ".join(["pt.Name LIKE ?"] * len(search_strings))
            sql += ")"

            if exclude_strings:
                sql += (
                    "\n    AND ("
                    + " AND ".join(["pt.Name NOT LIKE ?"] * len(exclude_strings))
                    + ")"
                )

            return sql

        def get_years_list(place: Place):
            years = []
            if place.start_year:
                years.append(place.start_year)
            if place.end_year:
                years.append(place.end_year)
            return years

        # Override search_strings in function call
        if len(search_strings) == 0:
            search_strings = self.search_strings
        # place.exclude_strings is optional, so could override, define, or do nothing
        if len(exclude_strings) == 0:
            exclude_strings = self.exclude_strings

        for place in self.places:
            sql = build_date_query(sql_base, place)
            sql = add_filter_strings(sql, search_strings, exclude_strings)

            params = (
                [place.rmid]                           # et.Place = ?
                + get_years_list(place)                # ? < date[4:8] < ?
                + [f"%{s}%" for s in search_strings]   # pt.Name like ? ..
                + [f"%{s}%" for s in exclude_strings]  # pt.Name not like ? ..
            )

            cur = conn.execute(sql, params)
            rows = cur.fetchall()

            if (len(rows)) > 0:
                self.update_events(conn, place, rows)
            else:
                print(f"No events found {self._date_string(place)} for {place.name}")

    def _date_string(self, place: Place):
        dates = (place.start_year, place.end_year)
        match dates:
            case (None, e):
                return f"before {e}"
            case (s, None):
                return f"after {s}"
            case (s, e):
                return f"between {s} and {e}"

    def update_events(self, conn: Connection, place: Place, rows: list[Row]):
        old_names = {}
        named_events = defaultdict(list)
        for r in rows:
            named_events[r[1]].append(r[0])
            old_names[r[1]] = r[2]

        print(
            f"Updating {len(rows)} events {self._date_string(place)} with the following places to '{place.name}':"
        )
        for i, n in enumerate(named_events.keys()):
            print(f"{i+1}. {n}")
        resp = input(
            "Any locations to skip (comma separated list) [Enter to fix all/0 to fix none]? "
        )
        if resp == "0":
            return

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

        sql = f"""\
UPDATE EventTable
    SET PlaceID = ?
    WHERE EventID in ({','.join(['?'] * len(event_ids))})
"""
        conn.execute(sql, [place.rmid] + event_ids)

        # self._delete_old_places(conn, list(old_names.keys()))

    def _delete_old_places(self, conn: Connection, place_ids: list[int]):
        delete = input("Delete original places [y/N]? ")
        if delete.lower() == "y":
            sql = f"DELETE FROM PlaceTable WHERE PlaceID in ({','.join(['?'] * len(place_ids))})"
            conn.execute(sql, place_ids)

