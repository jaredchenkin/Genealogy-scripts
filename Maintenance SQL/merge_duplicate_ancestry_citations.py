import sys
from pathlib import Path
from sqlite3 import Connection
import itertools
from urllib.parse import urlsplit, SplitResult
import xml.etree.ElementTree as ET
import sqlite3


sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
import RMpy.RMDate as RMdate  # noqa #type: ignore

# Used when RM creates a new source with one citation for every ancestry fact downloaded, regardless of whether or not it exists
def main():
    config = RM.get_config()
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]

    with RM.create_db_connection2(database_Path, [RMNOCASE_Path]) as conn:

        # Citation links on ancestry have a unique id. Find all instances where the same id points to multiple RM citations
        find_dupe_sql = "SELECT rmID, anID FROM AncestryTable GROUP BY anID having count(*) > 1 and LinkType = ?"
        
        for dupes in conn.execute(find_dupe_sql, (RM.OwnerType.CITATION,)):

            # Looping through each pair of (RM citation ID, AN citation ID).
            # Even though we're looking for duplicate anids, the query only returns one rmid for the duplicated anid
            # Assuming the table is sorted, this should be the lowest numerical citation id that has that anid
            # We'll use that as the citation id to preserve
            base_rmid, anid = dupes
            
            # *Now* get the list of all citation ids that point to that the an link
            cur = conn.execute("SELECT rmID from AncestryTable WHERE anID = ?", (anid,))
            citations_to_merge = [x["rmID"] for x in cur.fetchall() if x["rmID"] != base_rmid]
            
            # Dynamically build the part of the sql query string for python to inject the citation id list, since it varies
            placeholders = "(" + ", ".join(["?"] * len(citations_to_merge)) + ")"
            
            # Repoint all the other citations links to the one citation we want to keep
            update_cit_link_sql = f"UPDATE CitationLinkTable set CitationID = ? WHERE CitationID IN {placeholders}"
            conn.execute(update_cit_link_sql, ([base_rmid] + citations_to_merge ))
            
            # Ancestry may download media for that source, so we need to repoint those links too
            update_media_links_sql = f"UPDATE MediaLinkTable SET OwnerID = ? WHERE OwnerType = ? and OwnerID in {placeholders}"
            conn.execute(update_media_links_sql, ([base_rmid, RM.OwnerType.CITATION] + citations_to_merge))
                        
            # Delete the duplicate orphaned citations
            conn.execute(f"DELETE FROM CitationTable WHERE CitationID in {placeholders}", citations_to_merge)

            # No need to keep the dangling ancestry links pointing to the unused citations
            conn.execute(f"DELETE FROM AncestryTable WHERE anID = ? and rmID in {placeholders}", ([anid] + citations_to_merge ))
            
            conn.commit()

if __name__ == "__main__":
    main()
