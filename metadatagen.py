import os
import asyncio
import json
import math
import sys
from typing import List, Dict, Any, Tuple
import re

from google import genai
from google.genai import types

# --- Globale Daten & Konfiguration ---

def load_bible_data(filepath: str) -> list:
    """
    Lädt die Bibel-Strukturdaten aus einer JSON-Datei.

    Args:
        filepath: Der Pfad zur JSON-Datei.

    Returns:
        Eine Liste mit den Bibel-Daten oder eine leere Liste bei einem Fehler.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Bibel-Struktur erfolgreich aus '{filepath}' geladen.")
        return data
    except FileNotFoundError:
        print(f"FEHLER: Die Datendatei '{filepath}' wurde nicht gefunden.")
        sys.exit(1) # Beendet das Skript, da die Daten essenziell sind.
    except json.JSONDecodeError:
        print(f"FEHLER: Die Datei '{filepath}' enthält kein gültiges JSON.")
        sys.exit(1) # Beendet das Skript.

def remove_empty_files(target_directory: str):
    """
    Durchsucht ein Verzeichnis rekursiv und löscht alle Dateien mit einer Größe von 0 Bytes.

    Args:
        target_directory: Der Pfad zum Verzeichnis, das bereinigt werden soll.
    """
    # 1. Überprüfen, ob das Verzeichnis überhaupt existiert, um Fehler zu vermeiden.
    if not os.path.isdir(target_directory):
        print(f"Info: Bereinigungs-Verzeichnis '{target_directory}' nicht gefunden, überspringe.")
        return

    print(f"\n--- Starte Bereinigung leerer Dateien in '{target_directory}' ---")
    files_removed_count = 0

    # 2. os.walk() durchläuft alle Ordner, Unterordner und Dateien.
    for dirpath, _, filenames in os.walk(target_directory):
        for filename in filenames:
            # 3. Den vollständigen Pfad zu jeder Datei erstellen.
            file_path = os.path.join(dirpath, filename)
            try:
                # 4. Prüfen, ob die Dateigröße exakt 0 ist.
                if os.path.getsize(file_path) == 0:
                    print(f"Lösche leere Datei: {file_path}")
                    # 5. Die leere Datei entfernen.
                    os.remove(file_path)
                    files_removed_count += 1
            except OSError as e:
                # Fängt Fehler ab, falls die Datei z.B. nicht mehr existiert oder keine Rechte bestehen.
                print(f"Fehler beim Entfernen von {file_path}: {e}")

    if files_removed_count > 0:
        print(f"Bereinigung abgeschlossen. {files_removed_count} leere Dateien entfernt.")
    else:
        print("Bereinigung abgeschlossen. Keine leeren Dateien gefunden.")
    print("----------------------------------------------------------\n")

BIBLE_DATA = load_bible_data("./bible.json")

# --- Konfiguration ---
MAX_WORKERS = 4
INPUT_FOLDER = "txt"
OUTPUT_FOLDER = "summaries"
MODEL_NAME = "models/gemini-2.5-flash-live-preview"

# --- Prompt-Vorlagen ---

# Vorlage für die kapitel-spezifischen Metadaten.
CHAPTER_PROMPT_TEMPLATE = """
Du bist ein Experte für die Erstellung von ansprechenden YouTube-Inhalten und SEO für religiöse Texte.
Basierend auf dem Text von {book_name}, Kapitel {chapter_number}, generiere ein JSON-Objekt mit den Schlüsseln: "video_title", "summary", "tags", und "seo_keywords".

- "video_title": Ein fesselnder, prägnanter Titel für ein YouTube-Video dieses Kapitels, sehr kurz und prägnant. Fange immer an mit dem Kapitelnamen an - Beispiel: "Genesis 1: Die Erschaffung der Welt"
- "summary": Eine sehr kurze, faktische Zusammenfassung der wichtigsten Ereignisse, Themen und Personen (aus traditionell-katholischer Sicht, nicht neutral geschrieben - erwähne hier aber nicht direkt das Wort "katholisch" beim Namen, gehe auch nicht auf Interpretationen ein). Dieser Abschnitt muss sehr kurz und eher faktisch sein, der "katholische" Teil ist eher ein theologischer Touch, aber sollte nicht extensiv sein. Vermeide alle Wörter, die bei YouTube anstößig sein können, umschreibe Morde und sexuelle Ereignisse.
- "tags": Eine Liste von 5-10 relevanten YouTube-Tags als Array von Strings.
- "seo_keywords": Eine Liste von 10-15 SEO-Schlüsselwörtern als Array von Strings.

Die Ausgabe muss ausschließlich ein gültiges JSON-Objekt sein. Keine Markdown-Formatierung.

Text für {book_name}, Kapitel {chapter_number}:
---
{chapter_text}
---
"""

# Vorlage für die buch-spezifischen Playlist-Metadaten.
PLAYLIST_PROMPT_TEMPLATE = """
Du bist ein Experte für die Erstellung von ansprechenden YouTube-Inhalten für biblische Texte.
Basierend auf dem Text des des Buches "{book_name}", erstelle die Metadaten für eine YouTube-Playlist, die ALLE Kapitel dieses Buches enthalten wird. Generiere ein JSON-Objekt mit den Schlüsseln: "playlist_title" und "playlist_description".

- "playlist_title": Ein klarer und ansprechender Titel für die Playlist (z.B. "Das Buch Genesis - Alle Kapitel | Hörbuch").
- "playlist_description": Eine kurze Beschreibung, die die zentralen Themen, Charaktere und die Bedeutung des gesamten Buches {book_name} zusammenfasst - unter 500 Zeichen, faktisch und sachlich. Worum geht es in diesem Buch?

Die Ausgabe muss ausschließlich ein gültiges JSON-Objekt sein. Keine Markdown-Formatierung.

Text von {book_name} als Kontext:
---
{chapter_text}
---
"""

# --- Live API Konfiguration ---
LIVE_CONFIG = types.LiveConnectConfig(response_modalities=["TEXT"])


# --- Hilfsfunktionen ---

def clean_markdown_artifacts(data_str: str) -> str:
    """
    Entfernt Markdown-Codeblock-Markierungen (z.B. ```json ... ```) von einem String.

    Diese Funktion ist darauf ausgelegt, JSON-Strings zu bereinigen, die fälschlicherweise
    von einer KI in einem Markdown-Block zurückgegeben wurden. Sie ist robust
    gegenüber Leerzeichen und verschiedenen Sprachbezeichnern.

    Args:
        data_str: Der potenziell "verschmutzte" Eingabe-String.

    Returns:
        Der bereinigte String, der nur noch den Inhalt des Code-Blocks enthalten sollte.
        Gibt den ursprünglichen String (nur bereinigt von Leerzeichen) zurück,
        wenn keine Markdown-Markierungen gefunden werden.
    """
    # Überprüft, ob der Input überhaupt ein String ist.
    if not isinstance(data_str, str):
        return data_str

    # Das Muster sucht nach einem optionalen Sprachbezeichner (wie 'json')
    # und extrahiert den gesamten Inhalt dazwischen. re.DOTALL lässt `.` auch Zeilenumbrüche matchen.
    # Pattern: ```[language]\n(CONTENT)\n```
    pattern = re.compile(r"^\s*```(?:[a-zA-Z]*)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)
    
    match = pattern.search(data_str)

    if match:
        # Wenn ein Match gefunden wird, gib die erste Capturing Group (den Inhalt) zurück.
        # Ein zusätzliches .strip() entfernt eventuelle Rest-Leerzeichen.
        return match.group(1).strip()
    else:
        # Wenn kein Markdown-Block gefunden wurde, gib einfach den von
        # Leerzeichen bereinigten Original-String zurück.
        return data_str.strip()
    
def save_json_file(file_name: str, data_str: str):
    """Speichert einen String, der JSON enthält, formatiert in einer Datei."""
    try:
        # Sicherstellen, dass das Verzeichnis existiert
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, "w", encoding="utf-8") as f:
            json_obj = json.loads(data_str)
            json.dump(json_obj, f, ensure_ascii=False, indent=4)
        return f"Datei gespeichert: {os.path.basename(file_name)}"
    except (IOError, json.JSONDecodeError) as e:
        return f"Fehler beim Speichern von {os.path.basename(file_name)}: {e}: {data_str}"

# --- Kernlogik ---

def find_tasks_to_process() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Findet alle fehlenden Metadaten-Dateien und erstellt eine Aufgabenliste.
    Eine Playlist-Aufgabe wird nur erstellt, wenn alle Kapitel-JSONs vorhanden sind.
    """
    tasks = []
    print("Suche nach fehlenden Metadaten-Dateien...")
    for book in BIBLE_DATA:
        book_name = book["book_name"]
        dir_name = book["directory_name"]
        dest_book_dir = os.path.join(OUTPUT_FOLDER, dir_name)

        # Zuerst nach fehlenden Kapiteln suchen, da diese eine Voraussetzung sind
        all_chapters_exist = True
        chapter_json_paths = []
        for chapter_num_str in book["chapters"].keys():
            chapter_num = int(chapter_num_str)
            chapter_dest_path = os.path.join(dest_book_dir, f"{chapter_num}.json")
            source_txt_path = os.path.join(INPUT_FOLDER, f"{dir_name}{chapter_num}.txt")
            
            chapter_json_paths.append(chapter_dest_path) # Pfad für später sammeln

            if not os.path.exists(chapter_dest_path):
                all_chapters_exist = False # Markieren, dass Playlist noch nicht erstellt werden kann
                # Aufgabe für fehlendes Kapitel erstellen, wenn die Textquelle existiert
                if os.path.exists(source_txt_path):
                    payload = {
                        "book_name": book_name,
                        "chapter_number": chapter_num,
                        "source_path": source_txt_path,
                        "output_path": chapter_dest_path
                    }
                    tasks.append(('chapter', payload))

        # Jetzt prüfen, ob eine Playlist-Aufgabe erstellt werden kann
        playlist_dest_path = os.path.join(dest_book_dir, "playlist_info.json")
        if not os.path.exists(playlist_dest_path) and all_chapters_exist:
            # Nur erstellen, wenn die Playlist-Datei fehlt UND alle Kapitel-JSONs da sind
            print(f"Alle Kapitel für '{book_name}' sind vorhanden. Erstelle Playlist-Aufgabe.")
            payload = {
                "book_name": book_name,
                "chapter_json_paths": chapter_json_paths, # Liste aller Kapitel-JSON-Pfade
                "output_path": playlist_dest_path
            }
            tasks.append(('playlist', payload))

    return tasks

async def process_task_in_stream(session, task_type: str, payload: Dict[str, Any]) -> str:
    """Sendet den Text basierend auf dem Aufgabentyp und sammelt die Antwort."""
    prompt = ""
    if task_type == 'chapter':
        with open(payload["source_path"], "r", encoding="utf-8") as f:
            text_content = f.read()
        prompt = CHAPTER_PROMPT_TEMPLATE.format(
            book_name=payload["book_name"],
            chapter_number=payload["chapter_number"],
            chapter_text=text_content
        )
    elif task_type == 'playlist':
        # Sammelt den Inhalt aus allen Kapitel-JSONs
        combined_summaries = []
        for json_path in payload["chapter_json_paths"]:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Formatiert den Titel und die Zusammenfassung für den Kontext
                    title = data.get("video_title", "Unbekannter Titel")
                    summary = data.get("summary", "Keine Zusammenfassung verfügbar.")
                    combined_summaries.append(f"{title}\nZusammenfassung: {summary}\n")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warnung: Konnte {json_path} nicht lesen oder parsen: {e}")
        
        # Fügt alle Texte zu einem großen Kontext-Block zusammen
        full_book_context = "\n---\n".join(combined_summaries)

        prompt = PLAYLIST_PROMPT_TEMPLATE.format(
            book_name=payload["book_name"],
            chapter_text=full_book_context  # Hier wird der zusammengefügte Text übergeben
        )

    await session.send_client_content(turns=types.Content(parts=[types.Part(text=prompt)]))
    turn = session.receive()
    response_parts = [text async for response in turn if (text := response.text)]
    return "".join(response_parts)

async def worker(worker_id: int, tasks: List[Tuple[str, Dict[str, Any]]]):
    """Ein Worker, der eine Liste von Aufgaben (Playlist oder Kapitel) verarbeitet."""
    print(f"[Worker {worker_id}] startet, {len(tasks)} Aufgaben zugewiesen.")
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        async with client.aio.live.connect(model=MODEL_NAME, config=LIVE_CONFIG) as session:
            for task_type, payload in tasks:
                try:
                    name = f"{payload['book_name']} Playlist" if task_type == 'playlist' else f"{payload['book_name']} Kap. {payload['chapter_number']}"
                    print(f"[Worker {worker_id}] Verarbeitet {task_type.upper()}: {name}")

                    json_response_str = await process_task_in_stream(session, task_type, payload)

                    if not json_response_str:
                        print(f"[Worker {worker_id}] Keine Antwort für {name} erhalten.")
                        continue

                    cleaned_json_str = clean_markdown_artifacts(json_response_str)

                    result = await asyncio.to_thread(save_json_file, payload["output_path"], cleaned_json_str)
                    print(f"[Worker {worker_id}] {result}")

                except Exception as e:
                    print(f"[Worker {worker_id}] FEHLER bei der Verarbeitung von {name}: {e}")
    except Exception as e:
        print(f"[Worker {worker_id}] FATALER FEHLER: {e}")

async def main():
    """Hauptfunktion zum Finden und Verteilen aller Verarbeitungsaufgaben."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Fehler: Die Umgebungsvariable GEMINI_API_KEY ist nicht gesetzt.")
        return

    remove_empty_files(OUTPUT_FOLDER)

    all_tasks = find_tasks_to_process()

    if not all_tasks:
        print("Alle Metadaten-Dateien sind bereits vorhanden und aktuell.")
        return

    print(f"{len(all_tasks)} neue Aufgaben gefunden (Playlists und Kapitel).")

    num_workers = min(MAX_WORKERS, len(all_tasks))
    tasks_per_worker = math.ceil(len(all_tasks) / num_workers)
    task_chunks = [
        all_tasks[i:i + tasks_per_worker]
        for i in range(0, len(all_tasks), tasks_per_worker)
    ]

    print(f"Starte {len(task_chunks)} Worker zur Verarbeitung...")
    worker_tasks = [asyncio.create_task(worker(i + 1, chunk)) for i, chunk in enumerate(task_chunks)]
    await asyncio.gather(*worker_tasks)
    print("\nAlle Aufgaben abgeschlossen.")

if __name__ == "__main__":
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    asyncio.run(main())