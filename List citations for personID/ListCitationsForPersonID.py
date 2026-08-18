import sys
from pathlib import Path
sys.path.append(str(Path.resolve(Path(__file__).resolve().parent / '../RMpy package')))

import RMpy.common as RMc       # noqa #type: ignore
import RMpy.launcher            # noqa #type: ignore
from RMpy.common import q_str   # noqa #type: ignore

# Requirements:
#   RootsMagic database file
#   RM-Python-config.ini

# Tested with:
#   RootsMagic database file v10
#   Python for Windows v3.13

# Config files fields used
#    FILE_PATHS  REPORT_FILE_PATH
#    FILE_PATHS  REPORT_FILE_DISPLAY_APP
#    FILE_PATHS  DB_PATH
#    RIN         PERSON_RIN (optional)


# ===================================================DIV60==
def main():

    # Configuration
    utility_info = {}
    utility_info["utility_name"]      = "ListCitationsForPersonID" 
    utility_info["utility_version"] = "UTILITY_VERSION_NUMBER_RM_UTILS_OVERRIDE"
    utility_info["config_file_name"]  = "RM-Python-config.ini"
    utility_info["script_path"]  = Path(__file__).parent
    utility_info["run_features_function"]  = run_selected_features
    utility_info["allow_db_changes"]  = False
    utility_info["RMNOCASE_required"] = False
    utility_info["RMNOCASE_optional"] = False
    utility_info["RegExp_required"]   = False
    utility_info["RegExp_optional"]   = False

    RMpy.launcher.launcher(utility_info)


# ===================================================DIV60==
def run_selected_features(config, db_connection, report_file):

    display_sources_feature(config, db_connection, report_file)


# ===================================================DIV60==
def display_sources_feature(config, db_connection, report_file):

    PersonID = None
    try:
        PersonID_str = config['RIN']['PERSON_RIN']
        PersonID = int(PersonID_str)

    except:
        pass

    rows = RMc.get_all_citations(db_connection, PersonID)

    report_file.write("PersonID = " + str(PersonID) + "\n")
    report_file.write(str(len(rows)) + " source citations found \n\n")

    for row in rows:
        report_file.write(row[0] + "\t\t" + row[1] + "\n\n")

    report_file.write(
        "================================================" "\n\n")

    return



# ===================================================DIV60==
# Call the "main" function
if __name__ == '__main__':
    main()

# ===================================================DIV60==
