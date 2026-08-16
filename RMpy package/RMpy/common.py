import configparser
import os
import sys
from pathlib import Path
from datetime import datetime
import sqlite3
from sqlite3 import Connection, DatabaseError
import ctypes
from contextlib import contextmanager
from typing import Any, Generator
import configparser
import enum
import xml.etree.ElementTree as ET
import itertools
import copy

# ===================================================DIV60==


@contextmanager
def create_db_connection(
    db_file_path, db_extension_file_path_list
) -> Generator[Connection, Any, None]:
    """Manages the RootsMagic database file object and tries to gracefully handle errors

    Args:
        db_file_path (str): Path to the database
        db_extension_file_path_list (list[str]): List of paths to any database extension files to load

    Yields:
        conn (sqlite3.Connection): The opened sqlite connection object
    """

    if not os.path.exists(db_file_path):
        print("Database path not found. Fix configuration file and try again.")
        return

    dbConnection = None
    try:
        dbConnection = sqlite3.connect(db_file_path)
        dbConnection.row_factory = sqlite3.Row
        dbConnection.autocommit = False
        if db_extension_file_path_list is not None:
            dbConnection.enable_load_extension(True)
            # load SQLite extensions
            for extension in db_extension_file_path_list:
                dbConnection.load_extension(str(extension))
        yield dbConnection
        dbConnection.commit()
    except DatabaseError as e:
        dbConnection.rollback()
        raise RM_Py_Exception(e, "\n\n" "SQLITE error." "\n")
    except Exception as e:
        dbConnection.rollback()
        raise e
    finally:
        dbConnection.close()


def get_config() -> configparser.ConfigParser:
    # Configuration file
    IniFile = str(Path.resolve(Path(__file__).resolve().parents[2] / "config.ini"))

    # ini file must be the project root directory and encoded as UTF-8 if non-ASCII chars present (no BOM)
    if not os.path.exists(IniFile):
        raise RM_Py_Exception("ERROR: Cannot find ini file: " + IniFile)

    config = configparser.ConfigParser()
    config.read(IniFile, "UTF-8")
    return config


# ===================================================DIV60==
def get_SQLite_library_version(dbConnection):

    # returns a string like 3.42.0
    SqlStmt = "SELECT sqlite_version()"
    cur = dbConnection.cursor()
    cur.execute(SqlStmt)
    return cur.fetchone()[0]


# ===================================================DIV60==
def time_stamp_now(type=None):

    # return a TimeStamp string
    now = datetime.now()
    if type is None:
        dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
    elif type == "file":
        dt_string = now.strftime("%Y-%m-%d_%H%M%S")
    return dt_string


# ===================================================DIV60==
def reindex_RMNOCASE(dbConnection):

    SqlStmt = "REINDEX RMNOCASE;"
    cur = dbConnection.cursor()
    cur.execute(SqlStmt, ())


# ===================================================DIV60==
def q_str(in_str):

    return '"' + str(in_str) + '"'


# ===================================================DIV60==
def get_bool_option(config, section_name, option_name, default=False):

    try:
        return config[section_name].getboolean(option_name)
    except (configparser.Error, KeyError, ValueError):
        return default


# ===================================================DIV60==
def launched_from_explorer():
    # Check how many processes are attached to the console
    arr = (ctypes.c_uint * 10)()
    count = ctypes.windll.kernel32.GetConsoleProcessList(arr, 10)

    # VS Code always sets TERM_PROGRAM=vscode
    in_vscode = os.environ.get("TERM_PROGRAM", "").lower() == "vscode"

    # Explorer launch: count == 2 AND not VS Code
    return count == 2 and not in_vscode


# ===================================================DIV60==
def pause_with_message(message=None):
    # Don't pause when running from a terminal or when input output is redirected
    if message != None:
        print(str(message))
    if launched_from_explorer():
        input("\n" "Press the <Enter> key to continue...")
    return


# ===================================================DIV60==
def get_current_directory(script_path: Path) -> Path:

    # Determine if application is a script file or frozen exe and get its directory
    # see   https://pyinstaller.org/en/stable/runtime-information.html
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        application_path = (Path(sys.executable)).parent
    else:
        application_path = script_path
    return application_path


# ===================================================DIV60==
class RM_Py_Exception(Exception):
    """Exceptions thrown for configuration/database/application logic issues"""


# ===================================================DIV60==


class OwnerType(enum.IntEnum):
    PERSON = 0
    FAMILY = 1
    EVENT = 2
    SOURCE = 3
    CITATION = 4
    PLACE = 5
    NAME = 7
    MEDIA = 11


class FieldType(enum.StrEnum):
    TEXT = "Text"
    NAME = "Name"
    PLACE = "Place"
    DATE = "Date"


class SourceTemplateField:
    def __init__(
        self,
        name: str,
        type: FieldType,
        display: str = None,
        citation: bool = False,
        hint: str = None,
        long_hint: str = None,
    ) -> None:
        self.name = name
        self.type = type
        self.display = display
        self.hint = hint
        self.long_hint = long_hint
        self.citation = citation

    def to_xml(self):
        field = ET.Element("Field")
        ET.SubElement(field, "FieldName").text = self.name
        ET.SubElement(field, "DisplayName").text = (
            self.display if self.display else self.name
        )
        ET.SubElement(field, "Type").text = self.type
        if self.hint:
            ET.SubElement(field, "Hint").text = self.hint
        if self.long_hint:
            ET.SubElement(field, "LongHint").text = self.long_hint
        ET.SubElement(field, "CitationField").text = str(self.citation)

        return field


class SourceTemplate:
    def __init__(
        self,
        name: str,
        fields: list[SourceTemplateField] = [],
        description: str = "",
        category: str = "",
        footnote: str = "",
        bibliography: str = "",
        short_footnote: str = "",
    ) -> None:
        self.name = name
        self.fields = fields
        self.description = description
        self.category = category
        self.footnote = footnote
        self.bibliography = bibliography
        self.short_footnote = short_footnote

    def to_xml(self):
        root = ET.Element("Root")
        if self.fields:
            fields = ET.SubElement(root, "Fields")
            fields.extend([f.to_xml() for f in self.fields])
        return root

    def create(self, conn: Connection) -> int:
        sql = """\
INSERT INTO SourceTemplateTable (
  Name, Description, Favorite, Category, Footnote, ShortFootnote, Bibliography, FieldDefs, UTCModDate
) VALUES (
  ?, ?, 0, ?, ?, ?, ?, ?, julianday('now') - 2415018.5
)
"""
        template_id = -1

        exists = find_source_template(conn, self.name)
        if exists:
            template_id = exists

        else:
            cur = conn.execute(
                sql,
                (
                    self.name,
                    self.description,
                    self.category,
                    self.footnote,
                    self.short_footnote,
                    self.bibliography,
                    ET.tostring(self.to_xml()),
                ),
            )

            if cur.lastrowid:
                template_id = cur.lastrowid

        return template_id


def find_source_template(conn: Connection, name):
    sql = "SELECT TemplateID FROM SourceTemplateTable where Name = ?"
    cur = conn.execute(sql, (name,))
    res = cur.fetchone()
    if res:
        return res[0]
    else:
        return None


# ===================================================DIV60==

INSERT_WEBLINK_STMT = """\
INSERT INTO URLTable (
  'OwnerType', 'OwnerID', 'LinkType', 'Name', 'URL', 'Note', 'UTCModDate'
)
VALUES (
  ?, ?, 0, ?, ?, '', julianday('now') - 2415018.5
)
"""


def add_weblink(conn: Connection, name, url, owner_id, owner_type: OwnerType):
    conn.execute(INSERT_WEBLINK_STMT, (owner_type, owner_id, name, url))


def add_weblinks(conn: Connection, data=None, **kwargs):
    """Creates multiple weblinks

    Args:
        data (list[tuple[OwnerType, str, str, str]]): list of tuples (OwnerType, owner_id, name, url)

    Keyword Args:
        owner_types (list[OwnerType])
        owners (list[str])
        names (list[str])
        urls (list[str])

    Returns:
        None
    """
    if data is None:
        for a, b in itertools.combinations(
            [len(a) for a in kwargs.values() if type(a) is list], 2
        ):
            if a != b:
                raise RM_Py_Exception("All input lists need to be same size")

        data = zip(
            kwargs["owner_types"], kwargs["owners"], kwargs["names"], kwargs["urls"]
        )

    conn.executemany(INSERT_WEBLINK_STMT, data)
    conn.commit()


# ===================================================DIV60==


def create_source(
    conn: Connection,
    name: str,
    template_id: str | int,
    fields: dict | ET.Element,
    ref_num="",
    url=None,
):
    sql = """\
INSERT INTO SourceTable (
  'Name','RefNumber','ActualText','Comments','IsPrivate','TemplateID','Fields','UTCModDate'
)
VALUES (
    ?,?,"","",0,?,?,julianday('now') - 2415018.5
)
    """
    root = wrap_fields(fields)
    source_id = conn.execute(
        sql, (name, ref_num, template_id, ET.tostring(root))
    ).lastrowid
    if not source_id:
        raise RM_Py_Exception(
            f"unable to create new source {name} {template_id}\n{ET.tostring(root)}"
        )
    if url:
        add_weblink(conn, "", url, source_id, OwnerType.SOURCE)
    return source_id


def delete_source(conn: Connection, source_id):
    # Remove the old source
    sql_delete = "DELETE from SourceTable WHERE SourceID = ?"
    conn.execute(sql_delete, (source_id,))


# ===================================================DIV60==

INSERT_CITATION_STMT = """\
INSERT INTO CitationTable(
  SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote, Bibliography, Fields, UTCModDate, CitationName
)
VALUES (
  ?, '', '', ?, '', '', '', ?, julianday('now') - 2415018.5, ? 
)    
"""


def create_citation(
    conn: Connection,
    source_id: str,
    ref_num: str,
    name: str,
    fields: dict | ET.Element,
    url=None,
):
    """Creates a new citation
    Returns:
        new citation ID
    """
    data = (source_id, ref_num, ET.tostring(wrap_fields(fields)), name)
    citation_id = conn.execute(INSERT_CITATION_STMT, data).lastrowid
    if not citation_id:
        raise RM_Py_Exception(f"Unable to create citation for {name}")
    if url:
        add_weblink(conn, name, url, citation_id, OwnerType.CITATION)
    return citation_id


def create_citations(conn: Connection, data=None, **kwargs):
    r"""Creates multiple citations

    Args:
        data (list[tuple[int, int, ET.Element, str]]): tuple of source_id, ref_num, fields, name

    Keyword Args:
        source_ids (list[int]): List of source IDs
        ref_nums (list[int]): List of reference numbers
        fields (list[ET.Element]): List of fields XML elements
        names (list[str]): List of names

    Returns:
        (first_citation_id, last_citation_id)
    """
    if data is None:
        for a, b in itertools.combinations(
            [len(a) for a in kwargs.values() if type(a) is list], 2
        ):
            if a != b:
                raise RM_Py_Exception("All input lists need to be same size")

        data = zip(
            kwargs["source_ids"],
            kwargs["ref_nums"],
            map(ET.tostring, kwargs["fields"]),
            kwargs["names"],
        )

    max = conn.execute("SELECT MAX(CitationID) FROM CitationTable;").fetchone()
    if max:
        next_citation_id = max[0] + 1
    else:
        raise RM_Py_Exception("Couldn't get number of rows in the CitationTable")

    cur = conn.executemany(INSERT_CITATION_STMT, data)
    conn.commit()

    if cur:
        return (next_citation_id, next_citation_id + cur.rowcount)
    else:
        None


INSERT_CITATION_LINK_STMT = """\
INSERT INTO CitationLinkTable(
  CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate
)
VALUES (
  ?, ?, ?, 0, '~~~', 0, 0, julianday('now') - 2415018.5
)
"""


def create_citation_link(
    conn: Connection, citation_id, owner_id, owner_type: OwnerType
):
    conn.execute(INSERT_CITATION_LINK_STMT, (citation_id, owner_type, owner_id))


def create_citation_links(conn: Connection, data=None, **kwargs):
    if data is None:
        for a, b in itertools.combinations(
            [len(a) for a in kwargs.values() if type(a) is list], 2
        ):
            if a != b:
                raise RM_Py_Exception("All input lists need to be same size")

        data = zip(kwargs["citation_ids"], kwargs["owner_types"], kwargs["owners"])

        conn.executemany(INSERT_CITATION_LINK_STMT, data)
        conn.commit()


def get_citations_for_source(conn: Connection, source_id) -> list[str]:
    """
    :returns: list of citation IDs
    """
    sql = "SELECT CitationID FROM CitationTable WHERE SourceID = ?"
    return [c[0] for c in conn.execute(sql, (source_id,))]


# ===================================================DIV60==
# XML fields data helper methods


def create_xml_fields(fields: dict, G_DEBUG=False):
    root = ET.Element("Fields")

    root.extend([create_xml_field(name, value) for name, value in fields.items()])

    if G_DEBUG:
        print("source XML START ============================")
        debug = copy.deepcopy(root)
        ET.indent(debug)
        ET.dump(debug)
        print("source XML END ==============================")

    return root


def create_xml_field(name, value):
    el = ET.Element("Field")
    ET.SubElement(el, "Name").text = name
    ET.SubElement(el, "Value").text = value
    return el


def wrap_fields(fields: str | ET.Element):
    root = ET.Element("Root")
    if isinstance(fields, dict):
        fields = create_xml_fields(fields)
    root.append(fields)
    return root


# ===================================================DIV60==
def create_repo(conn: Connection, name, url):
    sql_create = """
INSERT INTO AddressTable (
  AddressType, Name, Street1, Street2, City,State,Zip,Country,
  Phone1,Phone2,Fax,Email,URL,Latitude,Longitude,Note,
  UTCModDate
)
VALUES (
  1, ?, '', '', '', '', '', '', 
  '', '', '', '', ?, 0, 0, '', 
  julianday('now') - 2415018.5
)
    """
    cur = conn.execute(sql_create, (name, url))
    if cur:
        return cur.lastrowid
    else:
        return None


def link_source_to_repo(conn: Connection, source_id, repo_id):
    sql_add_repo = """
INSERT INTO AddressLinkTable (
  OwnerType, AddressID, OwnerID, AddressNum, Details, UTCModDate
) VALUES (
  ?,?,?,0,"",julianday('now') - 2415018.5
)
    """
    conn.execute(sql_add_repo, (OwnerType.SOURCE, repo_id, source_id))


# ===================================================DIV60==
