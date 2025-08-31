import os
import re

# --- Configuration ---
# Directory containing your Bible chapter .txt files (e.g., Gen1.txt)
INPUT_DIR = "txt"

# Directory where the new chapter folders and blocks will be created
OUTPUT_DIR = "chapters"

# The minimum number of words a block should have before a split is considered
MINIMUM_WORDS_PER_BLOCK = 50

def process_bible_chapters():
    """
    Reads Bible chapter files, splits them into smaller, evenly-sized
    blocks based on word count and sentence endings, and saves them
    in a structured directory layout.
    """
    # Create the main output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output will be saved in '{OUTPUT_DIR}' directory.")

    # Get a list of all .txt files from the input directory
    try:
        filenames = [f for f in os.listdir(INPUT_DIR) if f.endswith('.txt')]
        if not filenames:
            print(f"Error: No .txt files found in the '{INPUT_DIR}' directory.")
            print("Please make sure your chapter files are in the correct location.")
            return
    except FileNotFoundError:
        print(f"Error: Input directory '{INPUT_DIR}' not found.")
        print("Please create it and place your Bible chapter files inside.")
        return

    print(f"Found {len(filenames)} chapter files to process...")

    # Process each file
    for filename in sorted(filenames):
        # Extract the base name for the chapter (e.g., "Gen1")
        chapter_name = os.path.splitext(filename)[0]
        
        # Create a specific directory for this chapter's blocks
        chapter_output_dir = os.path.join(OUTPUT_DIR, chapter_name)
        os.makedirs(chapter_output_dir, exist_ok=True)

        print(f"\nProcessing {filename} -> {chapter_output_dir}")

        # Read all verses from the current chapter file
        input_filepath = os.path.join(INPUT_DIR, filename)
        with open(input_filepath, 'r', encoding='utf-8') as f:
            verses = f.readlines()

        # Variables to hold the state for the current chapter
        current_block_verses = []
        word_count = 0
        block_file_counter = 1

        # Iterate through each verse of the chapter
        for verse in verses:
            # Clean up the verse line
            cleaned_verse = verse.strip()
            if not cleaned_verse:
                continue

            # Add the verse to the current block and update the word count
            current_block_verses.append(cleaned_verse)
            word_count += len(cleaned_verse.split())

            # Check if conditions are met to save the block
            if word_count >= MINIMUM_WORDS_PER_BLOCK and cleaned_verse.endswith('.'):
                # Join the collected verses into a single string
                block_content = "\n".join(current_block_verses)
                
                # Define the output path for the new block file
                output_filename = f"{block_file_counter:03d}.txt"
                output_path = os.path.join(chapter_output_dir, output_filename)
                
                # Write the block to its file
                with open(output_path, 'w', encoding='utf-8') as out_f:
                    out_f.write(block_content)
                
                # Reset for the next block
                current_block_verses = []
                word_count = 0
                block_file_counter += 1

        # After the loop, save any remaining verses as the last block
        if current_block_verses:
            block_content = "\n".join(current_block_verses)
            output_filename = f"{block_file_counter:03d}.txt"
            output_path = os.path.join(chapter_output_dir, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.write(block_content)

    print("\n--- Processing complete! ---")

if __name__ == "__main__":
    process_bible_chapters()