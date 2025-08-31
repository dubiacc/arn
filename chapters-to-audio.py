# To run this code you need to install the following dependencies:
# pip install google-genai

import os
import asyncio
import math
import struct
from typing import List, Tuple

from google import genai
from google.genai import types

# --- Configuration ---
# Number of concurrent live streams to run.
MAX_WORKERS = 40
# Source folder containing subdirectories like "Gen1", "Exo2", etc.
INPUT_FOLDER = "chapters"
# Destination folder for the output .wav files.
OUTPUT_FOLDER = "wav"
# Style instructions for the TTS model.
STYLE_PROMPT = "Read aloud in a warm and friendly tone, but a touch faster than usual: "
# Voice and Model selection.
VOICE_NAME = "Charon"
MODEL_NAME = "models/gemini-2.5-flash-live-preview"
# A dictionary for text replacements.
REPLACEMENTS = {
    # "1.Mose" : "Erstes Buch Mose"
}

# --- Live API Configuration ---
# These settings are critical for text-only input to return audio.
LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],  # We only need the audio data as output.
    speech_config=types.SpeechConfig(
        language_code="de-DE",  # German (Germany)
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
        )
    ),
)


# --- Utility Functions (from your script) ---
def save_binary_file(file_name, data):
    """Saves binary data to a file."""
    try:
        with open(file_name, "wb") as f:
            f.write(data)
        # Return a success message including just the filename for cleaner logs
        return f"File saved to: {os.path.basename(file_name)}"
    except IOError as e:
        return f"Error saving file {os.path.basename(file_name)}: {e}"

def convert_to_wav(audio_data: bytes) -> bytes:
    """Generates a WAV file header for the given raw audio data (L16 format)."""
    sample_rate = 24000
    bits_per_sample = 16
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size
    )
    return header + audio_data


# --- Core Processing Logic ---

def find_files_to_process(input_dir: str, output_dir: str) -> List[Tuple[str, str]]:
    """
    Recursively finds all .txt files and creates a list of (source, destination)
    pairs, skipping files that have already been converted.
    """
    tasks = []
    print(f"Searching for .txt files in '{input_dir}'...")
    for root, _, files in os.walk(input_dir):
        for file in sorted(files): # Sort files for predictable order
            if file.endswith(".txt"):
                source_path = os.path.join(root, file)
                # Create a corresponding path in the output directory
                relative_path = os.path.relpath(source_path, input_dir)
                # Change the extension to .wav for the output file
                output_filename = os.path.splitext(relative_path)[0] + ".wav"
                dest_path = os.path.join(output_dir, output_filename)

                # Caching: Skip if the WAV file already exists
                if os.path.exists(dest_path):
                    continue

                # Ensure the output directory for this file exists
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                tasks.append((source_path, dest_path))
    return tasks

async def process_chapter_in_stream(session, txt_filepath: str) -> bytes:
    """
    Sends a single chapter's text through the live stream and collects the audio response.
    """
    with open(txt_filepath, "r", encoding="utf-8") as f:
        text_content = f.read()

    # Apply replacements and style prompt
    for old, new in REPLACEMENTS.items():
        text_content = text_content.replace(old, new)
    full_text_for_api = f"{STYLE_PROMPT}{text_content}"

    if len(full_text_for_api) > 5000:
        print(f"Warning: File {os.path.basename(txt_filepath)} is long and might exceed API limits.")

    # Use `send_client_content` to send the text as a complete turn.
    await session.send_client_content(
        turns=types.Content(parts=[types.Part(text=full_text_for_api)])
    )

    audio_chunks = []
    # Receive the complete audio response for the text we just sent.
    turn = session.receive()
    async for response in turn:
        # We only care about the audio data, ignoring any text responses.
        if data := response.data:
            audio_chunks.append(data)

    return b"".join(audio_chunks)

async def worker(worker_id: int, tasks: List[Tuple[str, str]]):
    """
    A worker that establishes a single live stream connection and processes a
    list of text files.
    """
    print(f"[Worker {worker_id}] starting, assigned {len(tasks)} files.")
    try:
        # Initialize the API client for this async worker.
        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=os.environ.get("GEMINI_API_KEY"),
        )

        async with client.aio.live.connect(model=MODEL_NAME, config=LIVE_CONFIG) as session:
            for txt_filepath, output_filepath in tasks:
                try:
                    print(f"[Worker {worker_id}] Processing: {os.path.relpath(txt_filepath)}")
                    raw_audio = await process_chapter_in_stream(session, txt_filepath)

                    if not raw_audio:
                        print(f"[Worker {worker_id}] No audio data received for {os.path.basename(txt_filepath)}.")
                        continue

                    # File I/O is blocking, so run it in a separate thread.
                    def process_and_save():
                        wav_data = convert_to_wav(raw_audio)
                        return save_binary_file(output_filepath, wav_data)

                    result = await asyncio.to_thread(process_and_save)
                    print(f"[Worker {worker_id}] {result}")

                except Exception as e:
                    print(f"[Worker {worker_id}] ERROR processing {os.path.basename(txt_filepath)}: {e}")

    except Exception as e:
        print(f"[Worker {worker_id}] FATAL ERROR: {e}")

async def main():
    """Main function to find and distribute all processing tasks."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        return

    # 1. Find all files that need to be processed
    all_tasks = find_files_to_process(INPUT_FOLDER, OUTPUT_FOLDER)

    if not all_tasks:
        print(f"No new .txt files found to process in '{INPUT_FOLDER}'. All files are up to date.")
        return

    print(f"Found {len(all_tasks)} new files to process.")

    # 2. Distribute tasks among workers
    num_workers = min(MAX_WORKERS, len(all_tasks))
    if num_workers == 0:
        return
        
    tasks_per_worker = math.ceil(len(all_tasks) / num_workers)
    task_chunks = [
        all_tasks[i:i + tasks_per_worker]
        for i in range(0, len(all_tasks), tasks_per_worker)
    ]

    # 3. Create and run worker tasks concurrently
    print(f"Starting {len(task_chunks)} workers to process the files...")
    worker_tasks = []
    for i, chunk in enumerate(task_chunks):
        worker_tasks.append(asyncio.create_task(worker(i + 1, chunk)))

    await asyncio.gather(*worker_tasks)
    print("\nAll tasks completed.")

if __name__ == "__main__":
    # Ensure source and destination folders exist
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Run the main asynchronous event loop
    asyncio.run(main())