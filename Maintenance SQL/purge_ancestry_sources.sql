-- Complete removal of all resources that were downloaded from Ancestry
delete from ancestrytable where rowid in (
    select at.rowid from ancestrytable as at 
    inner join citationtable as ct on at.rmid = ct.CitationID 
    inner join sourcetable as st using (sourceid)
    inner join addresslinktable as alt on alt.ownerid = st.sourceid 
    where st.TemplateID = 439      -- Internal Ancestry source template
        and st.sourceid != 50      -- My FamilySearch person source uses the ancestry source template, keep it
        and alt.OwnerType = 3      -- Source
        and alt.addressid != 7     -- My FamilySearch repository - any other sources pulled from FS that use the ancestry template
        and at.LinkType = 4        -- Citation
);

delete from citationlinktable where rowid in (
    select clt.rowid from citationlinktable as clt 
    inner join citationtable as ct using (citationid) 
    inner join sourcetable as st using (sourceid)
    inner join addresslinktable as alt on alt.ownerid = st.sourceid 
    where st.TemplateID = 439 
        and st.sourceid != 50 
        and alt.OwnerType = 3
        and alt.addressid != 7
);

delete from citationtable where rowid in (
    select ct.rowid from citationtable as ct 
    inner join sourcetable as st using (sourceid)
    inner join addresslinktable as alt on alt.ownerid = st.sourceid 
    where st.TemplateID = 439 
        and st.sourceid != 50 
        and alt.OwnerType = 3
        and alt.addressid != 7
);

delete from sourcetable where rowid in (
    select distinct st.rowid from sourcetable as st
    inner join addresslinktable as alt on alt.ownerid = st.sourceid 
    where st.TemplateID = 439 
        and st.sourceid != 50 
        and alt.OwnerType = 3
        and alt.addressid != 7
);