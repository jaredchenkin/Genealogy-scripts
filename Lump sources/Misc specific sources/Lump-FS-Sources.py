from sqlite3 import Connection
import xml.etree.ElementTree as ET
import re
import sys
from pathlib import Path

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[2] / "RMpy package")))
import RMpy.common as RM
import RMpy.familysearch as FS

from typing import TypeAlias

# FS Citation Format: FamilySearch (URL : Date), Record Name, Record Date"
cit_re = re.compile(r"FamilySearch \((.+?) : ([^)]*)\), ([\w\s\d]+)(?:, (.+?))?[.;]")

# Source Name in RM db Format: Principal, Collection Name
source_name_re = re.compile(r"(.*?), \"(.*?)\"")

# Strips any HTML tags from a string
html_strip_re = re.compile(r"<[^<]+?>")

G_DEBUG = False
MOD_DATE = None

Source: TypeAlias = dict[str, int]
SourceList: TypeAlias = dict[str, Source]


def main():
    global MOD_DATE
    config = RM.get_config()

    # Read file paths from ini file
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]

    # Process the database
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:

        fs_template_id = "439"  # get_or_create_fs_template(conn)
        fs_repo_id = FS.get_or_create_fs_repo(conn)
        fs_sources = FS.get_existing_sources(conn)

        # TemplateID = 0 is FreeForm template
        # RM Downloads FamilySearch sources as FreeForm sources
        # RM puts all the source information into the Footnote/Biblio fields in the source data itself
        #    not any of the columns in the SourceTable
        sql = "SELECT SourceID, Name, Fields, TemplateID FROM SourceTable WHERE Fields LIKE '%FamilySearch%' AND TemplateID = 0"

        for source in conn.execute(sql):
            principal, collection = FS.parse_source_name(source["Name"])
            citation, fields = FS.parse_citation(source["Fields"])
            citation_name = '{}, {}, "{}"'.format(
                principal, fields["record_name"], collection
            )

            if collection not in fs_sources:
                fs_source = create_fs_source(
                    conn, collection, fs_template_id, fields["url"]
                )
                FS.link_source_to_repo(conn, fs_source["id"], fs_repo_id)
                fs_sources[collection] = fs_source
            else:
                fs_source = fs_sources[collection]

            fields = create_citation_fields(citation, fs_source["template"])

            citation_id = process_citations(
                conn, source["SourceID"], fs_source["id"], citation_name, fields
            )
            update_url_owner(conn, citation_id, source["SourceID"])
            FS.delete_source(conn, source["SourceID"])


def create_fs_source(
    conn: Connection, collection, template_id, url
) -> dict[str, dict[str, str]]:
    print("=============== Creating new FamilySearch source ===================")
    print(f"Source Name: {collection}")
    print(f"Derived from source url: {url}")
    print("==== Be sure to update fields all before syncing with Ancestry! ====\n")

    fields = {
        "Author": "",
        "Title": collection,
        "Publisher": "FamilySearch.org",
        "PubPlace": "",
    }
    fields_elem = FS.create_xml_fields(fields)
    new_id = FS.create_source(conn, collection, template_id, fields_elem)
    if new_id:
        return {"id": new_id, "template": template_id}
    else:
        raise RM.RM_Py_Exception(
            "Unable to create new FamilySearch source: " + collection
        )


def update_url_owner(conn: Connection, citation_id, old_source_id):
    # Change owner & type columns for relevant web tags so they follow the citationToMove
    sql_url = """\
UPDATE URLTable
  SET OwnerType = 4,
      OwnerID = ? 
  WHERE OwnerType = 3 AND OwnerID = ?
  """
    conn.execute(sql_url, (citation_id, old_source_id))


def process_citations(conn, old_source_id, new_source_id, citation_name, fields) -> str:
    """
    Takes the first citation of the original FS source and migrates it to the new source.
    Sets up the new citation to cover all uses.
    Any other citations pointing to the old source are redundant and deleted.

    :param conn: sqlite3.Connection object
    :param old_source_id: ID of the FS Source created by RM import
    :param new_source_id: ID of the new lumped FS Source in RM
    :param citation_name: Citation text to be used in the citation title field
    :param fields: ElementTree object with xml data for citation fields
    :returns: ID of the citation created from the original FS source
    """
    citation_id: str = None
    for citation in FS.get_citations_for_source(conn, old_source_id):
        if not citation_id:
            citation_id = citation
            convert_citation(conn, citation_name, citation_id, new_source_id, fields)
            convert_citation_links(conn, citation_id, old_source_id)
        else:
            conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (citation,))

    if citation_id is None:
        raise Exception(f"Source Citation not found for source id #{old_source_id}")

    return citation_id


def convert_citation(conn, citation_name, citation_id, new_source_id, fields):
    #  migrate the existing source data to the corresponding citation
    sql_update = """\
UPDATE CitationTable
  SET CitationName = ?,
      SourceID = ?,
      Fields = ?,
      UTCModDate = ?
  WHERE CitationID = ?
  """
    conn.execute(
        sql_update,
        (
            citation_name,
            new_source_id,
            ET.tostring(fields),
            RM.UTC_MOD_DATE,
            citation_id,
        ),
    )


def convert_citation_links(conn, citation_id, old_source_id):
    """
    Repoint Citations from the RM imported FS Source to the new citation for the Lumped FS Source.

    TODO: Also moves any citations links that point to the person to point to the person's primary name
    as Ancestry's new API doesn't return/expect citations to point to the person and should
    point to the primary name if they aren't pointing to an alternate name already.

    :param conn: sqlite3.Connection object
    :param citation_id: ID of the new citation for the Lumped FS Source
    :param old_source_id: ID of the source created by RM when importing from FS
    """
    sql = """\
UPDATE CitationLinkTable
SET CitationID = ?, UTCModDate = ?
WHERE LinkID in
(
  SELECT clt.LinkID FROM CitationLinkTable clt 
  INNER JOIN CitationTable ct USING (CitationID)
  WHERE ct.SourceID = ?
    AND clt.CitationID != ?
) 
    """
    conn.execute(sql, (citation_id, RM.UTC_MOD_DATE, old_source_id, citation_id))


def parse_citation(fields: str) -> list[str]:
    old_fields = processXmlDataToDOM(fields)
    encoded_citation_text = old_fields.find(
        ".//Fields/Field[Name='Footnote']/Value"
    ).text
    return FS.parse_citation(encoded_citation_text)


def create_citation_fields(citation, new_template_id):
    if new_template_id == "439":
        # Ancestry Source builtin
        root = FS.create_xml_fields({"Page": citation})
    elif new_template_id == "43":
        # U.S. Federal Census builtin template
        # TODO or not todo
        None

    return root


# ================================================================
def processXmlDataToDOM(XmlTxt):
    if not isinstance(XmlTxt, str):
        XmlTxt = XmlTxt.decode("utf-8")

    # test for and fix old style "XML" no longer used in RM8
    xmlStart = "<Root"
    rootLoc = XmlTxt.find(xmlStart)
    if rootLoc != 0:
        XmlTxt = XmlTxt[rootLoc::]
    # print (XmlTxt)

    # read into DOM and parse for needed values
    # only Page needed from old cit  XML data
    XmlRoot = ET.fromstring(XmlTxt)

    return XmlRoot


# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
