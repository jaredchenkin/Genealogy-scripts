import sys
from pathlib import Path
from sqlite3 import Connection, Row
import signal
from collections import defaultdict
sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore


def sigint_handler(sig, frame):
    print("")
    sys.exit(1)


signal.signal(signal.SIGINT, sigint_handler)



DEBUG = False

class Place:
    def __init__(
        self,
        name: str,
        rmid: int = 0,
        start_year: int = None,
        end_year:int = None
    ):
        self.name = name
        self.rmid = rmid
        if not start_year and not end_year:
            raise RM.RM_Py_Exception("need either start or end years")
        
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


    def fix_events(self, conn: Connection, search_strings=list(), exclude_strings=list()):
        def build_query(sql_base, place, search_strings, exclude_strings):
            ys = (place.start_year, place.end_year)
            match ys:
                case (s, None):
                    sql = sql_base.replace("<cond>", ">= ?")
                    years = [s]
                case (None, e):
                    sql = sql_base.replace("<cond>", "< ?")
                    years = [e]
                case (s,e):
                    sql=sql_base.replace("<cond>", "between ? and ?")
                    years = [s, e]

            sql += ' OR '.join(["pt.Name LIKE ?"] * len(search_strings))
            sql+=")"

            if exclude_strings:
                sql+="\n    AND (" + ' AND '.join(["pt.Name NOT LIKE ?"] * len(exclude_strings)) + ")"

            return sql,years

        if len(search_strings) == 0:
            search_strings = self.search_strings
        if len(exclude_strings) == 0:
            exclude_strings= self.exclude_strings

        sql_base="""\
SELECT et.EventID, pt.Name, et.PlaceID
    FROM EventTable as et
    INNER JOIN PlaceTable as pt USING (PlaceID)
    WHERE et.PlaceID != ? 
    AND et.Date != '.'
    AND cast(substr(et.date, 4, 4) as integer) <cond>
    AND ("""
        
        for place in self.places:
            sql, years = build_query(sql_base, place, search_strings, exclude_strings)

            params = [place.rmid] + years + [f"%{s}%" for s in search_strings]
            if exclude_strings:
                params += [f"%{s}%" for s in exclude_strings]

            cur = conn.execute(sql, params)
            rows = cur.fetchall()

            if (len(rows)) > 0:
                self.update_events(conn, place, rows)
            else:
                print(f"No events found {self._date_string(place)} for {place.name}")

    def _date_string(self, place: Place):
        dates = (place.start_year, place.end_year)
        match dates:
            case (None, e): return f"before {e}"
            case (s, None): return f"after {s}"
            case (s,e): return f"between {s} and {e}"

    def update_events(self, conn: Connection, place: Place, rows: list[Row]):        
        old_names = {}
        named_events = defaultdict(list)
        for r in rows:
            named_events[r[1]].append(r[0])
            old_names[r[1]] = r[2]

        print(f"Updating {len(rows)} events {self._date_string(place)} with the following places to '{place.name}':")
        for i,n in enumerate(named_events.keys()):
            print(f"{i+1}. {n}")
        resp = input("Any locations to skip (comma separated list) [Enter to fix all/0 to fix none]? ")
        if resp == "0":
            return
        
        skiplist = [int(t) - 1 for t in resp.split(',') if t.strip().isdigit() and int(t) >= 1]
        for i in skiplist:
            on = list(old_names.keys())
            if i < len(on):
                del named_events[on[i]]
                del old_names[on[i]]

        # Because python doesn't have list.flatten()
        event_ids = [x for xs in list(named_events.values()) for x in xs]

        sql=f"""\
UPDATE EventTable
    SET PlaceID = ?
    WHERE EventID in ({','.join(['?'] * len(event_ids))})
"""
        conn.execute(sql, [place.rmid] + event_ids)

        # self._delete_old_places(conn, list(old_names.keys()))

    def _delete_old_places(self, conn: Connection, place_ids: list[int]):
        delete= input("Delete original places [y/N]? ")
        if delete.lower() == 'y':
            sql = f"DELETE FROM PlaceTable WHERE PlaceID in ({','.join(['?'] * len(place_ids))})"
            conn.execute(sql, place_ids)

# ====================================================
## Hardcoded to the known good place ids in my prod database
## TODO: Perhaps dynamically find/create the place instead of hardcoding PlaceID
dvinsk = PlaceGroup(
    places=[
        Place("Dinaburg, Grand Duchy of Lithuania", 6361, 1667, 1802),
        Place("Dinaburg, Daugavpils, Vitebsk, Russian Empire", 6611, 1802, 1893),
        Place("Dvinsk, Dvinsk, Vitebsk, Russian Empire", 6608, 1893, 1917),
        Place("Daugavpils, Latvia, Soviet Union", 6612, 1917, 1991),
        Place("Daugavpils, Latvia", 950, 1991)
    ],
    search_strings=['Dinaburg', 'Dvinsk', 'Dunaburg', 'Daugavpils'],
    exclude_strings=['Glazmanka', 'Vishki', 'Krustpils', 'Līvāni', 'Višķi', 'Preiļi', 'Grīva', 'Dagdas', 'Jēkabpils', 'Krāslava', 'Latgale', 'Danker']
)

punsk = PlaceGroup(
    places=[
        Place("Puńsk, Troki, Grand Duchy of Lithuania", 7186, end_year=1795),
        Place("Puńsk, Białystok, New East Prussia, Kingdom of Prussia", 7187, 1795, 1806),
        Place("Puńsk, Sejny, Łomża, Duchy of Warsaw", 7188, 1807, 1815),
        Place("Puńsk, Augustów, Kingdom of Poland, Russian Empire", 305, 1816, 1866),
        Place("Puńsk, Suwałki, Suwałki, Kingdom of Poland, Russian Empire", 2178, 1867, 1917),
        Place("Puńsk, Sejny, Białystok, Poland", 2758, 1918,1975),
        Place("Puńsk, Suwałki, Poland", 284, 1975, 1999),
        Place("Puńsk, Sejny, Podlaskie, Poland", 1006, 1999)
    ],
    search_strings=['punsk', 'Puńsk'],
)

augustow = PlaceGroup(
    places=[
        Place("Augustów, Podlaskie, Kingdom of Poland", 5603, 1569, 1795),
        Place("Augustów, Białystok, New East Prussia, Kingdom of Prussia", 302, 1795, 1806),
        Place("Augustów, Dąbrowa, Łomża, Duchy of Warsaw", 301, 1807, 1815),
        Place("Augustów, Suwałki, Kingdom of Poland, Russian Empire", 2197, 1816, 1917),
        Place("Augustów, Augustów, Białystok, Poland", 235 , 1918, 1975),
        Place("Augustów, Suwałki, Poland",7204,1975,1999), # TODO
        Place("Augustów, Augustów, Podlaskie, Poland",7205,1999) # TODO
    ],
    search_strings=['augustow','Augustów'],
    exclude_strings=['punsk', 'Puńsk', 'sejny', 'krasnopol']
)

suwalki = PlaceGroup(
    places=[
        Place("Suwałki, Augustów, Kingdom of Poland, Russian Empire", 6427, 1816, 1866),
        Place("Suwałki, Suwałki, Suwałki, Kingdom of Poland, Russian Empire", 4322, 1867, 1917),
        Place("Suwałki, Białystok, Poland", 1220, 1918, 1999),
        Place("Suwałki, Podlaskie, Poland", 1237, 1999)
    ],
    search_strings=["suwalki", "Suwałki"],
    exclude_strings=['pu_sk', 'sejny', 'krasnopol', 'klonorejsc','filip_w']
)

sejny = PlaceGroup(
    places=[
        Place("Sejny, Białystok, New East Prussia, Kingdom of Prussia", 7207, 1795, 1806),
        Place("Sejny, Sejny, Łomża, Duchy of Warsaw", 7206, 1807, 1815),
        Place("Sejny, Sejny, Augustów, Kingdom of Poland, Russian Empire", 5978, 1816, 1866),
        Place("Sejny, Sejny, Suwałki, Kingdom of Poland, Russian Empire", 4047, 1867, 1917)
    ],
    search_strings=['sejny'],
    exclude_strings=['pu_sk']
)

krasnopol = PlaceGroup(
    places=[
        Place("Krasnopol, Podlaskie, Kingdom of Poland", 5200, 1569, 1795),
        Place("Krasnopol, Białystok, New East Prussia, Kingdom of Prussia", 1585, 1795, 1806),
        Place("Krasnopol, Dąbrowa, Łomża, Duchy of Warsaw", 2259, 1807, 1815),
        Place("Krasnopol, Augustów, Kingdom of Poland, Russian Empire", 6896, 1816, 1867),
        Place("Krasnopol, Sejny, Suwałki, Kingdom of Poland, Russian Empire", 458, 1867, 1914),
        Place("Krasnopol, Suwałki, Białystok, Poland", 5979, 1918, 1956)
    ],
    search_strings=['krasnopol']
)

brooklyn = PlaceGroup(
    places=[
        Place("Brooklyn, Kings, New York, United States", 5955, end_year=1898),
        Place("Brooklyn, New York City, New York, United States", 5879, start_year=1898)
    ],
    search_strings=['brooklyn%new york'],
    exclude_strings=['cemetery']
)
places = [krasnopol, suwalki, augustow, punsk, dvinsk]

def fix_all(conn: Connection):
    for place in places:
        place.fix_events(conn)

# ====================================================

def main():
    config = RM.get_config()
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        # fix_all(conn)
        krasnopol.fix_events(conn)

# ===================================================DIV60==
# Call the "main" function
if __name__ == '__main__':
    main()

# ===================================================DIV60==
