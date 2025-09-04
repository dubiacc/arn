import json
import re
from pathlib import Path
from tqdm import tqdm

# --- Configuration ---
# The directory where your individual JSON results are stored.
OUTPUT_DIR = Path("audio-check")

# The number of words from the start of the original text to check for.
NUM_WORDS_TO_CHECK = 5

# The value to set the Levenshtein distance to if the condition is met.
FLAG_LEVENSHTEIN_VALUE = 999


def normalize_text(text: str) -> str:
    """
    Normalizes text for comparison by making it lowercase, removing punctuation,
    and collapsing whitespace.
    """
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def patch_files_with_intro_errors():
    """
    Scans all individual JSON files, identifies those with leading text
    in the transcription, and updates their Levenshtein distance to flag them.
    """
    print("--- Starting Scan to Patch Files with Introduction Errors ---")

    # Find all individual JSON results, excluding any top-level report files.
    all_results_files = [p for p in OUTPUT_DIR.rglob("*.json") if p.parent.name != OUTPUT_DIR.name]

    if not all_results_files:
        print(f"Error: No individual chunk JSON files found in '{OUTPUT_DIR}' subdirectories.")
        return

    print(f"Scanning {len(all_results_files)} result files...")

    modified_files_count = 0
    
    # Use tqdm for a progress bar, as this might take a moment.
    for file_path in tqdm(all_results_files, desc="Processing files"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            original_text = data.get("original_text")
            transcribed_text = data.get("transcribed_text")

            # Ensure both text fields exist
            if not original_text or not transcribed_text:
                continue

            # Normalize for a fair comparison
            norm_original = normalize_text(original_text)
            norm_transcribed = normalize_text(transcribed_text)

            original_words = norm_original.split()

            # Skip if the original text is too short to form a reliable snippet
            if len(original_words) < NUM_WORDS_TO_CHECK:
                continue

            # Create the snippet from the first 5 words of the original text
            original_snippet = " ".join(original_words[:NUM_WORDS_TO_CHECK])

            # The core logic:
            # 1. The German snippet IS in the transcription...
            # 2. ...BUT the transcription does NOT start with it.
            if original_snippet in norm_transcribed and not norm_transcribed.startswith(original_snippet):
                # This file matches the "English introduction" pattern.
                # Check if it needs updating to avoid unnecessary writes.
                if data.get("levenshtein_distance") != FLAG_LEVENSHTEIN_VALUE:
                    data["levenshtein_distance"] = FLAG_LEVENSHTEIN_VALUE
                    
                    # Overwrite the file with the new value
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                    
                    modified_files_count += 1

        except (json.JSONDecodeError, IOError) as e:
            # Using tqdm.write is safe for printing during a loop
            tqdm.write(f"Warning: Could not process file {file_path}. Error: {e}")
        except Exception as e:
            tqdm.write(f"An unexpected error occurred with file {file_path}: {e}")

    print("\n--- Patching Complete ---")
    print(f"Total files scanned: {len(all_results_files)}")
    print(f"Total files modified: {modified_files_count}")
    if modified_files_count > 0:
        print("\nRerun your main analysis script (V11) to generate updated reports.")
    else:
        print("\nNo files needed patching.")


if __name__ == "__main__":
    patch_files_with_intro_errors()