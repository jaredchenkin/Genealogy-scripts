import sys
from pathlib import Path
sys.path.append(str(Path.resolve(Path(__file__).resolve().parents[1] / "RMpy package")))
import xml.etree.cElementTree as ET
import RMpy.common as RM  # noqa #type: ignore
import RMpy.customization as Cust
from RMpy.facts import Fact

def customize_ancestry_trees(conn):
    f = Fact(
        Cust.ANCESTRY_TREE_FACT.name,
        RM.OwnerType.PERSON,
        Cust.ANCESTRY_TREE_FACT.name,
        use_value=False,
        use_place=False,
        use_date=False,
        sentence="[person] is linked to other trees on Ancestry.",
        to_gedcom=False,
        to_web=False
    )
    f.create(conn)
    return f

def main():
    config = RM.get_config()

    with RM.create_db_connection(
        config["FILE_PATHS"]["DB_PATH"], [config["FILE_PATHS"]["RMNOCASE_PATH"]]
    ) as conn:    
        customize_ancestry_trees(conn)

if __name__ == "__main__":
    main()
