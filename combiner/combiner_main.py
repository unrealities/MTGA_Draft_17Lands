import sys
import os
from combine_sets import SetCombiner

def check_paths(file_path1, file_path2):
    file_name1 = os.path.basename(file_path1)
    file_name2 = os.path.basename(file_path2)
    
    file1_parts = file_name1.split("_")
    file2_parts = file_name2.split("_")
    
    if file1_parts[0] != file2_parts[0]:
        print("Error: Datafiles must be from the same cardset.")
        sys.exit(1)
        
    if file1_parts[1] != file2_parts[1]:
        print("Error: Datafiles must be from the event type.")
        sys.exit(1) 


def main(file_path1, file_path2):
    check_paths(file_path1, file_path2)
    combiner = SetCombiner()
    combiner.load_json(file_path1)
    combiner.load_json(file_path2)
    combiner.combine_sets()
    combiner.get_combined(file_path1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python combine_sets.py <file_path1> <file_path2>"
        )
    else:
        main(sys.argv[1], sys.argv[2])
