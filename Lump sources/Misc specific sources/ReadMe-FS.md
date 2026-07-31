# FamilySearch Source Lumper

## Preamble

When using the TreeShare fature of Roots Magic with Family Search, you download sources individually and associate them with facts or events with checkboxes at that time. (Obviously you can add more links later too.) RM creates a new source with the Free Form source template (TemplateID = 0) and creates a single citation for the person that source is being downloaded for. This sort of compensates for how FS sees sources and citations: backwards. In FS, the source is the instances of a record attached to a person/fact/event/etc, and the citation is the document that the source is located in. In the RM domain model, sources are the documents with the information and citations point to the portion of the document pertient to that person/fact/event/etc. However, since when downloading an FS source, the only information about the citation (or what RM would consider a source) is the citation text, RM can't reverse the entries without making a lot of assumptions. Instead, it creates a new source for the FS source and a single citation to link that source to a person. In effect, this means the "source" is really one big citation since it doesn't cite the actual document where the informatoin originated.

## Example

For example, given the FS source at https://www.familysearch.org/ark:/61903/1:1:249X-XZT, the citation to that source is on the left hand side of the page:

```text
"New York, New York City Marriage Records, 1829-1938", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:249X-XZT : Thu Jul 24 17:20:33 UTC 2025), Entry for Barnet Chyenkin and Fanny Mendelson, 23 March 1890.
```

When downloading this source, Roots Magic creates the following Free Form source:

```text
Source Name: Barnet Chenkin, "New York, New York City Marriage Records, 1829-1938"
Footnote: "New York, New York City Marriage Records, 1829-1938", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:24W6-CZ3 : Thu Jul 24 19:49:27 UTC 2025), Entry for George B. Chenkin and Miriam Schneider, 19 June 1921.
Short Footnote: "New York, New York City Marriage Records, 1829-1938", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:24W6-CZ3 : Thu Jul 24 19:49:27 UTC 2025), Entry for George B. Chenkin and Miriam Schneider, 19 June 1921.
Bibliography: "New York, New York City Marriage Records, 1829-1938", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:24W6-CZ3 : Thu Jul 24 19:49:27 UTC 2025), Entry for George B. Chenkin and Miriam Schneider, 19 June 1921.
```

RM creates a webtag on the source to the following:

```text
Name: Barnet Chenkin, "New York, New York City Marriage Records, 1829-1938"
URL: https://familysearch.org/ark:/61903/1:1:24W6-CZQ
```

and a citation with no Name or Page number, but linked to the person/event/fact(s) indicated by the boxes checked in the download source dialog popup in TreeShare.

The corresponding data blob in the Fields field in the SourceTable in sqlite is this xml:

```xml
<Root>
  <Fields>
    <Field>
      <Name>Footnote</Name>
      <Value>"New York, New York City Marriage Records, 1829-1938", &lt;i&gt;FamilySearch&lt;/i&gt; (https://www.familysearch.org/ark:/61903/1:1:24W6-CZ3 : Thu Jul 24 19:49:27 UTC 2025), Entry for George B. Chenkin and Miriam Schneider, 19 June 1921.</Value>
    </Field>
    <Field>
      <Name>ShortFootnote</Name>
      <Value>...</Value>
    </Field>
    <Field>
      <Name>Bibliography</Name>
      <Value>...</Value>
    </Field>
  </Fields>
</Root>
```

## End State

1. A single source in RM for "New York, New York City Marriage Records, 1829-1938" that is compatible for easy upload to Ancestry. Right now, that's the Ancestry Source template (ID 439)
2. A single citation for the "Entry for George B. Chenkin and Miriam Schneider"
3. The citation linked to the various people/events/facts required

## Process

### Conventions

#### Source Name convention

The source name is the name of the principal individual for the citation and the collection name in double quotes, separated by a comma.

`Barnet Chenkin, "New York, New York City Marriage Records, 1829-1938"`

#### FS Source citation text convention

To be able to do this with the information given, we need to decompose the citation text given by FS, and we need to assume some conventions here are followed.

| Field | Used | Convention | Example |
| ----- | :---:  | ---------- | ---------------------------------------------- |
| Collection Name | Y | First quoted string (including commas) | New York, New York City Marriage Records, 1829-1938 |
| Website Name | N | FamilySearch wrapped in `<i>` tags | `<i>FamilySearch</i>` |
| Record URL | Y | Opening paren, the URL, a space, then a colon | `(https://www.familysearch.org/ark:/61903/1:1:24W6-CZ3 : ` |
| Record Create Date | N | An ISO 8608 date, followed by close parens and comma | ` Thu Jul 24 19:49:27 UTC 2025),` |
| Record Name | Y | Text up to the next comma | `Entry for George B. Chenkin and Miriam Schneider,` |
| Record Date | Y | Date in DD MMM YYYY format | `19 June 1921` |

The date could end in either a period or a comma, as I found out. Additional follow on data could come after if there is a comma. The regular expression I landed on ignores all of it after the date.
The date could also not be present at all, the entry just ends with the record name. The regex needed to account for that possibility too.

### Code path

0. Generate the [UTCModDate](https://sqlitetoolsforrootsmagic.com/date-last-edited/)
1. Create an Address to represent the Repository for FamilySearch.org, or get the address ID of the existing one.
2. Populate a dict of all existing sources at FamilySearch (those which are housed at the repository in step 1) where the key is the collection name, and the value is a dict with keys for the `id` (source ID) and `template` (template ID) values for that named source. This makes it easy figure out if I can reuse an already created source or if I need to make a new one for this record.
3. Find all sources that use the Free Form Template and have the string "FamilySearch" somewhere in the Fields cell (does the source data include the citation text pulled from FS?)
4. Looping through each source entry:
   * Parse out the necessary fields from the source name and field data
   * Find the RM source ID for the current source, or if one doesn't exist, create it
   * Take the first citation row created for that source and push the citation data into it
   * Create a URL link to the FS record and link it to the new citation
   * Delete the original source and extra citations, if any
