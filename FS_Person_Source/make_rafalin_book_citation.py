import sys
from pathlib import Path
import argparse

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rm_id", type=int, help="RootsMagic Person ID Number")
    parser.add_argument("page", type=int, help="Page number in the Rafalin Book")
    parser.add_argument("register", type=int, help="Register number for this individual")
    try:
        parser.error = parser.exit
        args = parser.parse_args()
    except SystemExit:
        parser.print_help(file=sys.stderr)
        sys.exit(2)

    if (args.page > 282 or args.page < 1):
        raise RM.RM_Py_Exception(f"There are only 282 pages in the book, {args.page} isn't valid. Try again")
    if (args.register > 590 or args.register < 1):
        raise RM.RM_Py_Exception(f"The highest register number is 590, {args.register} isn't valid. Try again")

    config = RM.get_config()
    database_Path = config["FILE_PATHS"]["DB_PATH"]
    RMNOCASE_Path = config["FILE_PATHS"]["RMNOCASE_PATH"]
    with RM.create_db_connection(database_Path, [RMNOCASE_Path]) as conn:
        make_rafalin_citation(conn, args.rm_id, args.page, args.register)

def get_name(conn, rm_id: str|int):
    sql="SELECT format('%s %s', Given, Surname) AS Name FROM NameTable WHERE IsPrimary = 1 AND OwnerID = ?"
    cur = conn.execute(sql, (rm_id,))
    return cur.fetchone()[0]


def make_rafalin_citation(conn, rm_id, page, register):
    name = get_name(conn, rm_id)
    if not name:
        raise RM.RM_Py_Exception(f"Couldn't find a person with RootsMagic ID number {rm_id}")
    fields = {
        'AccessType':'',
        'AccessDate':'',
        'Page':f"Page {page}",
        'Annotation':f"Register #{register}"
    }
    url = f"https://familysearch.org/library/books/idviewer/114611/{page - 2}"
    source_id = get_or_create_book_source(conn)
    citation_id = RM.create_citation(conn, source_id, '', name, fields, url)
    RM.create_citation_link(conn, citation_id, rm_id, RM.OwnerType.PERSON)


def get_or_create_book_source(conn) -> int:
    name = "The Raphael/Rafalin family"
    sql = "SELECT SourceID FROM SourceTable WHERE Name = ?"
    cur = conn.execute(sql, (name,))
    res = cur.fetchone()
    if res:
        return res[0]
    else:
        ref_num = 1327648
        source_template_id = 172
        url = "https://www.familysearch.org/library/books/records/item/114611-the-raphael-rafalin-family-jewish-roots-in-punsk-poland-and-vicinity-including-krasnopol-kalwaria-sejny-augustow-suwalki-filipow-and-klonorejsc"
        fields = {
            "Author":"Stehle, Randy; Schoenburg, Nancy",
            "Role":None,
            "Editors":None,
            "Title": name,
            "SubTitle":"Jewish roots in Punsk, Poland and vicinity; including Krasnopol, Kalwaria, Sejny, Augustow, Suwalki, Filipow and Klonorejsc",
            "Edition":None,
            "PubPlace":None,
            "Publisher":None,
            "PubDate":None,
            "NewFormat":None,
            "Creator":None,
            "WebsiteTitle":"Family Search",
            "URL":url
        }
        return RM.create_source(conn, source_template_id, fields, ref_num, url)

# ================================================================
# Call the "main" function
if __name__ == "__main__":
    main()

# ================================================================
