import sys
from pathlib import Path
sys.path.append(str(Path.resolve(Path(__file__).resolve().parent)))
import common as RM
import source_template as ST
from facts import Fact

VITAL_RECORDS = ST.Template("Vital Records (ancestry friendly)")
FAMILY_TREE = ST.Template("Family Trees, Documented")

ANCESTRY_TREE_FACT = Fact("Ancestry Trees")