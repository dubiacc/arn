import asyncio
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

# --- Configuration ---
WAV_DIR = Path("wav")
CHAPTERS_DIR = Path("chapters")
OUTPUT_DIR = Path("audio-check")
FINAL_REPORT_FILE = OUTPUT_DIR / "report.json"
DEFICIENT_THRESHOLD_PERCENT = 50
NUM_WORKERS = 20  # Number of audio files to process concurrently
LOCALE = "de-DE"

def normalize_text(text: str) -> str:
    """
    Normalizes text for comparison by making it lowercase, removing punctuation,
    and collapsing whitespace.
    """
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates the Levenshtein distance between two strings using a
    dynamic programming approach. Does not require any external modules.
    """
    m, n = len(s1), len(s2)
    if m == 0: return n
    if n == 0: return m

    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for j in range(n + 1):
        dp[0][j] = j
    for i in range(m + 1):
        dp[i][0] = i

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1,        # Deletion
                           dp[i][j - 1] + 1,        # Insertion
                           dp[i - 1][j - 1] + cost) # Substitution

    return dp[m][n]

async def run_hear_transcription(wav_file: Path) -> str:
    """
    Asynchronously runs the 'hear' command and returns the transcribed text.
    """
    command = ["hear", "-d", "-i", str(wav_file), "-l", LOCALE]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            # Using tqdm.write is thread-safe for printing from workers
            tqdm.write(f"Warning: 'hear' failed for {wav_file}. Stderr: {stderr.decode().strip()}")
            return ""
        
        return stdout.decode().strip()
    except FileNotFoundError:
        # This will only happen once if 'hear' is not installed.
        raise
    except Exception as e:
        tqdm.write(f"An unexpected error occurred processing {wav_file}: {e}")
        return ""

async def process_chunk(wav_path: Path):
    """
    The complete processing logic for a single audio chunk.
    """
    relative_path = wav_path.relative_to(WAV_DIR)
    chapter_name = wav_path.parts[-2]
    chunk_name = wav_path.stem
    
    txt_path = CHAPTERS_DIR / relative_path.with_suffix(".txt")
    output_json_path = OUTPUT_DIR / chapter_name / f"{chunk_name}.json"

    if not txt_path.exists():
        tqdm.write(f"Warning: No matching text file for {wav_path}. Skipping.")
        return

    # Run transcription
    transcribed_text = await run_hear_transcription(wav_path)
    
    # Read and process original text
    original_text = txt_path.read_text(encoding='utf-8')
    norm_original = normalize_text(original_text)
    norm_transcribed = normalize_text(transcribed_text)
    distance = levenshtein_distance(norm_original, norm_transcribed)

    # Prepare and save the result JSON
    chunk_data = {
        "chapter": chapter_name,
        "chunk": chunk_name,
        "levenshtein_distance": distance,
        "original_text": original_text.strip(),
        "transcribed_text": transcribed_text,
    }
    
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(chunk_data, indent=4), encoding='utf-8')

async def worker(name: str, queue: asyncio.Queue, pbar: tqdm):
    """
    A worker task that consumes file paths from the queue and processes them.
    """
    while True:
        try:
            wav_path = await queue.get()
            await process_chunk(wav_path)
            pbar.update(1)
            queue.task_done()
        except asyncio.CancelledError:
            # The worker was cancelled, exit the loop
            break

async def main():
    """
    Main function to set up the async workers and orchestrate the process.
    """
    if not shutil.which("hear"):
        print("Error: The 'hear' command was not found in your system's PATH.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # --- Phase 1: Asynchronous Processing ---
    print("Scanning for audio files to process...")
    all_wav_files = sorted(list(WAV_DIR.rglob("*.wav")))
    
    # Filter out files that already have a result JSON
    files_to_process = []
    for wav_path in all_wav_files:
        output_json_path = OUTPUT_DIR / wav_path.parts[-2] / f"{wav_path.stem}.json"
        if not output_json_path.exists():
            files_to_process.append(wav_path)
            
    if not files_to_process:
        print("All audio chunks already have analysis results.")
    else:
        print(f"Found {len(files_to_process)} new audio chunks to process.")
        queue = asyncio.Queue()
        for wav_path in files_to_process:
            queue.put_nowait(wav_path)

        with tqdm(total=len(files_to_process), desc="Processing Chunks") as pbar:
            # Create and start worker tasks
            tasks = [
                asyncio.create_task(worker(f"Worker-{i}", queue, pbar))
                for i in range(NUM_WORKERS)
            ]

            # Wait for the queue to be fully processed
            await queue.join()

            # All work is done, cancel the worker tasks
            for task in tasks:
                task.cancel()
            
            # Wait for all tasks to finish their cancellation
            await asyncio.gather(*tasks, return_exceptions=True)

    # --- Phase 2: Synchronous Reporting (runs after all async work is done) ---
    generate_report_and_analyze()

def generate_report_and_analyze():
    """
    Finds all individual JSON results, aggregates them into a final report,
    and prints a deficiency analysis to the console.
    """
    print("\n--- Generating Final Report and Analysis ---")
    
    all_results_files = [p for p in OUTPUT_DIR.rglob("*.json") if p.name != FINAL_REPORT_FILE.name]
    
    if not all_results_files:
        print("No chunk results found to analyze.")
        return

    full_report_data = []
    for f in sorted(all_results_files): # Sort for consistent report order
        try:
            full_report_data.append(json.loads(f.read_text(encoding='utf-8')))
        except json.JSONDecodeError:
            print(f"Warning: Could not read malformed JSON file: {f}")

    FINAL_REPORT_FILE.write_text(json.dumps(full_report_data, indent=4), encoding='utf-8')
    print(f"Final report generated at: '{FINAL_REPORT_FILE}'")

    print("\n--- Deficiency Analysis ---")
    chapter_stats = defaultdict(lambda: {"total": 0, "deficient": 0})
    for res in full_report_data:
        chapter = res["chapter"]
        chapter_stats[chapter]["total"] += 1
        if res["levenshtein_distance"] > 0:
            chapter_stats[chapter]["deficient"] += 1

    problematic_chapters = []
    for chapter, stats in sorted(chapter_stats.items()):
        total = stats["total"]
        deficient = stats["deficient"]
        deficiency_rate = (deficient / total) * 100 if total > 0 else 0
        
        print(f"Chapter '{chapter}': {deficient}/{total} deficient chunks ({deficiency_rate:.1f}%).")
        if deficiency_rate > DEFICIENT_THRESHOLD_PERCENT:
            problematic_chapters.append(chapter)

    print("\n--- Summary ---")
    if problematic_chapters:
        print(f"The following chapters have over {DEFICIENT_THRESHOLD_PERCENT}% deficient chunks:")
        for chapter in problematic_chapters:
            print(f" - {chapter}")
    else:
        print(f"No chapters exceeded the {DEFICIENT_THRESHOLD_PERCENT}% deficiency threshold.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
