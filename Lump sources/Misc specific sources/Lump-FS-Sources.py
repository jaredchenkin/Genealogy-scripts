import sqlite3
import os
import configparser
import xml.etree.ElementTree as ET
import re
import html
import contextlib

cit_re = re.compile(r'"(.+?)", \<i\>FamilySearch\<\/i\> \((.+?) : (.*?)\), ([\w\s\d]+), (.+?)\.')
source_name_re = re.compile(r'(.*?), \"(.*?)\"')
html_strip_re = re.compile(r'<[^<]+?>')

G_DEBUG = False

MOD_DATE = None

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
  with contextlib.closing(create_DBconnection(database_Path)) as conn:
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

      for source in get_sources_to_lump(conn):
        collection = source['collection']
        if collection in fs_sources:
          fs_source = fs_sources[collection]
        else:
          fs_source = create_fs_source(conn, source, fs_template_id)
          link_source_to_repo(conn, fs_source['id'], fs_repo_id)
          fs_sources[collection] = fs_source

        convert_source(conn, source, fs_source, fs_template_id)


def create_DBconnection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)

    return conn

def get_sources_to_lump(conn):
  # TemplateID = 0 is FreeForm template
  # RM Downloads FamilySearch sources as FreeForm sources
  # RM puts all the source information into the Footnote/Biblio fields in the source data itself
  #    not any of the columns in the SourceTable
  sql="""\
SELECT SourceID, Name, Fields, TemplateID
  FROM SourceTable
  WHERE Fields LIKE '%FamilySearch%'
    AND TemplateID = 0
"""

  cur = conn.cursor()
  sources = []
  for s in cur.execute(sql):
    name_matches = source_name_re.match(s['Name'])
    principal = name_matches[1]
    collection = name_matches[2]
    sources.append({'id': s['SourceID'],
                           'collection': collection,
                           'principal': principal,
                           'fields' : processXmlDataToDOM(s['Fields'].decode()),
                           'template_id': s['TemplateID'],
                          })
  return sources

def get_existing_fs_sources(conn):
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

def create_fs_source(conn, source_data, template_id):
    collection = source_data['collection']
    print("==== Creating new FamilySearch source ====")
    print(collection)
    print("==== Be sure to update fields all before syncing with Ancestry! ====")
    
    sql="""
INSERT INTO SourceTable (
  'Name','RefNumber','ActualText','Comments','IsPrivate','TemplateID','Fields','UTCModDate'
)
VALUES (
    ?,"","","",0,?,?,?
)
    """
    fields = create_fs_source_fields(collection)
    cur = conn.cursor()
    res = cur.execute(sql, (collection, template_id, ET.tostring(fields), MOD_DATE))
    return { 'id': res.lastrowid, 'template': template_id }
  
def link_source_to_repo(conn, source_id, repo_id):
    sql_add_repo = """
  INSERT INTO AddressLinkTable (
    OwnerType, AddressID, OwnerID, AddressNum, Details, UTCModDate
  ) VALUES (
    3,?,?,0,"",?
  )
    """
    RunSqlNoResult(conn, sql_add_repo, (source_id, repo_id, MOD_DATE))

def create_fs_source_fields(collection):
    root = ET.Element("Root")
    fields = ET.SubElement(root, "Fields")
    create_field(fields, "Publisher", "FamilySearch.org")
    create_field(fields, "PubPlace", "https://www.familysearch.org")
    create_field(fields, "Title", collection)
    return root

def convert_source(conn, old_source, new_source, fs_template_id):
  citation_id = get_source_citation(conn, old_source['id'])

  encoded_citation_text = old_source['fields'].find(".//Fields/Field[Name='Footnote']/Value").text
  citation_text = html.unescape(encoded_citation_text) 
  citation = cit_re.match(citation_text)
  stripped_citation = html_strip_re.sub('', citation_text)
  if old_source['collection'] != citation[1]:
    raise Exception(F"Collections don't match: Source is {old_source['collection']}, citation is {citation[1]}")

  cit_name = "{}, {}, \"{}\"".format(old_source['principal'], citation[4], old_source['collection'])

  root = ET.Element("Root")
  fields = ET.SubElement(root, "Fields")

  if new_source['template'] == '439':
    create_field(fields, 'Page', stripped_citation)
  elif new_source['template'] == fs_template_id:
    create_field(fields, "RecordDate", citation[5])
    create_field(fields, "RecordPrincipal", old_source['principal'])
    create_field(fields, "Page", cit_name)
    create_field(fields, "URL", citation[2])
  elif new_source['template'] == 43:
    # U.S. Federal Census builtin template
    None
  
  if G_DEBUG:
      print("citation XML START ============================")
      ET.indent(root)
      ET.dump(root)
      print("citation XML END ==============================")


  # Change owner & type columns for relevant web tags so they follow the citationToMove
  sql_url = """\
  UPDATE URLTable
    SET OwnerType = 4,
        OwnerID = ? 
    WHERE OwnerType = 3 AND OwnerID = ?
  """
  RunSqlNoResult(conn, sql_url, (citation_id, old_source['id']))
  
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
                 (cit_name, new_source['id'],
                  ET.tostring(root),
                  MOD_DATE,
                  citation_id)
                 )

  # Remove the old source
  sql_delete = """\
  DELETE from SourceTable
    WHERE SourceID = ?  
  """
  RunSqlNoResult(conn, sql_delete, (old_source['id'],))
    

def get_source_citation(conn, source_id):
  SqlStmt="SELECT CitationId FROM CitationTable WHERE SourceId = ?"
  cur = conn.cursor()
  cur.execute(SqlStmt, (source_id,))
  res = cur.fetchone()
  if res is not None:
    return res['CitationId']
  else:
    raise Exception(F"Source Citation not found for source id #{source_id}")

# ================================================================
def GetListOfRows ( conn, SqlStmt):
    # SqlStmt should return a set of single values
    cur = conn.cursor()
    cur.execute(SqlStmt)

    result = []
    for t in cur:
      for x in t:
        result.append(x)
    return result

def RunSqlNoResult(db_connection, SqlStmt):
    cur = db_connection.cursor()
    res = cur.execute(SqlStmt)
    return res.lastrowid

def RunSqlNoResult ( conn, SqlStmt, myTuple):
    cur = conn.cursor()
    res = cur.execute(SqlStmt, myTuple)
    return res.lastrowid

def getFieldsXmlDataAsDOM ( conn, rowID ):
  SqlStmt = """\
        SELECT Fields
    FROM SourceTable
    WHERE SourceID = ?
"""
  cur = conn.cursor()
  cur.execute(SqlStmt, (rowID,))
  XmlTxt = cur.fetchone()[0].decode()
  # print (XmlTxt)
  return processXmlDataToDOM(XmlTxt)

def processXmlDataToDOM(XmlTxt):
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

def get_or_create_fs_repo(conn):
  sql = "SELECT AddressID FROM AddressTable WHERE Name = 'FamilySearch'"
  cur = conn.cursor()
  res = cur.execute(sql)
  repo_id = res.fetchone()
  
  if repo_id is not None:
    return repo_id[0]
  else:
    return create_repo(conn, "FamilySearch", "https://www.familysearch.com")
  
def create_repo(conn, name, url):
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

# ================================================================
# Call the "main" function
if __name__ == '__main__':
    main()

# ================================================================


### Not being used since I decided to use the Ancestry Record template (439) instead
def get_or_create_fs_template(conn):
  sql="SELECT TemplateID FROM SourceTemplateTable WHERE Name = 'FamilySearch Record'"
  cur = conn.cursor()
  res = cur.execute(sql)
  templateId = res.fetchone()

  if templateId is None:
    field_data = create_fs_source_template_fields()
    fields = ET.tostring(field_data)
    
    # TODO: Decide on Footnote formatting
    footnote = "[Author], <i>[Title]</i> (<[PubPlace]|N.p.>: <[Publisher]|n.p.>, <[PubDate]|n.d.>)<, [Page]>."
    shortfootnote = "[Author:Surname], <i>[Title:Abbrev]</i><, [Page]>."
    biblio = "[Author:Reverse]. <i>[Title]</i>. <[PubPlace]|N.p.>: <[Publisher]|n.p.>, <[PubDate]|n.d.>."
    
    sql_create="""\
INSERT INTO SourceTemplateTable (
  'Name',
  'Description',
  'Favorite',
  'Category',
  'Footnote',
  'Shortfootnote',
  'Bibliography',
  'FieldDefs',
  'UTCModDate'
)
VALUES (
  'FamilySearch Record',
  'FamilySearch.org Record Source',
  1,
  "",
  ?,?,?,?,?
)
    """
    cur.execute(sql_create, (footnote, shortfootnote, biblio, fields, MOD_DATE) )
    return cur.lastrowid
  else:
    return templateId[0]

def create_fs_source_template_fields():
  root = ET.Element("Root")
  fields = ET.SubElement(root, "Fields")

  def add_field(field_name, display_name, type_, hint, citation_field):
      field = ET.SubElement(fields, "Field")
      
      ET.SubElement(field, "FieldName").text = field_name
      ET.SubElement(field, "DisplayName").text = display_name
      ET.SubElement(field, "Type").text = type_
      ET.SubElement(field, "Hint").text = hint
      ET.SubElement(field, "CitationField").text = citation_field

  def add_source_field(field_name, display_name, type_, hint=""):
    add_field(field_name, display_name, type_, hint, "False")
    
  def add_cit_field(field_name, display_name, type_, hint=""):
    add_field(field_name, display_name, type_, hint, "True")
 
  # Add each field
  add_source_field("Author", "Author", "Name", "the author(s) of the record")

  add_source_field("Title", "Title", "Text", "the title of the record")

  add_source_field("PubPlace", "Publish Place", "Place",
            "the place the record was published, if known")

  add_source_field("Publisher", "Publisher", "Text",
            "the publisher of the record, if known")

  add_source_field("PubDate", "Publish Date", "Date",
            "the date the record was published, if known")

  add_cit_field("Page", "Detail", "Text", "specific detail for this citation")

  add_cit_field("URL", "Record URL", "Text")

  add_cit_field("RecordDate", "Date", "Date")

  add_cit_field("RecordPrincipal", "Principal", "Name")

  # Build and write tree

  return root