import json
import subprocess
import os

def run_git_command(command):
    """
    Executes a shell command, prints its output, and handles errors.
    Returns True on success, False on failure.
    """
    print(f"Executing: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        # We will specifically ignore the "no changes added to commit" error later.
        # For other errors, we print them.
        print(f"Error executing command: {e}")
        print(f"Standard Output:\n{e.stdout}")
        print(f"Standard Error:\n{e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

# --- Configuration ---
# Set this to False to run the actual Git commands.
# It is highly recommended to do a dry run first.
DRY_RUN = False

# The name of your JSON file.
BIBLE_JSON_FILE = 'bible.json'

# The path to the directory containing your chapter folders.
AUDIO_FILES_BASE_PATH = 'wav'

# --- Main Script ---

if not os.path.exists(BIBLE_JSON_FILE):
    print(f"Error: The file '{BIBLE_JSON_FILE}' was not found in this directory.")
else:
    with open(BIBLE_JSON_FILE, 'r') as f:
        bible_data = json.load(f)

    print("Starting the git automation process...")
    if DRY_RUN:
        print("--- DRY RUN is ENABLED. No commands will be executed. ---")

    for book in bible_data:
        book_name = book.get("book_name")
        directory_name = book.get("directory_name")
        chapters = book.get("chapters", {})

        if not all([book_name, directory_name, chapters]):
            print(f"Skipping a record due to missing data: {book}")
            continue

        for chapter_number in chapters:
            chapter_directory_name = f"{directory_name}{chapter_number}"
            chapter_directory_path = os.path.join(AUDIO_FILES_BASE_PATH, chapter_directory_name)

            print("\n" + "="*50)
            print(f"Processing: {book_name} Chapter {chapter_number} (Directory: {chapter_directory_path})")
            print("="*50)
            
            if not os.path.isdir(chapter_directory_path):
                print(f"Warning: Directory '{chapter_directory_path}' not found. Skipping.")
                continue

            # Construct all git commands
            add_command = f'git add "{chapter_directory_path}"'
            commit_message = f"Update: {chapter_directory_name}"
            commit_command = f'git commit -m "{commit_message}"'
            push_command = 'git push'
            
            if DRY_RUN:
                print(f"WOULD RUN: {add_command}")
                print(f"WOULD RUN: {commit_command}")
                print(f"WOULD RUN: {push_command}")
                continue

            # --- Execute Commands with Change Detection ---
            
            # 1. Stage any new or modified files
            if not run_git_command(add_command):
                print(f"Failed to add files for {chapter_directory_name}. Halting script.")
                exit()

            # 2. NEW: Check if there are any staged changes
            # 'git diff --staged --quiet' exits with 0 if nothing is staged, 1 if there are.
            check_changes_command = "git diff --staged --quiet"
            result = subprocess.run(check_changes_command, shell=True, capture_output=True)

            # result.returncode will be 0 if there are NO changes
            if result.returncode == 0:
                print(f"No changes detected for {chapter_directory_name}. Skipping commit and push.")
                continue  # Move to the next chapter

            # 3. If we are here, it means there are changes to commit.
            print(f"Changes detected. Proceeding with commit and push for {chapter_directory_name}.")

            # Commit the staged changes
            if not run_git_command(commit_command):
                print(f"Failed to commit files for {chapter_directory_name}. Halting script.")
                exit()

            # Push the commit
            if not run_git_command(push_command):
                print(f"Failed to push changes for {chapter_directory_name}. Halting script.")
                exit()

    print("\nAll tasks completed successfully!")