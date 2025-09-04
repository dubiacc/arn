import json
import re
import argparse
import asyncio
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

# --- MAIN CONFIGURATION ---
# These are the 75th percentile thresholds from your analysis.
# Any chunk with an error rate HIGHER than this will be flagged for removal.
THRESHOLD_NT = 0.036
THRESHOLD_OT = 0.057

# --- File and Directory Paths ---
OUTPUT_DIR = Path("audio-check")
WAV_DIR = Path("wav")
REMOVAL_LIST_JSON = OUTPUT_DIR / "files_to_remove.json"

# --- Filtering Configuration ---
# These must match the lists in your analysis script.
NEW_TESTAMENT_BOOKS = {
    "Mt", "Mk", "Lk", "Joh", "Apg", "Roem", "1Kor", "2Kor", "Gal", "Eph",
    "Phil", "Kol", "1Thess", "2Thess", "1Tim", "2Tim", "Tit", "Phlm",
    "Hebr", "Jak", "1Petr", "2Petr", "1Joh", "2Joh", "3Joh", "Jud", "Offb"
}
OLD_TESTAMENT_BOOKS = {
    "Gen", "Ex", "Lev", "Num", "Dtn", "Jos", "Ri", "Rut", "1Sam", "2Sam",
    "1Koen", "2Koen", "1Chr", "2Chr", "Esra", "Neh", "Tob", "Jdt", "Est",
    "1Makk", "2Makk", "Ijob", "Ps", "Spr", "Koh", "Hld", "Weish", "Sir",
    "Jes", "Jer", "Klgl", "Bar", "Ez", "Dan", "Hos", "Joel", "Am", "Obd",
    "Jona", "Mi", "Nah", "Hab", "Zef", "Hag", "Sach", "Mal"
}


def normalize_text(text: str) -> str:
    """Normalizes text for comparison."""
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


async def main():
    """Main function to identify, list, and optionally remove flagged files."""
    parser = argparse.ArgumentParser(description="Identify and remove audio chunks based on Levenshtein error thresholds.")
    parser.add_argument(
        "--doit",
        action="store_true",
        help="Actually delete the .wav files. Without this flag, the script only generates a list."
    )
    parser.add_argument(
        "--sync-db",
        action="store_true",
        help="Actually remove entries from the Turso database. Requires the --doit flag."
    )
    args = parser.parse_args()

    # --- 1. Identify files to remove ---
    print("--- Starting Scan to Identify Files for Removal ---")
    all_results_files = [p for p in OUTPUT_DIR.rglob("*.json") if p.parent.name != OUTPUT_DIR.name]
    if not all_results_files:
        print(f"Error: No individual chunk JSON files found in '{OUTPUT_DIR}'.")
        return

    chunks_to_remove = []
    for f in tqdm(all_results_files, desc="Scanning JSON files"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            chapter_name = data.get("chapter")
            if not chapter_name: continue

            match = re.match(r'^([0-9]?[A-Za-z]+)', chapter_name)
            if not match: continue
            book_abbr = match.group(1)

            threshold = None
            if book_abbr in NEW_TESTAMENT_BOOKS:
                threshold = THRESHOLD_NT
            elif book_abbr in OLD_TESTAMENT_BOOKS:
                threshold = THRESHOLD_OT
            else:
                continue # Skip uncategorized books

            distance = data.get("levenshtein_distance", 0)
            original_text = data.get("original_text", "")
            text_length = len(normalize_text(original_text))
            
            raw_error_rate = distance / text_length if text_length > 0 else 1.0
            error_rate = min(1.0, raw_error_rate)

            if error_rate > threshold:
                chunks_to_remove.append({
                    "chapter": chapter_name,
                    "chunk": data.get("chunk"),
                    "wav_path": f"{WAV_DIR}/{chapter_name}/{data.get('chunk')}.wav",
                    "error_rate": error_rate,
                    "threshold": threshold
                })
        except (json.JSONDecodeError, IOError):
            pass # Ignore malformed files

    # --- 2. Generate the JSON report (Dry Run) ---
    print(f"\n--- Dry Run Summary ---")
    print(f"Identified {len(chunks_to_remove)} chunks exceeding their respective thresholds.")
    REMOVAL_LIST_JSON.write_text(json.dumps(chunks_to_remove, indent=4), encoding='utf-8')
    print(f"A detailed list of files to be removed has been saved to: '{REMOVAL_LIST_JSON}'")

    if not args.doit:
        print("\nThis was a dry run. No files were deleted.")
        print("To permanently delete these files, run the script again with the --doit flag.")
        return

    # --- 3. Perform Deletion if --doit is specified ---
    if chunks_to_remove:
        print("\n" + "="*50)
        print("!! WARNING: You have used the --doit flag. !!")
        print(f"This will permanently delete {len(chunks_to_remove)} .wav files.")
        confirmation = input("Type 'yes' to proceed with deletion: ")
        
        if confirmation.lower() == 'yes':
            deleted_count = 0
            for chunk in tqdm(chunks_to_remove, desc="Deleting WAV files"):
                wav_path = Path(chunk['wav_path'])
                if wav_path.exists():
                    wav_path.unlink()
                    deleted_count += 1
            print(f"\nSuccessfully deleted {deleted_count} .wav files.")

        else:
            print("\nDeletion aborted by user.")
    else:
        print("\nNo files to delete.")

if __name__ == "__main__":
    # Use asyncio.run() to execute the main async function
    asyncio.run(main())