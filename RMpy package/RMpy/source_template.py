import sys
from pathlib import Path
sys.path.append(str(Path.resolve(Path(__file__).resolve().parent)))
import enum
import common as RM
import xml.etree.ElementTree as ET
from sqlite3 import Connection

class FieldType(enum.StrEnum):
    TEXT = "Text"
    NAME = "Name"
    PLACE = "Place"
    DATE = "Date"

class Field:
    def __init__(
        self,
        name: str,
        type: FieldType,
        display: str = None,
        hint: str = None,
        long_hint: str = None,
        citation: bool = False,
    ) -> None:
        self.name = name
        self.type = type
        self.display = display
        self.hint = hint
        self.long_hint = long_hint
        self.citation = citation

    def to_xml(self):
        field = ET.Element("Field")
        ET.SubElement(field, "FieldName").text = self.name
        ET.SubElement(field, "DisplayName").text = (
            self.display if self.display else self.name
        )
        ET.SubElement(field, "Type").text = self.type
        if self.hint:
            ET.SubElement(field, "Hint").text = self.hint
        if self.long_hint:
            ET.SubElement(field, "LongHint").text = self.long_hint
        ET.SubElement(field, "CitationField").text = str(self.citation)

        return field


class Template:
    def __init__(
        self,
        name: str,
        fields: list[Field] = [],
        description: str = "",
        category: str = "",
        footnote: str = "",
        bibliography: str = "",
        short_footnote: str = "",
    ) -> None:
        self.name = name
        self.fields = fields
        self.description = description
        self.category = category
        self.footnote = footnote
        self.bibliography = bibliography
        self.short_footnote = short_footnote
        self.template_id = -1

    def to_xml(self):
        root = ET.Element("Root")
        if self.fields:
            fields = ET.SubElement(root, "Fields")
            fields.extend([f.to_xml() for f in self.fields])
        return root

    def create(self, conn: Connection) -> int:
        sql = """\
INSERT INTO SourceTemplateTable (
  Name, Description, Favorite, Category, Footnote, ShortFootnote, Bibliography, FieldDefs, UTCModDate
) VALUES (
  ?, ?, 0, ?, ?, ?, ?, ?, julianday('now') - 2415018.5
)
"""
        

        exists = self.get_id(conn)
        if exists:
            self.template_id = exists

        else:
            cur = conn.execute(
                sql,
                (
                    self.name,
                    self.description,
                    self.category,
                    self.footnote,
                    self.short_footnote,
                    self.bibliography,
                    ET.tostring(self.to_xml()),
                ),
            )

            if cur.lastrowid:
                self.template_id = cur.lastrowid

        return self.template_id

    def get_id(self, conn: Connection):
        if not self.template_id or self.template_id == -1:
            sql = "SELECT TemplateID FROM SourceTemplateTable where Name = ?"
            self.template_id = RM.get_first(conn.execute(sql, (self.name,)))
            return self.template_id
