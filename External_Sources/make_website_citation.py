#!/usr/bin/env python3
import sys
from pathlib import Path
import argparse
from urllib import parse
import re

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rm_id", type=int, help="RootsMagic Person ID Number")
    # parser.add_argument("name", type=str, help="Name of the person")
    subparsers = parser.add_subparsers(required=True)

    rafalin = subparsers.add_parser("r", help="Rafalin/Rafael book")
    rafalin.add_argument("name", type=str, help="Name of the person in the book")
    rafalin.add_argument("page", type=int, help="Page number in the Rafalin Book")
    rafalin.add_argument(
        "register", type=str, help="Register number for this individual"
    )
    rafalin.set_defaults(func=process_rafalin)

    monastirli = subparsers.add_parser("m", help="Cassorla.net Trees")
    monastirli.add_argument("name", type=str, help="Name of the person on the website")
    monastirli.add_argument(
        "page",
        type=str,
        help="Web Address direct to the person, such as 'El_Cass.html#Elias_Eliyahu'",
    )
    monastirli.set_defaults(func=process_monastirli)

    yad_vashem = subparsers.add_parser("y", help="Yad Vashem Shoah Names DB")
    yad_vashem.add_argument("name", type=str, help="Name of the person in the DB")
    yad_vashem.add_argument(
        "ref_num", type=int, help="Reference Number to record on USHMM"
    )
    yad_vashem.add_argument("url", type=str, help="URL to the website")
    yad_vashem.set_defaults(func=process_yad_vashem)

    ushmm = subparsers.add_parser("u", help="US Holocaust Museum photos")
    ushmm.add_argument("ref_num", type=int, help="Reference Number to record on USHMM")
    ushmm.add_argument("url", type=str, help="URL to the picture page")
    ushmm.add_argument(
        "more_rm_ids", type=int, help="Additional RM people IDs to link to", nargs="*"
    )
    ushmm.set_defaults(func=process_ushmm)

    try:
        parser.error = parser.exit
        args = parser.parse_args()
    except SystemExit:
        parser.print_help(file=sys.stderr)
        sys.exit(2)

    config = RM.get_config()
    args.func(args, config)

def process_rafalin(args, config):
    if args.page > 282 or args.page < 1:
        raise RM.RM_Py_Exception(
            f"There are only 282 pages in the book, {args.page} isn't valid. Try again"
        )
    if args.register.isdigit() and (int(args.register) > 590 or int(args.register) < 1):
        raise RM.RM_Py_Exception(
            f"The highest register number is 590, {int(args.register)} isn't valid. Try again"
        )

    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        fields = {
            "ItemOfInterest":args.name,
            "AccessType": "",
            "AccessDate": "",
            "Page": f"Page {args.page}",
            "Annotation": f"Register #{args.register}",
        }
        url = f"https://familysearch.org/library/books/idviewer/114611/{args.page - 2}"
        source_id = get_or_create_rafalin_source(conn)
        if check_link_exists(conn, source_id, args.rm_id, args.name):
            citation_id = RM.create_citation(conn, source_id, "", args.name, fields, url)
            # name = RM.get_primary_name(conn, args.rm_id)
            RM.create_citation_link(conn, citation_id, args.rm_id, RM.OwnerType.PERSON)

def check_link_exists(conn, source_id, rm_id, name):
    for row in RM.get_all_citations(conn, rm_id):
        if row['SourceID'] == source_id and row['CitationName'] == name:
            redo = input(f"The citation for {name} to the source already exists. Make again? [y/N] ")
            if redo.lower() == 'y':
                return True
            else:
                return False
    return True


def get_or_create_rafalin_source(conn) -> int:
    name = "The Raphael/Rafalin family"
    source_id = RM.get_source(conn, name)
    if not source_id:
        url = "https://www.familysearch.org/library/books/records/item/114611-the-raphael-rafalin-family-jewish-roots-in-punsk-poland-and-vicinity-including-krasnopol-kalwaria-sejny-augustow-suwalki-filipow-and-klonorejsc"

        fields = {
            "Author": "Stehle, Randy; Schoenburg, Nancy",
            "Role": None,
            "Editors": None,
            "Title": name,
            "SubTitle": "Jewish roots in Punsk, Poland and vicinity; including Krasnopol, Kalwaria, Sejny, Augustow, Suwalki, Filipow and Klonorejsc",
            "Edition": None,
            "PubPlace": None,
            "Publisher": None,
            "PubDate": None,
            "NewFormat": None,
            "Creator": None,
            "WebsiteTitle": "Family Search",
            "URL": url,
        }
        source_id = RM.create_source(conn, name, 172, fields, 1327648, url, True)
    return source_id


def process_monastirli(args, config):

    page_base_names = {
        "El_Cass.html": "Descendants of Elias Cassorla of Monastir",
        "Haim_JacobCalderon.html": "Haim and Jacob Calderon Family of Monastir",
        "Aroesty.html": "The Menachem Aroesty Family Tree",
        "Mord_Testa.html": "The Mordohai Testa Family Tree",
    }

    url = parse.urlsplit(args.page)
    if url.path[0] == "/":
        path = url.path[1:]  # Strip leading '/'
    else:
        path = url.path

    if path not in page_base_names:
        raise RM.RM_Py_Exception(
            f"Page named {args.page} not in the list of known pages.\nKnown pages are:\n"
            + ",\n".join(list(page_base_names))
        )
    tree_title = page_base_names[path]

    fields = {
        "AccessType": "",
        "AccessDate": "",
        "TreeTitle": tree_title,
        "ItemOfInterest": args.name,
        "SubmitDate": "",
        "SubmittedBy": "",
        "EmailAddress": "",
        "StreetAddress": "",
        "CityAddress": "",
        "FilmDetails": "",
        "Annotation": "",
    }
    if not url.netloc:
        url = url._replace(scheme="https")
        url = url._replace(netloc="www.cassorla.net")
        args.page = parse.urlunsplit(url)

    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        source_id = get_or_create_cassorla_source(conn)
        citation_id = RM.create_citation(
            conn, source_id, "", args.name, fields, args.page
        )
        RM.create_citation_link(conn, citation_id, args.rm_id, RM.OwnerType.PERSON)


def get_or_create_cassorla_source(conn) -> int:
    name = "Descendants of the Sefaradim of Monastir and the Ottoman Lands"

    source_id = RM.get_source(conn, name, True)
    if not source_id:
        url = "https://cassorla.net"
        fields = {
            "DatabaseTitle": name,
            "Format": "website",
            "Creator": "Eli Cassorla",
            "WebsiteTitle": "",
            "URL": url,
        }
        source_id = RM.create_source(conn, template_id=428, fields=fields, url=url)
    return source_id


def process_yad_vashem(args, config):
    base_uri = "https://collections.yadvashem.org/en/names"
    fields = {"AccessType": "", "AccessDate": "", "ItemOfInterest": args.name}

    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        url = f"{base_uri}/{args.ref_num}"
        source_id = get_or_create_yad_vashem_source(conn, base_uri)
        citation_id = RM.create_citation(
            conn, source_id, args.ref_num, args.name, fields, url
        )
        RM.create_citation_link(conn, citation_id, args.rm_id, RM.OwnerType.PERSON)


def get_or_create_yad_vashem_source(conn, uri):
    name = "Yad Vashem Shoah Names DB"
    source_id = RM.get_source(conn, name, True)
    if not source_id:
        fields = {
            "Author": "Yad Vashem",
            "DatabaseTitle": "Shoah Names DB",
            "CreatorOwner": "",
            "WebsiteTitle": "",
            "URL": uri,
            "ItemType": "",
            "CreditLine": "",
        }
        source_id = RM.create_source(conn, name, 347, fields, uri=uri)
    return source_id


def process_ushmm(args, config):
    base_uri = "https://collections.ushmm.org"
    subject = input("Enter full subject title from site: ")
    fields = {
        "Type": "Portrait",
        "Subject": subject,
        "Photographer": "",
        "DigitalID": "",
        "AccessType": "",
        "AccessDate": "",
    }
    m = re.search(r"^Portrait of ([^.]+)\.", subject)
    if m:
        citation_name = m[1]
    else:
        citation_name = input("Couldn't extract subject name, enter here: ")

    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        source_id = get_or_create_ushmm_source(conn, base_uri)
        citation_id = RM.create_citation(
            conn, source_id, args.ref_num, citation_name, fields, args.url
        )
        RM.create_citation_link(conn, citation_id, args.rm_id, RM.OwnerType.PERSON)

        if args.more_rm_ids:
            size = len(args.more_rm_ids)
            RM.create_citation_links(conn,
                citation_ids=[citation_id] * size,
                owner_types= [RM.OwnerType.PERSON] * size,
                owners=args.more_rm_ids
            )


def get_or_create_ushmm_source(conn, uri):
    name = "The Jews in Macedonia during the Second World War (1941-1945), Vol.II - Kolonomos, Zhamila"
    source_id = RM.get_source(conn, name, True)
    if not source_id:
        fields = {
            "Collection": name,
            "Repository": "United States Holocaust Memorial Museum Photographs",
            "RepositoryLoc": "Washington, D.C.",
            "Format": "online images",
            "URL": uri,
        }
        source_id = RM.create_source(conn, name, 83, fields, url=uri, verbose=True)
    return source_id


# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
