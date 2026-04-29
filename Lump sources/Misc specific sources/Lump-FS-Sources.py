import sqlite3
from sqlite3 import Connection
import os
import configparser
import xml.etree.ElementTree as ET
import re
import html
import contextlib
import copy
from typing import TypeAlias

# FS Citation Format: FamilySearch (URL : Date), Record Name, Record Date"
cit_re = re.compile(r'FamilySearch \((.+?) : ([^)]*)\), ([\w\s\d]+)(?:, (.+?))?[.;]')

# Source Name in RM db Format: Principal, Collection Name
source_name_re = re.compile(r'(.*?), \"(.*?)\"')

# Strips any HTML tags from a string
html_strip_re = re.compile(r'<[^<]+?>')

G_DEBUG = False
MOD_DATE = None

Source: TypeAlias = dict[str, int]
SourceList: TypeAlias = dict[str, Source]

def main():
  global MOD_DATE
  # Configuration file
  IniFile="RM-Python-config.ini"

  # ini file must be in "current directory" and encoded as UTF-8 if non-ASCII chars present (no BOM)
  if not os.path.exists(IniFile):
      print("ERROR: The ini configuration file, " + IniFile + " must be in the current directory." )
      return

  config = configparser.ConfigParser()
  config.read(IniFile, 'UTF-8')

  # Read file paths from ini file
  database_Path = config['File Paths']['DB_PATH']
  RMNOCASE_Path = config['File Paths']['RMNOCASE_PATH']

  if not os.path.exists(database_Path):
      print('Database path not found. Fix configuration file and try again.')
      return

  # Process the database
  with contextlib.closing(sqlite3.connect(database_Path)) as conn:
    conn.enable_load_extension(True)
    conn.load_extension(RMNOCASE_Path)
    conn.row_factory = sqlite3.Row
    
    cur = conn.cursor()
    # Ref: https://sqlitetoolsforrootsmagic.com/date-last-edited/
    cur.execute('SELECT julianday(\'now\') - 2415018.5')
    MOD_DATE = cur.fetchone()[0]

    with conn:
      fs_template_id = '439'   # get_or_create_fs_template(conn)
      fs_repo_id = get_or_create_fs_repo(conn)
      fs_sources = get_existing_fs_sources(conn)

      # TemplateID = 0 is FreeForm template
      # RM Downloads FamilySearch sources as FreeForm sources
      # RM puts all the source information into the Footnote/Biblio fields in the source data itself
      #    not any of the columns in the SourceTable
      sql="SELECT SourceID, Name, Fields, TemplateID FROM SourceTable WHERE Fields LIKE '%FamilySearch%' AND TemplateID = 0"

      for source in cur.execute(sql):
        (principal, collection) =  parse_source_name(source['Name'])
        (citation, url, record_accessed, record_name, record_date) = parse_citation(source['Fields'])
        citation_name = "{}, {}, \"{}\"".format(principal, record_name, collection)
        
        if collection not in fs_sources:
          fs_source = create_fs_source(conn, collection, fs_template_id, url)
          link_source_to_repo(conn, fs_source['id'], fs_repo_id)
          fs_sources[collection] = fs_source
        else:
          fs_source = fs_sources[collection]

        fields = create_citation_fields(citation, fs_source['template'])
          
        citation_id = process_citations(conn, source['SourceID'], fs_source['id'], citation_name, fields)
        update_url_owner(conn, citation_id, source['SourceID'])
        delete_old_source(conn, source['SourceID'])

def get_existing_fs_sources(conn: Connection) -> SourceList:
  # Find all existing Sources in the FamilySearch repository:
  # Find the Repository (AddressType = 1) with the name FamilySearch
  # Find all the sources that the FS Repo is used in (OwnerType = 3)
  # Return sourceID, Name, Fields, Template ID from the SourcesTable
  #   for those sources
  # Don't limit to just the FamilySearch source type in case of other source
  #   template types used, such as US Census, etc.
  sql_stmt="""\
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
  sources = {}
  cur = conn.cursor()
  for s in cur.execute(sql_stmt):
    sources[s['Name']] = {
                          'id': s['SourceID'],
                          'template': s['TemplateID'],
                         }
  
  return sources

def create_fs_source(conn: Connection, collection, template_id, url) -> Source:
    print("=============== Creating new FamilySearch source ===================")
    print(F"Source Name: {collection}")
    print(F"Derived from source url: {url}")
    print("==== Be sure to update fields all before syncing with Ancestry! ====\n")
    
    sql="""
INSERT INTO SourceTable (
  'Name','RefNumber','ActualText','Comments','IsPrivate','TemplateID','Fields','UTCModDate'
)
VALUES (
    ?,"","","",0,?,?,?
)
    """
    fields = create_fs_source_fields(collection)
    new_id = RunSqlNoResult(conn, sql, (collection, template_id, ET.tostring(fields), MOD_DATE))
    return { 'id': new_id, 'template': template_id }
  
def link_source_to_repo(conn: Connection, source_id, repo_id):
    sql_add_repo = """
INSERT INTO AddressLinkTable (
  OwnerType, AddressID, OwnerID, AddressNum, Details, UTCModDate
) VALUES (
  3,?,?,0,"",?
)
    """
    RunSqlNoResult(conn, sql_add_repo, (repo_id, source_id, MOD_DATE))

def create_fs_source_fields(collection):
    root = ET.Element("Root")
    fields = ET.SubElement(root, "Fields")
    
    create_field(fields, 'Author', '')
    create_field(fields, "Title", collection)
    create_field(fields, "Publisher", "FamilySearch.org")
    create_field(fields, "PubPlace", "")
    
    if G_DEBUG:
      print("source XML START ============================")
      debug = copy.deepcopy(root)
      ET.indent(debug)
      ET.dump(debug)
      print("source XML END ==============================")

    return root

def update_url_owner(conn: Connection, citation_id, old_source_id):
  # Change owner & type columns for relevant web tags so they follow the citationToMove
  sql_url = """\
UPDATE URLTable
  SET OwnerType = 4,
      OwnerID = ? 
  WHERE OwnerType = 3 AND OwnerID = ?
  """
  RunSqlNoResult(conn, sql_url, (citation_id, old_source_id))

def delete_old_source(conn, old_source_id):
  # Remove the old source
  sql_delete = "DELETE from SourceTable WHERE SourceID = ?"
  RunSqlNoResult(conn, sql_delete, (old_source_id,))

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
  SqlStmt="SELECT CitationID FROM CitationTable WHERE SourceID = ?"
  cur = conn.cursor()
  
  citation_id: str = None
  for citation in cur.execute(SqlStmt, (old_source_id,)):
    if not citation_id:
      citation_id = citation['CitationID']
      convert_citation(conn, citation_name, citation_id, new_source_id, fields)
      convert_citation_links(conn, citation_id, old_source_id)
    else:
      RunSqlNoResult(conn, "DELETE FROM CitationTable WHERE CitationID = ?", (citation['CitationID'],))
  
  if citation_id is None:
      raise Exception(F"Source Citation not found for source id #{old_source_id}")
  
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
  RunSqlNoResult(conn, sql_update, 
                 (citation_name,
                  new_source_id,
                  ET.tostring(fields),
                  MOD_DATE,
                  citation_id)
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
  RunSqlNoResult(conn, sql, (citation_id, MOD_DATE, old_source_id, citation_id))

def parse_source_name(name):
  m = source_name_re.match(name)
  if not m:
    raise Exception(F"Cant parse source name {name}")
  return m.groups()

def parse_citation(fields: str) -> list[str]:
  old_fields = processXmlDataToDOM(fields)
  encoded_citation_text = old_fields.find(".//Fields/Field[Name='Footnote']/Value").text
  citation = html_strip_re.sub('', html.unescape(encoded_citation_text))

  m = cit_re.search(citation)
  if not m:
    raise Exception(F"Can't parse citation text {citation}")
  
  return [citation, *m.groups()]

def get_or_create_fs_repo(conn: Connection):
  sql = "SELECT AddressID FROM AddressTable WHERE Name = 'FamilySearch'"
  cur = conn.cursor()
  res = cur.execute(sql)
  repo_id = res.fetchone()
  
  if repo_id is None:
    return create_repo(conn, "FamilySearch", "https://www.familysearch.com")
  else:
    return repo_id[0]
  
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
  ?
)
    """
    return RunSqlNoResult(conn, sql_create, (name, url, MOD_DATE))

def create_citation_fields(citation, new_template_id):
  root = ET.Element("Root")
  fields = ET.SubElement(root, "Fields")

  if new_template_id == '439':
    # Ancestry Source builtin
    create_field(fields, 'Page', citation)
  elif new_template_id == '43':
    # U.S. Federal Census builtin template
    # TODO or not todo
    None

  if G_DEBUG:
    print("citation XML START ============================")
    debug = copy.deepcopy(root)
    ET.indent(debug)
    ET.dump(debug)
    print("citation XML END ==============================")
    
  return root
    
  
# ================================================================
def create_DBconnection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)

    return conn

def GetListOfRows ( conn: Connection, SqlStmt):
    # SqlStmt should return a set of single values
    cur = conn.cursor()
    cur.execute(SqlStmt)

    result = []
    for t in cur:
      for x in t:
        result.append(x)
    return result

def RunSqlNoResult(db_connection: Connection, SqlStmt):
    cur = db_connection.cursor()
    res = cur.execute(SqlStmt)
    return res.lastrowid

def RunSqlNoResult ( conn: Connection, SqlStmt, myTuple):
    cur = conn.cursor()
    res = cur.execute(SqlStmt, myTuple)
    return res.lastrowid

def processXmlDataToDOM(XmlTxt):
  if not isinstance(XmlTxt, str):
    XmlTxt = XmlTxt.decode('utf-8')
  
  # test for and fix old style "XML" no longer used in RM8
  xmlStart = "<Root"
  rootLoc=XmlTxt.find(xmlStart)
  if rootLoc != 0:
    XmlTxt = XmlTxt[rootLoc::]
  # print (XmlTxt)

  # read into DOM and parse for needed values
  # only Page needed from old cit  XML data
  XmlRoot = ET.fromstring(XmlTxt)

  return XmlRoot

def create_field(fields, name, value):
    newPair = ET.SubElement(fields, "Field")
    ET.SubElement(newPair, "Name").text = name
    ET.SubElement(newPair, "Value").text = value
    
    return newPair

# ================================================================
# Call the "main" function
if __name__ == '__main__':
    main()

# ================================================================
