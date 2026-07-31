import sys
from pathlib import Path

sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import RMpy.common as RM  # noqa #type: ignore
import RMpy.RMDate as RMdate  # noqa #type: ignore

VITAL_RECORDS = "Vital Records (ancestry compatible)"

_vital_records = RM.SourceTemplate(
    VITAL_RECORDS,
    [
        RM.SourceTemplateField("Jurisdiction", RM.FieldType.PLACE),
        RM.SourceTemplateField("Agency", RM.FieldType.TEXT),
        RM.SourceTemplateField("Series", RM.FieldType.TEXT),
        RM.SourceTemplateField("Repository", RM.FieldType.TEXT),
        RM.SourceTemplateField("RepositoryLoc", RM.FieldType.PLACE),
        RM.SourceTemplateField("Person", RM.FieldType.NAME, "Name of Person(s)", True),
        RM.SourceTemplateField("Date", RM.FieldType.DATE, "Certificate Date", True),
        # RM.SourceTemplateField('Type', RM.FieldType.TEXT, 'Certificate Type', True),
        RM.SourceTemplateField(
            "CertificateNo", RM.FieldType.TEXT, "Certificate Number", True
        ),
    ],
    description="""Birth, Death, Marriage certificates; jurisdiction & agency as lead elements
Derived from Vital Records (state, certificates)""",
    category="[EE, QC-9, p 430]",
    footnote="[Series]",
    short_footnote="[Jurisdiction]< [Type]>< [CertificateNo]><, ([Date])><, [PersonID:Abbrev]>.",
    bibliography="[Jurisdiction]<. [Agency]><. [Series]>. [Repository]<, [RepositoryLoc]>.",
)


def setup():
    config = RM.get_config()

    with RM.create_db_connection(
        config["FILE_PATHS"]["DB_PATH"], config["FILE_PATHS"]["RMNOCASE_PATH"]
    ) as conn:
        _vital_records.create(conn)
