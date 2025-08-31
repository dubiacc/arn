import os
import subprocess
import sys

# --- Configuration ---

# The root folder where your generated .wav files are stored.
# The script will scan this folder and all its subdirectories.
AUDIO_FOLDER = "wav"

# The root folder where your original .txt source files are stored.
# This is needed to calculate the input text cost.
SOURCE_FOLDER = "chapters"

# Supported audio file extensions to scan for.
SUPPORTED_EXTENSIONS = ('.wav',)

# --- Live API Pricing (per 1 Million Tokens) ---
# Source: As provided from your prompt.
COST_PER_MILLION_INPUT_TEXT_TOKENS = 0.50   # $0.35 for text input
COST_PER_MILLION_OUTPUT_AUDIO_TOKENS = 12.00  # $8.50 for audio output

# --- Token Estimation Constants ---
# According to Gemini documentation, audio is tokenized at a fixed rate.
TOKENS_PER_SECOND_OF_AUDIO = 32
# Text tokenization is variable. A common estimate for European languages is
# around 4-6 characters per token. We'll use 5 as a reasonable average.
# This is an ESTIMATE for the input cost.
CHARS_PER_INPUT_TOKEN_ESTIMATE = 4.0

# --- Main Script ---

def get_audio_duration(file_path):
    """
    Uses ffprobe to get the duration of an audio file in seconds.
    Returns the duration as a float or None if an error occurs.
    """
    command = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    try:
        # Execute the command
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding='utf-8')
        # Convert the string output to a float
        return float(result.stdout.strip())
    except FileNotFoundError:
        # This error means ffprobe is not installed or not in the PATH
        print("\n[ERROR] 'ffprobe' command not found.", file=sys.stderr)
        print("Please ensure FFmpeg is installed and accessible in your system's PATH.", file=sys.stderr)
        sys.exit(1) # Exit the script
    except subprocess.CalledProcessError as e:
        # This error means ffprobe ran but failed (e.g., corrupted file)
        print(f"\nWarning: Could not get duration for '{os.path.basename(file_path)}'.", file=sys.stderr)
        print(f"ffprobe error: {e.stderr.strip()}", file=sys.stderr)
        return None
    except ValueError:
        # This error means the output of ffprobe was not a valid number
        print(f"\nWarning: ffprobe returned non-numeric duration for '{os.path.basename(file_path)}'.", file=sys.stderr)
        return None


def main():
    """
    Main function to scan directories, sum durations and text lengths, and calculate total cost.
    """
    if not os.path.isdir(AUDIO_FOLDER):
        print(f"Error: The audio directory '{AUDIO_FOLDER}' was not found.", file=sys.stderr)
        return
    if not os.path.isdir(SOURCE_FOLDER):
        print(f"Error: The source text directory '{SOURCE_FOLDER}' was not found.", file=sys.stderr)
        return

    total_duration_seconds = 0.0
    total_input_characters = 0
    files_processed = 0
    files_skipped = 0

    print(f"Scanning for audio files in './{AUDIO_FOLDER}' and corresponding text in './{SOURCE_FOLDER}'...")

    # Recursively walk through the audio directory
    for root, _, files in os.walk(AUDIO_FOLDER):
        for filename in sorted(files):
            if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
                continue

            audio_file_path = os.path.join(root, filename)
            duration = get_audio_duration(audio_file_path)

            if duration is None:
                files_skipped += 1
                continue

            # Successfully processed audio file, now find the source text file
            total_duration_seconds += duration
            files_processed += 1

            # Construct the path to the corresponding source .txt file
            relative_path = os.path.relpath(audio_file_path, AUDIO_FOLDER)
            source_txt_relative_path = os.path.splitext(relative_path)[0] + '.txt'
            source_txt_path = os.path.join(SOURCE_FOLDER, source_txt_relative_path)

            if os.path.exists(source_txt_path):
                try:
                    with open(source_txt_path, 'r', encoding='utf-8') as f:
                        total_input_characters += len(f.read())
                except Exception as e:
                    print(f"Warning: Could not read source file '{source_txt_path}': {e}", file=sys.stderr)
            else:
                print(f"Warning: Source file not found for '{audio_file_path}' at '{source_txt_path}'", file=sys.stderr)


    if files_processed == 0:
        print("\nNo valid audio files were found to analyze.")
        return

    # --- Calculations ---
    total_minutes = total_duration_seconds / 60

    # Output Audio Cost
    total_output_audio_tokens = total_duration_seconds * TOKENS_PER_SECOND_OF_AUDIO
    output_audio_cost = (total_output_audio_tokens / 1_000_000) * COST_PER_MILLION_OUTPUT_AUDIO_TOKENS

    # Input Text Cost (Estimated)
    estimated_input_text_tokens = total_input_characters / CHARS_PER_INPUT_TOKEN_ESTIMATE
    input_text_cost = (estimated_input_text_tokens / 1_000_000) * COST_PER_MILLION_INPUT_TEXT_TOKENS
    
    # Total Cost
    total_estimated_cost = output_audio_cost + input_text_cost

    # --- Display Results ---
    print("\n--- Live API Cost Estimation Summary ---")
    print(f"Files Processed Successfully: {files_processed}")
    if files_skipped > 0:
        print(f"Files Skipped (due to errors): {files_skipped}")
    
    print("\nTotal Duration:")
    print(f"  {total_duration_seconds:,.2f} seconds")
    print(f"  {total_minutes:.2f} minutes")
    
    print("\nCost Breakdown:")
    print(f"  Input Text ({int(estimated_input_text_tokens):,} tokens*):".ljust(30) + f"${input_text_cost:8.4f}")
    print(f"  Output Audio ({int(total_output_audio_tokens):,} tokens):".ljust(30) + f"${output_audio_cost:8.4f}")
    print(f"  {'':-<38}")
    print(f"  Total Estimated Cost:".ljust(30) + f"${total_estimated_cost:8.4f}")
    print("------------------------------------------")
    print(f"* Input token count is an estimate based on ~{CHARS_PER_INPUT_TOKEN_ESTIMATE} chars/token.")


if __name__ == "__main__":
    main()