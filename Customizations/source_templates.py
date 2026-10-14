import sys
from pathlib import Path
import xml.etree.cElementTree as ET
sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
import RMpy.customization as Cust
import RMpy.source_template as ST

def make_vital_records(conn):
    t =ST.Template(
        name=Cust.VITAL_RECORDS.name,
            fields=[
            ST.Field("Jurisdiction", ST.FieldType.PLACE),
            ST.Field("Series", ST.FieldType.TEXT),
            ST.Field("Agency", ST.FieldType.TEXT),
            ST.Field("URL", ST.FieldType.TEXT, "URL", True),
            ST.Field("Person", ST.FieldType.NAME, "Name of Person(s)", True),
            ST.Field("Date", ST.FieldType.DATE, "Certificate Date", True),
            ST.Field('Type', ST.FieldType.TEXT, 'Certificate Type', True),
            ST.Field("CertificateNo", ST.FieldType.TEXT, "Certificate Number", True),
            ST.Field("AccessType", ST.FieldType.TEXT, "Access Type", True),
            ST.Field("AccessDate", ST.FieldType.DATE, "Access Date", True),
            ST.Field("CreditLine", ST.FieldType.TEXT, "Credit Line")
        ],
        description="""Birth, Death, Marriage certificates; jurisdiction & agency as lead elements
Derived from Vital Records (state, certificates, online)""",
        category="[EE, sec 9.6, p 439]",
        footnote="[Jurisdiction:First], [Agency], [Series]",
        short_footnote='[Jurisdiction]< [Type:lower]>< certificate no. [CertificateNo]>, [Person]<, ([Date])>.',
        bibliography='[Jurisdiction],< [Type:lower]>< certificate no. [CertificateNo]>, [Person], [Date]; <[Agency],> <i>[Series]</i>,< [Format],|digital images,> ([URL] : <[AccessType]|accessed> [AccessedDate])<; [CreditLine]>.'
    )
    t.create(conn)
    return t

def make_family_tree(conn):
    t = ST.Template(
        name = Cust.FAMILY_TREE.name,
        fields = [
            ST.Template("DatabaseTitle", ST.FieldType.TEXT, "Database title", hint="title of the database"),
            ST.Template("Format", ST.FieldType.TEXT, "Format", hint="the format used, e.g. database", long_hint="[default = database]"),
            ST.Template("Creator", ST.FieldType.TEXT, "Creator/owner", hint="creator or owner of the website (optional)"),
            ST.Template("WebsiteTitle", ST.FieldType.TEXT, "Website title", hint="title of the website", long_hint="default = Ancestry.com"),
            ST.Template("URL", ST.FieldType.TEXT, "URL", hint="website address, e.g. http://www.ancestry.com"),
            ST.Template("TreeTitle", ST.FieldType.TEXT, "Tree title", hint="the title of the family tree"),
            ST.Template("AccessType", ST.FieldType.TEXT, "Access type", citation=True, hint="how you accessed the site", long_hint="e.g. accessed, viewed, printed, downloaded [default = accessed]"),
            ST.Template("AccessDate", ST.FieldType.DATE, "Access date", citation=True, hint="the date you accessed the site"),
            ST.Template("ItemOfInterest", ST.FieldType.TEXT, "Item of interest", citation=True, hint="entry details, name, date, etc.", long_hint="full version || shortened version of the title (if no short title, full title will be used in subsequent notes), e.g. card for Clovis Julian, no. 120, New Orleans Draft Board 13||card for Clovis Julian, #120, New Orleans Draft Bd. 13"),
            ST.Template("SubmitDate", ST.FieldType.DATE, "Submit date", citation=True, hint="date the file was submitted"),
            ST.Template("SubmittedBy", ST.FieldType.NAME, "Submitted by", citation=True, hint="the name of the person who submitted the tree"),
            ST.Template("EmailAddress", ST.FieldType.TEXT, "Email address", citation=True, hint="email address of the submitter"),
            ST.Template("StreetAddress", ST.FieldType.TEXT, "Street address", citation=True, hint="Street address of the submitter"),
            ST.Template("CityAddress", ST.FieldType.PLACE, "City address", citation=True, hint="city and state of submitter's address"),
            ST.Template("FilmDetails", ST.FieldType.TEXT, "Film details", citation=True, hint="Film publisher and film number, and roll number", long_hint="e.g. National Archives microfilm publication M1509"),
            ST.Template("Annotation", ST.FieldType.TEXT, "Annotation", citation=True, hint="Annotated remarks"),
        ],
        description="Family Trees, Documented data; databases and images, online.",
        category='[AQS inside right]',
        footnote='"[DatabaseTitle]", <[Format:lower]|database>,< [Creator],> <i><[WebsiteTitle]|Ancestry.com></i> ([URL] : <[AccessType]|accessed> [AccessDate])<, "[TreeTitle]><," [ItemOfInterest]|">; submitted< [SubmitDate]>< by [SubmittedBy]><!<, [EmailAddress]>><!<, [StreetAddress]>|, [<sc>contact information for private use</sc>]><, [CityAddress]><; citing [FilmDetails]><; [Annotation]>.',
        short_footnote='"[DatabaseTitle]," <[Format:lower]|database>, <i><[WebsiteTitle]|Ancestry.com></i><, "[TreeTitle]><," [ItemOfInterest:Abbrev].|.">',
        bibliography='"[DatabaseTitle]." <[Format:Caps]|Database>.< [Creator].> <i><[WebsiteTitle]|Ancestry.com></i>. [URL] : [AccessDate:Year]. '
    )
    t.create(conn)
    return t

def main():
    config = RM.get_config()

    # with RM.create_db_connection(
    #     config["FILE_PATHS"]["DB_PATH"], [config["FILE_PATHS"]["RMNOCASE_PATH"]]
    # ) as conn:
    #    make_vital_records()
    #    make_family_tree()
    #    for t in [Cust.VITAL_RECORDS, CUST.FAMILY_TREE]:
    #        t.create(conn)
    print(ET.tostring(Cust.VITAL_RECORDS.to_xml()))


if __name__ == "__main__":
    main()
