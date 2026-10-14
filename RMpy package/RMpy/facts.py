import sys
from pathlib import Path
sys.path.append(str(Path.resolve(Path(__file__).resolve().parent)))
import common as RM
from sqlite3 import Connection

class Fact:
    def __init__(
            self,
            name: str,
            owner: RM.OwnerType = RM.OwnerType.PERSON,
            abbrev: str = "",
            gedcomTag: str = "EVEN",
            use_value: bool = True,
            use_date: bool = True,
            use_place: bool = True,
            sentence: str = "",
            **kwargs
    ):
        self.owner = owner
        self.name = name
        self.abbrev = abbrev
        self.gedcomTag = gedcomTag
        self.use_value = int(use_value)
        self.use_date = int(use_date)
        self.use_place = int(use_place)
        self.sentence = sentence
        self.id = None
        if len(kwargs) == 0:
            self.flags = 2147483647
        else:
            self.flags: int = ~(64 + ~(
                kwargs.get('to_gedcom', True) << 0
                | kwargs.get('to_web', True) << 1
                | kwargs.get('to_fgs', True) << 2
                | kwargs.get('to_narr', True) << 3
                | kwargs.get('to_indiv', True) << 4
                | kwargs.get('to_lists', True) << 5
            ))

    def get_id(self, conn: Connection):
        if not self.id:
            sql = "SELECT FactTypeID from FactTypeTable where Name = ?"
            self.id = RM.get_first(conn.execute(sql, (self.name,)), "Fact Type", "ID")
        return self.id

    def create(self, conn: Connection):
        sql="""\
INSERT INTO FactTypeTable (
    OwnerType, Name, Abbrev, GedcomTag, UseValue, UseDate, UsePlace, Sentence, Flags, UTCModDate
)
VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?, ?, julianday('now') - 2415018.5
)
"""
        res = conn.execute(sql, (
            self.owner,
            self.name,
            self.abbrev,
            self.gedcomTag,
            self.use_value,
            self.use_date,
            self.use_place,
            self.sentence,
            self.flags
        ))
        self.id = RM.get_first(res, "FactType", "ID")
        return self.id

class Event:
    def __init__(
        self,
        fact_type: Fact,
        owner_type: RM.OwnerType,
        owner_id: int,
        **kwargs
    ):
        self.fact_type = fact_type
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.params = kwargs
        self.id = None

    def create(self, conn: Connection):
        sql="""\
INSERT INTO EventTable (
    EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate, IsPrimary, IsPrivate, Proof, Status, Sentence, Details, Note, UTcModDate
)
VALUES (
    ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, "", ?, ?, julianday('now') - 2415018.5
)
"""
        values = [
            self.fact_type.get_id(conn),
            self.owner_type,
            self.owner_id,
            self.params.get('place_id', 0),
            self.params.get('site_id', 0),
            self.params.get('date', ""),
            self.params.get('sort_date', 9223372036854775807),  # Highest number sorts event to the bottom of the list by default
            self.params.get('is_primary', 0),
            self.params.get('is_private', 0),
            self.params.get('proof', ""),
            self.params.get('status', ""),
            self.params.get('sentence', ""),
            self.params.get('details', "")
        ]
        res = conn.execute(sql, values)
        self.id= res.lastrowid
        if self.id:
            return self.id

    def get_id(self, conn: Connection):
        if not self.id:
            sql="SELECT EventID from EventTable WHERE EventType = ? AND OwnerType = ? AND OwnerID = ?"
            res = conn.execute(sql, (self.fact_type.get_id(conn), self.owner_type, self.owner_id))
            self.id = RM.get_first(res, "Event", "ID")
        return self.id
