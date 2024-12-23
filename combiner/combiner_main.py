import sys
from combine_sets import SetCombiner


def main(file_path1, file_path2, output_file_path):
    combiner = SetCombiner()
    combiner.load_json(file_path1)
    combiner.load_json(file_path2)
    combiner.combine_sets()
    combiner.get_combined(output_file_path)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: python combine_sets.py <file_path1> <file_path2> <output_file_path>"
        )
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
