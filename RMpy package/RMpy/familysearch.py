from . import common as RM
from sqlite3 import Connection
import xml.etree.ElementTree as ET
import re
import html
import copy
from pathlib import Path
import sys
import html
import enum
import itertools

# FS Citation Format: FamilySearch (URL : Date), Record Name, Record Date"
cit_re = re.compile(
    r"FamilySearch \((?P<url>.+?) : (?P<date>[^)]*)\), (?P<record_name>[\w\s\d]+)(?:, (?P<record_date>.+?))?[.;]"
)

# Source Name in RM db Format: Principal, Collection Name
source_name_re = re.compile(r"(?P<principal>.*?), \"(?P<collection>.*?)\"")

# Strips any HTML tags from a string
html_strip_re = re.compile(r"<[^<]+?>")

# Source methods


def get_existing_sources(conn: Connection) -> dict[str, dict[str, str]]:
    """
    Find all existing Sources in the FamilySearch repository:
    Find the Repository (AddressType = 1) with the name FamilySearch
    Find all the sources that the FS Repo is used in (OwnerType = 3)
    Return sourceID, Name, Template ID from the SourcesTable
      for those sources
    Don't limit to just the FamilySearch source type in case of other source
      template types used, such as US Census, etc.
    
    Args:
        conn Connection: open sqlite3 connection object
    
    Returns:
        dict[str, dict[str,str]]: Map with keys like {'name':{'id', 'template'}}
    """
    # TODO: Multiple sources with same name?
    sql_stmt = """\
SELECT st.Name, st.SourceID, st.TemplateID
  FROM SourceTable st 
    WHERE st.SourceID IN (
    SELECT alt.OwnerID 
    FROM AddressTable at 
    INNER JOIN AddressLinkTable alt USING (AddressID) 
      WHERE at.Name = 'FamilySearch' 
        AND at.AddressType = 1
        AND alt.OwnerType = 3
    )
  """
    return {
        s["Name"]: {"id": s["SourceID"], "template": s["TemplateID"]}
        for s in conn.execute(sql_stmt)
    }


def find_source(conn: Connection, name: str):
    sql = """\
SELECT st.SourceID, st.TemplateID
  FROM SourceTable st 
    INNER JOIN AddressLInkTable alt ON st.SourceID = alt.OwnerID
    INNER JOIN AddressTable at USING (AddressID)
    WHERE st.Name = ? 
      AND at.Name = 'FamilySearch' 
      AND at.AddressType = 1
      AND alt.OwnerType = 3
  """
    cur = conn.execute(sql, (name,))
    sources = cur.fetchall()
    if len(sources) > 1:
        raise RM.RM_Py_Exception(
            f"More than 1 FamilySearch source in RootsMagic with the name {name}. Please Lump first."
        )
    if sources:
        return sources[0]["SourceID"]
    else:
        return None


def parse_source_name(name):
    m = source_name_re.match(name)
    if not m:
        raise RM.RM_Py_Exception(f"Cant parse source name {name}")
    return m.groups()


# Citation Methods
def parse_citation(citation):
    clean_citation = html_strip_re.sub("", html.unescape(citation))

    m = cit_re.search(clean_citation)
    if not m:
        raise Exception(f"Can't parse citation text {citation}")

    return (clean_citation, m.groupdict())


def make_citation_name(source, citation):
    principal, citation_name = parse_source_name(source)
    m = cit_re.search(citation)
    if m:
        fields = m.groupdict()
        return '{}, {}, "{}"'.format(principal, fields["record_name"], citation_name)
    else:
        return ""


# Repository methods


def get_or_create_fs_repo(conn: Connection):
    sql = "SELECT AddressID FROM AddressTable WHERE Name = 'FamilySearch'"
    res = conn.execute(sql)
    repo_id = res.fetchone()

    if repo_id is None:
        repo_id = RM.create_repo(conn, "FamilySearch", "https://www.familysearch.com")
        if not repo_id:
            raise RM.RM_Py_Exception("Unable to create FamilySearch repository")
    else:
        repo_id = repo_id[0]

    return repo_id
