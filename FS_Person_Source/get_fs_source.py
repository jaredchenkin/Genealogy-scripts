import sys
from pathlib import Path
from sqlite3 import Connection
import argparse
import re
from urllib.parse import urlsplit, SplitResult
import xml.etree.ElementTree as ET
import signal

from getmyancestors.classes.tree import Tree, Source, Indi
from getmyancestors.classes.session import Session

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
import RMpy.RMDate as RMdate  # noqa #type: ignore
import RMpy.familysearch as FS
import RMpy.customizations as Cust


def sigint_handler(sig, frame):
    print("")
    sys.exit(1)


signal.signal(signal.SIGINT, sigint_handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fsid", type=str, help="FamilySearch ID")

    try:
        parser.error = parser.exit
        args = parser.parse_args(["L8M6-6BH"])
    except SystemExit:
        parser.print_help(file=sys.stderr)
        sys.exit(2)

    fsid = args.fsid
    if not re.match(r"[A-Z0-9]{4}-[A-Z0-9]{3}", fsid):
        sys.exit("Invalid FamilySearch ID: " + fsid)

    config = RM.get_config()
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]

    print("Logging into FamilySearch...")
    fs = Session(
        config["CREDENTIALS"]["FS_USERNAME"],
        config["CREDENTIALS"]["FS_PASSWORD"],
        verbose=False,
    )
    tree = Tree(fs)
    print(f"Finding person with FSID {fsid}")
    tree.add_indis([fsid])
    person: Indi = tree.indi[fsid]
    fs_sources = get_fs_sources(fs, person)

    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:

        rmID = get_rmid_from_fsid(conn, fsid)
        print(
            f"Found {person.name.given} {person.name.surname} in RootsMagic with ID number {rmID}"
        )

        while True:
            fs_source = get_fs_source_target(fs_sources)
            targets = {}
            targets[RM.OwnerType.EVENT] = get_fact_targets(conn, rmID)
            targets[RM.OwnerType.NAME] = get_name_targets(conn, rmID)
            targets[RM.OwnerType.PERSON] = [rmID] if get_person_target() else []

            if not any(targets.values()):
                print("Nothing to do")
                sys.exit(1)

            process_source(conn, rmID, fs_source, targets)

            again = input(
                f"Do you want to add another source to {person.name.given} [y/N]? "
            )
            if again and again.lower() == "y":
                continue
            else:
                break


def get_targets(list, length):
    """
    Takes the user input comma separated list and returns a list of ints, silently discarding
    inputs outside of the acceptable range
    :param: list string of comma separated integers
    :param: length max length of the array being indexed into
    :returns: normalized list of integers,
    """
    targets = []
    for t in list.split(","):
        if t.strip().isdigit() and 1 <= int(t) <= length:
            targets.append(int(t) - 1)
        else:
            raise

    return targets


def get_fact_targets(conn, rid):
    """
    Needs to query event table for both individual facts and family facts
    Props to ModifyCitationList.py for the incredible sql work
    """
    sql = """\
WITH 
Constants AS ( SELECT  ?   AS C_PersonID ),
Families AS (
    SELECT FamilyID
    FROM FamilyTable
    WHERE (FatherID = (SELECT C_PersonID FROM Constants)
        OR MotherID = (SELECT C_PersonID FROM Constants))
        )

SELECT et.EventID AS id, et.Date, ft.Name, pt.Name as Place, et.Details
  FROM EventTable et
  INNER JOIN FactTypeTable ft ON et.EventType = ft.FactTypeID
  INNER JOIN PlaceTable pt ON et.PlaceID = pt.PlaceID
WHERE et.OwnerID = (SELECT C_PersonID FROM Constants)
  AND et.OwnerType = 0

UNION
SELECT et.EventID AS id, et.Date, ft.Name, pt.Name as Place, et.Details
  FROM EventTable et
  INNER JOIN FactTypeTable ft ON et.EventType = ft.FactTypeID
  INNER JOIN PlaceTable pt ON et.PlaceID = pt.PlaceID
  WHERE et.OwnerID IN (SELECT FamilyID FROM Families)
    AND et.OwnerType = 1
      """

    facts = []
    for f in conn.execute(sql, (rid,)):
        fact = {}
        for key in f.keys():
            k = key.lower()
            if k == "date":
                fact[k] = RMdate.RMDate_str_TO_en_str(f[key], RMdate.Format.SHORT)
            else:
                fact[k] = f[key]
        facts.append(fact)

    print(f"RootsMagic facts for this person:")
    for i, f in enumerate(facts):
        print(f'{i + 1}: {f["name"]}, {f["date"]}, {f["place"]}, {f["details"]}')

    targets = []

    while True:
        response = input(
            "Do you want to associate this source with any facts?\n"
            + "Enter the fact number or [Nn] to skip: "
        )

        try:
            if response and response.lower() != "n":
                for t in get_targets(response, len(facts)):
                    targets.append(facts[t]["id"])
            break
        except:
            print("Bad input, try again")
            continue

    return targets


# Gets a list of names, with the primary name at index 0


def get_name_targets(conn, rid) -> list[str]:
    # Finding names is a little more straightforward than facts
    sql = "SELECT NameID AS id, Surname, Given, isPrimary FROM NameTable WHERE OwnerID = ?"

    names = []
    for n in conn.execute(sql, (rid,)):
        name = {k.lower(): n[k] for k in n.keys() if k != "IsPrimary"}
        if n["IsPrimary"] == "1":
            names.insert(0, name)
        else:
            names.append(name)

    print("RootsMagic names for this person:")
    for i, n in enumerate(names):
        print(f"{i + 1}: {n['given']} {n['surname']} {'(Primary)' if i == 0 else ''}")

    targets = []

    while True:
        response = input(
            "Do you want to associate this source with any names?\n"
            + "Enter the name number or [Nn] to skip: "
        )
        try:
            if response and response.lower() != "n":
                for n in get_targets(response, len(names)):
                    targets.append(names[n]["id"])
            break
        except:
            print("Bad input try again")
            continue

    return targets


def get_person_target():
    answer = input("Associate this source with the person record? [y/N] ")
    if answer:
        return answer.lower() == "y"


def get_fs_sources(fs: Session, person: Indi) -> list[Source]:
    print(
        f"Getting FamilySearch for sources of {person.name.given} {person.name.surname} [{person.fid}]..."
    )
    sources: list[Source] = [s[0] for s in person.sources]
    sources.sort(key=lambda s: s.num)
    return sources


def get_fs_source_target(sources: list[Source]) -> Source:
    print("FamilySearch sources found:")
    for s in sources:
        print(f"{s.num}: {s.title} | {s.citation.split(',')[-1].strip()[:-1]}")

    fs_source = int(input("Select an FS source to bring over: "))
    if fs_source == 0:
        sys.exit(0)
    elif fs_source < 0 and fs_source > len(sources):
        raise RM.RM_Py_Exception(f"Not a valid source number {fs_source}")
    return sources[fs_source - 1]


def get_rmid_from_fsid(conn: Connection, fsid: str) -> int:
    sql = "SELECT rmID FROM FamilySearchTable WHERE fsID = ?"
    cur = conn.execute(sql, (fsid,))
    if cur:
        return cur.fetchone()[0]
    else:
        raise RM.RM_Py_Exception("Can't find person with FSID " + fsid)

    """
  Notes on FamilySearch API object structure that isn't obvious/documented
#From /platform/tree/person/{fsid}/sources
src = ['sourceDescriptions'][]
url = src['about']
collection_id = src['identifiers']['http://getcomx.org/Collection'][0]
title = src['titles'][0]['value']
citation = src['citations'][0]['value']

#From /platform/records/collections/{collection_ID}
coll =  ['sourceDescriptions'][0]
url = coll['about']
jurisdiction = coll['coverage'][0]['spatial']['original']
citation = coll['citations'][0]['value']
description = coll['descriptions'][0]['value'] if coll['descriptions'][0]['lang'] == "en_US"
title = coll['titles'][0]['value'] if coll['titles'][0]['lang'] = "en_US
  """


def process_source(
    conn: Connection, rid: int, fs_source: Source, targets: dict[str, list]
):

    principal_name, source_name = FS.parse_source_name(fs_source.title)
    citation, citation_fields = FS.parse_citation(fs_source.citation)
    citation_name = FS.make_citation_name(fs_source.title, citation)

    source_id = FS.find_source(conn, source_name)
    source_info["type"] = None
    new_citation_fields = {}
    source_root = ET.Element("Root")
    source_info = {}
    collection_url = None

    if source_id:
        source_info["type"] = get_source_type_from_name(fs_source)
    else:
        source_data = fs_source.tree.fs.get_url(
            f"/platform/sources/descriptions/{fs_source.fid}"
        )
        try:
            collection_url = get_collection_url(source_data)
            collection_data = fs_source.tree.fs.get_url(urlsplit(collection_url).path)

            if type(collection_data) is dict:
                source_info = get_source_info(collection_data["sourceDescriptions"][0])
            else:
                raise KeyError

        except KeyError as e:
            print(
                "No information on the collection available, you must enter it to the source object manually"
            )
            print(e.with_traceback())

    match source_info["type"]:
        case "Birth" | "Death" | "Marriage":
            if not source_id:
                source_id = create_vitals_source(
                    conn, source_name, source_root, source_info, collection_url
                )
            new_citation_fields = build_vital_citation_fields(
                principal_name, citation_fields["record_date"]
            )
        case "Census":
            if "United States" in source_info["title"]:
                source_id = create_us_fed_census_source(
                    conn, source_name, source_root, source_info, collection_url
                )
            elif "UK" in source_info["title"]:
                source_id = create_uk_census(
                    conn, source_name, source_info, source_root, collection_url
                )
            else:
                source_id = create_us_state_census(
                    conn, source_name, source_info, source_root, collection_url
                )
        case _:
            source_id = make_new_source(conn, source_name, source_root, 1)

    print(f"Using source {source_name} with source ID {source_id}")

    citation_id = create_citation(
        conn, fs_source, source_id, citation_name, new_citation_fields, fs_source.url
    )
    print(f"Created new citation with ID {citation_id}")

    create_citation_links(conn, citation_id, targets)
    print(
        f"Completed migrating source {source_name} for {principal_name} from FamilySearch to RootsMagic!"
    )


def create_us_state_census(conn, source_name, source_root, source_info, collection_url):
    template_id = 54
    new_source_fields = make_us_state_census_fields(source_info)
    source_id = make_new_source(
        conn, source_name, source_root, template_id, new_source_fields, collection_url
    )
    return source_id


def create_uk_census(conn, source_name, source_info, source_root, collection_url):
    template_id = 35
    new_source_fields = source_info  # or do something else
    source_id = make_new_source(
        conn, source_name, source_root, template_id, new_source_fields, collection_url
    )
    return source_id


def create_us_fed_census_source(
    conn, source_name, source_root, source_info, collection_url
):
    template_id = 43
    new_source_fields = make_us_federal_census_fields(source_info)
    source_id = make_new_source(
        conn, source_name, new_source_fields, source_root, collection_url, template_id
    )
    return source_id


def create_vitals_source(conn, source_name, source_root, source_info, collection_url):
    template_id = RM.find_source_template(conn, Cust.VITAL_RECORDS)
    new_source_fields = make_vital_source_fields(source_info)
    source_id = make_new_source(
        conn, source_name, new_source_fields, source_root, collection_url, template_id
    )
    return source_id


def get_collection_url(source_data):
    return source_data["sourceDescriptions"][0]["identifiers"][
        "http://gedcomx.org/Collection"
    ][0]


def get_source_info(data):
    source_info = {}
    source_info["citation"] = data["citations"][0]["value"]
    source_info["description"] = get_en_US_item(data["descriptions"])
    source_info["title"] = get_en_US_item(data["titles"])
    source_info["jurisdiction"] = data["coverage"][0]["spatial"]["original"]
    source_info["type"] = get_type(data)
    return source_info


def get_source_type_from_name(fs_source):
    source_type = None
    vitals = re.search(r"(birth|death|marriage)", fs_source.title, re.IGNORECASE)
    if vitals:
        source_type = str(vitals[0]).title()
    return source_type


def get_en_US_item(items) -> str:
    for item in items:
        if item["lang"] == "en_US":
            return item["value"]
    return ""


def get_type(coll):
    for r in coll["coverage"]:
        type: SplitResult = urlsplit(r["recordType"])
        if "gedcomx.org" in type.netloc:
            return type.path.split("/")[1]


def make_new_source(conn, name, root, template_id, fields={}, collection_url=None):
    print(f'Creating new source with name "{name}" using template {template_id}')
    if fields:
        root.append(RM.create_xml_fields(fields))
        print(f"New fields are: \n{fields}")
    print(f"Linked to url {collection_url}")
    source_id = RM.create_source(conn, name, template_id, root, collection_url)
    RM.link_source_to_repo(conn, source_id, FS.get_or_create_fs_repo(conn))
    return source_id


def make_vital_source_fields(data: dict):
    repo, repo_loc = data["citation"].split(".")[-2].strip().split(",")
    return dict(
        Jurisdiction=data["jurisdiction"],
        # Agency='',
        Series=data["title"],
        Repository=repo.strip(),
        RepositoryLoc=repo_loc.strip(),
    )


def build_vital_citation_fields(name, date):
    return dict(Person=name, Date=date)


def make_us_federal_census_fields(data):
    return {
        "CensusID": "",  # Year and type
        "Jurisdiction": data["jurisdiction"],
        "Schedule": "population schedule",
        "ItemType": "",
        "Website": "",
        "URL": "",
        "CreditLine": "",
    }


def make_us_state_census_fields(data):
    pass


def create_citation(
    conn, fs_source: Source, rm_source_id, name: str, fields: list[dict], url
):
    """
    :returns: RM citation ID
    """
    print(
        f"Creating new citation {fs_source.title} to source {rm_source_id} and url {url} with fields:\n{fields}"
    )
    root = ET.Element("Root")
    fields = RM.create_xml_fields(fields)
    root.append(fields)
    return RM.create_citation(conn, rm_source_id, fs_source.fid, name, root, url)


def create_citation_links(conn, citation_id, targets={}):
    owner_types_temp = [[t] * len(target) for (t, target) in targets.items()]
    owner_types = [t for x in owner_types_temp for t in x]
    RM.create_citation_links(
        conn,
        citation_ids=[citation_id] * len(owner_types),
        owners=[t for x in targets.values() for t in x],
        owner_types=owner_types,
    )


# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
