import json
import re
import argparse
import sys

def get_abbreviations_from_txt(filepath):
    """Extracts unique book abbreviations from a given text file."""
    abbreviations = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    # Regex to capture the non-numeric part (the abbreviation)
                    # e.g., '1Thess5' -> '1Thess'
                    match = re.match(r'([1-3]?[A-Za-z]+)', line)
                    if match:
                        abbreviations.add(match.group(1))
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.", file=sys.stderr)
        sys.exit(1)
    return abbreviations

def get_directory_names_from_json(filepath):
    """Extracts 'directory_name' values from a given JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Use a set comprehension for efficient and duplicate-free extraction
            return {book['directory_name'] for book in data if 'directory_name' in book}
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: The file '{filepath}' is not a valid JSON file.", file=sys.stderr)
        sys.exit(1)
    except (TypeError, KeyError):
        print(f"Error: The JSON in '{filepath}' does not have the expected structure (a list of objects with 'directory_name' keys).", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function to parse arguments and run the comparison."""
    parser = argparse.ArgumentParser(
        description="Compare book abbreviations from a TXT file against 'directory_name' entries in a JSON file."
    )
    parser.add_argument("txt_file", help="Path to the .txt file containing the list of book chapters.")
    parser.add_argument("json_file", help="Path to the .json file containing the book data.")
    args = parser.parse_args()

    print(f"--- Checking consistency between '{args.txt_file}' and '{args.json_file}' ---")

    # 1. Get data from files
    txt_abbrevs = get_abbreviations_from_txt(args.txt_file)
    json_dirs = get_directory_names_from_json(args.json_file)

    # 2. Find inconsistencies
    in_txt_but_not_json = sorted(list(txt_abbrevs - json_dirs))
    in_json_but_not_txt = sorted(list(json_dirs - txt_abbrevs))

    # 3. Report results
    print("-" * 30)
    if not in_txt_but_not_json and not in_json_but_not_txt:
        print("✅ Success: All abbreviations and directory names are consistent.")
    else:
        if in_json_but_not_txt:
            print("❌ Found 'directory_name' entries in JSON that are missing from the TXT file:")
            for name in in_json_but_not_txt:
                print(f"  - {name}")
        
        if in_txt_but_not_json:
            print("\n❌ Found abbreviations in the TXT file that are missing from the JSON file:")
            for name in in_txt_but_not_json:
                print(f"  - {name}")
    print("-" * 30)


if __name__ == "__main__":
    main()