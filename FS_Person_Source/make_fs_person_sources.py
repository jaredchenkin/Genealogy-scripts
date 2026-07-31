from sqlite3 import Connection
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))

import RMpy.common as RM  # noqa #type: ignore
import RMpy.RMDate as RMdate  # noqa #type: ignore
import RMpy.familysearch as FS

G_DEBUG = False


def main():

    config = RM.get_config()

    # Read file paths from ini file
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]

    updated = []

    # Process the database
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        cur = conn.cursor()
        MOD_DATE = RMdate.get_MOD_DATE()

        fs_source_id = get_or_create_fs_person_source(conn)
        citations = dict(fields=[], names=[], ref_nums=[])
        urls = []

        for to_link in find_missing_links(conn, fs_source_id):
            name = f"{to_link['Name']}, individual in FamilySearch Family Tree"
            urls.append(f"https://familysearch.org/en/tree/person/{to_link['fsID']}")
            citations["names"].append(name)
            citations["fields"].append(create_citation_fields(name))
            citations["ref_nums"].append(to_link["fsID"])
            updated.append((to_link["Name"], to_link["PersonID"]))

        size = len(updated)
        citations["source_ids"] = [fs_source_id] * size

        citations_results = RM.create_citations(conn, **citations)
        if citations_results:
            RM.create_citation_links(
                conn,
                citation_ids=range(citations_results[0], citations_results[1] + 1),
                owner_types=[RM.OwnerType.PERSON] * size,
                owners=[u[1] for u in updated],
            )
            RM.add_weblinks(
                conn,
                urls=urls,
                owners=range(citations_results[0], citations_results[1] + 1),
                owner_types=[RM.OwnerType.CITATION] * size,
                names=citations["names"],
            )

    if len(updated) > 0:
        print(f"Successfully updated {len(updated)} records:")
        for p in updated:
            print(*p)
    else:
        print("No new records to update")


def find_missing_links(conn: Connection, source_id):
    cur = conn.cursor()
    sql = """\
SELECT pt.PersonID,
       fs.fsID,
       trim(nt.Prefix || ' ' || nt.Given || ' ' || nt.Surname || ' ' || nt.Suffix) Name
FROM PersonTable pt
  INNER JOIN FamilySearchTable fs ON pt.PersonId = fs.rmID
  INNER JOIN NameTable nt ON pt.PersonId = nt.OwnerID
  WHERE nt.IsPrimary = 1
    AND pt.PersonId NOT IN 
    (
        SELECT clt.OwnerID FROM CitationLinkTable clt
        INNER JOIN CitationTable ct USING (CitationId)
        WHERE clt.OwnerType = 0
            AND ct.SourceId = ?
    )
    """
    res = cur.execute(sql, (source_id,))
    return res.fetchall()


def get_or_create_fs_person_source(conn: Connection) -> int:
    name = "FamilySearch Family Tree Individual"
    title = "FamilySearch Family Tree Individual"
    sql = "SELECT SourceID FROM SourceTable WHERE Name = ?"

    cur = conn.cursor()
    cur.execute(sql, (name,))
    res = cur.fetchone()

    repo_id = FS.get_or_create_fs_repo(conn)

    if res is None:
        print("FS master source not found, creating..")
        return create_fs_person_source(conn, title, repo_id)
    else:
        print(f"Found master FS source at ID {res[0]}")
        return res[0]


def create_fs_person_source(conn: Connection, name, repo_id):
    template_id = 439  # Ancestry Source template builtin
    fields = make_source_fields(name)
    source_id = RM.create_source(conn, name, template_id, fields)
    RM.link_source_to_repo(conn, source_id, repo_id)
    return source_id


def make_source_fields(name):
    field_data = {
        "Publisher": "FamilySearch.org",
        "PubPlace": "https://www.familysearch.org",
        "Title": name,
        "Author": "FamilySearch.org",
    }
    return RM.create_xml_fields(field_data)


def create_citation_fields(detail):
    field_data = {"Page": detail}
    return RM.create_xml_fields(field_data)


# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
