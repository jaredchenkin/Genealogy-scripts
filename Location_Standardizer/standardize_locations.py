import sys
from pathlib import Path
from sqlite3 import Connection
import signal

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
from place import Place, PlaceGroup


def sigint_handler(sig, frame):
    print("")
    sys.exit(1)

signal.signal(signal.SIGINT, sigint_handler)

DEBUG = False

# ====================================================
## Hardcoded to the known good place ids in my prod database
## TODO: Perhaps dynamically find/create the place instead of hardcoding PlaceID
dvinsk = PlaceGroup(
    places=[
        Place("Dinaburg, Grand Duchy of Lithuania", 6361, 1667, 1802),
        Place("Dinaburg, Daugavpils, Vitebsk, Russian Empire", 6611, 1802, 1893),
        Place("Dvinsk, Dvinsk, Vitebsk, Russian Empire", 6608, 1893, 1917),
        Place("Daugavpils, Latvia, Soviet Union", 6612, 1917, 1991),
        Place("Daugavpils, Latvia", 950, 1991),
    ],
    search_strings=["Dinaburg", "Dvinsk", "Dunaburg", "Daugavpils"],
    exclude_strings=[
        "Glazmanka",
        "Vishki",
        "Krustpils",
        "Līvāni",
        "Višķi",
        "Preiļi",
        "Grīva",
        "Dagdas",
        "Jēkabpils",
        "Krāslava",
        "Latgale",
        "Danker",
    ],
)

punsk = PlaceGroup(
    places=[
        Place("Puńsk, Troki, Grand Duchy of Lithuania", 7186, end_year=1795),
        Place(
            "Puńsk, Białystok, New East Prussia, Kingdom of Prussia", 7187, 1795, 1806
        ),
        Place("Puńsk, Sejny, Łomża, Duchy of Warsaw", 7188, 1807, 1815),
        Place("Puńsk, Augustów, Kingdom of Poland, Russian Empire", 305, 1816, 1866),
        Place(
            "Puńsk, Suwałki, Suwałki, Kingdom of Poland, Russian Empire", 2178, 1867, 1917
        ),
        Place("Puńsk, Sejny, Białystok, Poland", 2758, 1918, 1975),
        Place("Puńsk, Suwałki, Poland", 284, 1975, 1999),
        Place("Puńsk, Sejny, Podlaskie, Poland", 1006, 1999),
    ],
    search_strings=["punsk", "puńsk"],
)

augustow = PlaceGroup(
    places=[
        Place("Augustów, Podlaskie, Kingdom of Poland", 5603, 1569, 1795),
        Place(
            "Augustów, Białystok, New East Prussia, Kingdom of Prussia", 302, 1795, 1806
        ),
        Place("Augustów, Dąbrowa, Łomża, Duchy of Warsaw", 301, 1807, 1815),
        Place("Augustów, Suwałki, Kingdom of Poland, Russian Empire", 2197, 1816, 1917),
        Place("Augustów, Augustów, Białystok, Poland", 235, 1918, 1975),
        Place("Augustów, Suwałki, Poland", 7204, 1975, 1999),  # TODO
        Place("Augustów, Augustów, Podlaskie, Poland", 7205, 1999),  # TODO
    ],
    search_strings=["augustow", "Augustów"],
    exclude_strings=["punsk", "Puńsk", "sejny", "krasnopol"],
)

suwalki = PlaceGroup(
    places=[
        Place("Suwałki, Augustów, Kingdom of Poland, Russian Empire", 6427, 1816, 1866),
        Place(
            "Suwałki, Suwałki, Suwałki, Kingdom of Poland, Russian Empire", 4322, 1867, 1917,
        ),
        Place("Suwałki, Białystok, Poland", 1220, 1918, 1999),
        Place("Suwałki, Podlaskie, Poland", 1237, 1999),
    ],
    search_strings=["suwalki", "Suwałki"],
    exclude_strings=["pu_sk", "sejny", "krasnopol", "klonorejsc", "filip_w"],
)

sejny = PlaceGroup(
    places=[
        Place(
            "Sejny, Białystok, New East Prussia, Kingdom of Prussia", 7207, 1795, 1806
        ),
        Place("Sejny, Sejny, Łomża, Duchy of Warsaw", 7206, 1807, 1815),
        Place(
            "Sejny, Sejny, Augustów, Kingdom of Poland, Russian Empire",5978,1816,1866,
        ),
        Place(
            "Sejny, Sejny, Suwałki, Kingdom of Poland, Russian Empire", 4047, 1867, 1917
        ),
    ],
    search_strings=["sejny"],
    exclude_strings=["pu_sk"],
)

krasnopol = PlaceGroup(
    places=[
        Place("Krasnopol, Podlaskie, Kingdom of Poland", 5200, 1569, 1795),
        Place(
            "Krasnopol, Białystok, New East Prussia, Kingdom of Prussia", 1585, 1795,
            1806,
        ),
        Place("Krasnopol, Dąbrowa, Łomża, Duchy of Warsaw", 2259, 1807, 1815),
        Place(
            "Krasnopol, Augustów, Kingdom of Poland, Russian Empire", 6896, 1816, 1867
        ),
        Place(
            "Krasnopol, Sejny, Suwałki, Kingdom of Poland, Russian Empire", 458, 1867, 1914,
        ),
        Place("Krasnopol, Suwałki, Białystok, Poland", 5979, 1918, 1956),
    ],
    search_strings=["krasnopol"],
)

brooklyn = PlaceGroup(
    places=[
        Place("Brooklyn, Kings, New York, United States", 5955, 1776, end_year=1898),
        Place(
            "Brooklyn, New York City, New York, United States", 5879, start_year=1898
        ),
    ],
    search_strings=["brooklyn%new york"],
    exclude_strings=["cemetery"],
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
        brooklyn.fix_events(conn)


# ===================================================DIV60==
# Call the "main" function
if __name__ == "__main__":
    main()

# ===================================================DIV60==
