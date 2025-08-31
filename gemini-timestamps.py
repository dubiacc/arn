# pip install google-cloud-speech

import os
from google.cloud import speech

# --- Configuration for Transcription ---

# Path to your Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./gemini-cred.json"

def get_verse_timestamps(audio_file_path, original_text_file_path):
    """
    Transcribes an audio file to get word-level timestamps and
    aligns them with verses from the original text file.
    """
    client = speech.SpeechClient()

    with open(audio_file_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        sample_rate_hertz=16000,  # This might need adjustment based on your MP3s
        language_code="de-DE",
        enable_word_time_offsets=True,
    )

    print(f"Transcribing {audio_file_path}...")
    response = client.recognize(config=config, audio=audio)

    # Read the original verses
    with open(original_text_file_path, "r", encoding="utf-8") as f:
        verses = [line.strip() for line in f if line.strip()]

    # Process the transcription results
    timed_words = []
    for result in response.results:
        for word_info in result.alternatives[0].words:
            timed_words.append(
                {
                    "word": word_info.word,
                    "start_time": word_info.start_time.total_seconds(),
                    "end_time": word_info.end_time.total_seconds(),
                }
            )

    # --- Alignment Logic ---
    # This is a conceptual part. You'll need to match the transcribed words
    # to the words in your original verses to find the start and end times.
    
    verse_timestamps = []
    word_index = 0
    
    for i, verse in enumerate(verses):
        verse_words = verse.split()
        num_verse_words = len(verse_words)
        
        if word_index < len(timed_words):
            start_time = timed_words[word_index]["start_time"]
            
            # Find the end of the verse
            end_word_index = word_index + num_verse_words - 1
            if end_word_index < len(timed_words):
                end_time = timed_words[end_word_index]["end_time"]
                
                verse_timestamps.append({
                    "verse_number": i + 1,
                    "verse_text": verse,
                    "start_time": start_time,
                    "end_time": end_time
                })
                
                word_index += num_verse_words
            else:
                print(f"Warning: Ran out of timed words for verse {i+1}")

    return verse_timestamps

if __name__ == "__main__":
    # Example usage for one file
    audio_file = "Gen1.mp3"
    text_file = "Gen1.txt"
    
    if os.path.exists(audio_file) and os.path.exists(text_file):
        timestamps = get_verse_timestamps(audio_file, text_file)
        for ts in timestamps:
            print(
                f"Verse {ts['verse_number']}: "
                f"Start: {ts['start_time']:.3f}s, "
                f"End: {ts['end_time']:.3f}s - "
                f"'{ts['verse_text'][:50]}...'"
            )