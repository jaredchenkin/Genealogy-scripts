import sys
from pathlib import Path
from sqlite3 import Connection
import itertools
from urllib.parse import urlsplit, SplitResult
import xml.etree.ElementTree as ET
import sqlite3
import argparse
import signal

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
import RMpy.RMDate as RMdate  # noqa #type: ignore
from RMpy.facts import Fact, Event
import RMpy.customization as Cust

def main():
    """
    Creates source, citation, and link for an ancestry family tree
    Creates a fact type called "Ancestry Tree" to stash the citations in so that they don't get uploaded to ancestry
      rather than attach them to the person or a name, to allow citations in those places to be uploaded
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("rm_id", type=int, help="RootsMagic Person ID Number")
    parser.add_argument("tree_name", type=str, nargs="?", help="Name of the person on the other tree")
    parser.add_argument("url", type=str, help="URL to the Ancestry Tree", nargs='?')

    args = parser.parse_args()

    config = RM.get_config()
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]

    with RM.create_db_connection2(database_Path, RMNOCASE_Path) as conn:
        person = conn.execute('SELECT Given || " " || Surname FROM NameTable WHERE IsPrimary = 1 AND OwnerID = ?', [args.rm_id,]).fetchone()
        if person == None:
            raise RM.RM_Py_Exception(f"Unable to find person with ID {args.rm_id} in RM database {database_Path}")
        else:
            name = person[0]
        print(f"Adding Ancestry tree citation(s) for {name}")
        if args.url:
            link_tree(conn, args.rm_id, args.tree_name, args.url)
        else:
            while True:
                url = input("Ancestry Tree URL []: ")
                if url == "":
                    break
                
                tree_name = input("Name on other tree []: ")
                if tree_name == "":
                    break
                
                link_tree(conn, args.rm_id, tree_name, url)


                
def link_tree(conn: Connection, rm_id: str, name: str, url: str):
    (tree_id, person_id) = parse_tree_url(url)
    source_id = get_or_create_tree_source(conn, tree_id)
    citation_id = create_citation(conn, source_id, person_id, name, url)
    event_id = fact = get_or_create_an_fact(conn, rm_id)
    RM.create_citation_link(conn, citation_id, event_id, RM.OwnerType.EVENT)
    
def create_citation(conn: Connection, source_id: int, person_id: int, name: str, url: str):
    fields = dict(
        AccessDate="",
        ItemOfInterest=name,
    )
    return RM.create_citation(conn, source_id, person_id, name, fields, url)

def get_or_create_an_fact(conn, rm_id: int):
    fact_id = Cust.ANCESTRY_TREE_FACT.get_id(conn)
    if fact_id is None:
        raise RM.RM_Py_Exception("Ancestry tree fact doesn't exist in this database. run customizer")
    event = Event(Cust.ANCESTRY_TREE_FACT, RM.OwnerType.PERSON, rm_id)
    event_id = event.get_id(conn)
    if event_id is None:
        event_id = event.create(conn)
    return event_id
    

def get_or_create_tree_source(conn: Connection, tree_id: int):
    source_id = RM.get_source_by_refn(conn, tree_id)
    if source_id == None:
        print(f"Couldn't find a Family Tree with id {tree_id}, creating:")
        name = input("Enter the tree name: ")
        owner = input("Enter the tree owner: ")

        template_id = Cust.FAMILY_TREE.get_id(conn)
        if template_id is None:
            template_id = Cust.FAMILY_TREE.create(conn)

        url = f"https://www.ancestry.com/family-tree/tree/{tree_id}/family"
        fields =  dict(
            DatabaseTitle="Ancestry Public Member Trees",
            Creator=owner,
            URL=url,
            TreeTitle=name
        )
        source_id = RM.create_source(conn, name, template_id, fields, tree_id, url)
    return source_id

def parse_tree_url(tree_url: str):
    url = urlsplit(tree_url)
    # /family-tree/person/tree/{tree_id}/person/{person_id}/facts
    path_parts = url.path.split("/")
    return (path_parts[4], path_parts[6])
    


def sigint_handler(sig, frame):
    print("")
    sys.exit(1)

signal.signal(signal.SIGINT, sigint_handler)


# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
