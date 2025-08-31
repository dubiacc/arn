import os
import json
import re
from collections import defaultdict

# 1. Kanonische Reihenfolge der Bücher des katholischen Kanons (Altes und Neues Testament)
# Diese Liste definiert die Reihenfolge in der finalen JSON-Datei.
CANONICAL_BOOK_ORDER = [
    # Altes Testament
    "Gen", "Ex", "Lev", "Num", "Dtn", "Jos", "Ri", "Rut", "1Sam", "2Sam", "1Koen", "2Koen",
    "1Chr", "2Chr", "Esra", "Neh", "Tob", "Jdt", "Est", "1Makk", "2Makk", "Ijob", "Ps",
    "Spr", "Koh", "Hld", "Weish", "Sir", "Jes", "Jer", "Klgl", "Bar", "Ez", "Dan", "Hos",
    "Joel", "Am", "Obd", "Jona", "Mi", "Nah", "Hab", "Zef", "Hag", "Sach", "Mal",
    # Neues Testament
    "Mt", "Mk", "Lk", "Joh", "Apg", "Roem", "1Kor", "2Kor", "Gal", "Eph", "Phil", "Kol",
    "1Thess", "2Thess", "1Tim", "2Tim", "Tit", "Phlm", "Hebr", "Jak", "1Petr", "2Petr",
    "1Joh", "2Joh", "3Joh", "Jud", "Offb"
]

# 2. Mapping der Abkürzungen zu den vollständigen deutschen Buchnamen
BOOK_ABBREVIATION_TO_NAME = {
    # Altes Testament
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Levitikus", "Num": "Numeri", "Dtn": "Deuteronomium",
    "Jos": "Josua", "Ri": "Richter", "Rut": "Rut", "1Sam": "1. Samuel", "2Sam": "2. Samuel",
    "1Koen": "1. Könige", "2Koen": "2. Könige", "1Chr": "1. Chronik", "2Chr": "2. Chronik",
    "Esra": "Esra", "Neh": "Nehemia", "Tob": "Tobit", "Jdt": "Judit", "Est": "Ester",
    "1Makk": "1. Makkabäer", "2Makk": "2. Makkabäer", "Ijob": "Ijob", "Ps": "Psalmen",
    "Spr": "Sprichwörter", "Koh": "Kohelet", "Hld": "Hoheslied", "Weish": "Weisheit",
    "Sir": "Jesus Sirach", "Jes": "Jesaja", "Jer": "Jeremia", "Klgl": "Klagelieder",
    "Bar": "Baruch", "Ez": "Ezechiel", "Dan": "Daniel", "Hos": "Hosea", "Joel": "Joel",
    "Am": "Amos", "Obd": "Obadja", "Jona": "Jona", "Mi": "Micha", "Nah": "Nahum",
    "Hab": "Habakuk", "Zef": "Zefanja", "Hag": "Haggai", "Sach": "Sacharja", "Mal": "Maleachi",
    # Neues Testament
    "Mt": "Matthäus", "Mk": "Markus", "Lk": "Lukas", "Joh": "Johannes", "Apg": "Apostelgeschichte",
    "Roem": "Römer", "1Kor": "1. Korinther", "2Kor": "2. Korinther", "Gal": "Galater",
    "Eph": "Epheser", "Phil": "Philipper", "Kol": "Kolosser", "1Thess": "1. Thessalonicher",
    "2Thess": "2. Thessalonicher", "1Tim": "1. Timotheus", "2Tim": "2. Timotheus",
    "Tit": "Titus", "Phlm": "Philemon", "Hebr": "Hebräer", "Jak": "Jakobus",
    "1Petr": "1. Petrus", "2Petr": "2. Petrus", "1Joh": "1. Johannes", "2Joh": "2. Johannes",
    "3Joh": "3. Johannes", "Jud": "Judas", "Offb": "Offenbarung"
}


def create_bible_json_structure():
    """
    Scannt das 'wav'-Verzeichnis, zählt Audio-Chunks und erstellt eine
    JSON-Datei in kanonischer Reihenfolge.
    """
    wav_dir = 'wav'
    if not os.path.isdir(wav_dir):
        print(f"Fehler: Das Verzeichnis '{wav_dir}' wurde nicht gefunden.")
        print("Bitte führen Sie das Skript im selben Ordner aus, in dem sich der 'wav'-Ordner befindet.")
        return

    # Temporäre Struktur, um alle gefundenen Daten zu sammeln
    # Format: { 'Gen': {1: 15, 2: 10}, 'Ex': {1: 8}, ... }
    processed_data = defaultdict(dict)

    print(f"Scanne Verzeichnisse in '{wav_dir}'...")

    # 3. Verzeichnisse scannen und Daten verarbeiten
    for chapter_dir in os.listdir(wav_dir):
        # Regex, um Buch-Abkürzung und Kapitelnummer zu trennen (z.B. "Gen1", "1Kor13")
        match = re.match(r'^([1-9]?[A-Za-z]+)(\d+)$', chapter_dir)
        if not match:
            print(f"  -> Überspringe '{chapter_dir}' (Format nicht erkannt)")
            continue

        book_abbr, chapter_num_str = match.groups()
        chapter_num = int(chapter_num_str)

        full_path = os.path.join(wav_dir, chapter_dir)

        # Zähle nur .wav Dateien im Verzeichnis
        if os.path.isdir(full_path):
            try:
                wav_files = [f for f in os.listdir(full_path) if f.lower().endswith('.wav')]
                chunk_count = len(wav_files)
                processed_data[book_abbr][chapter_num] = chunk_count
            except OSError as e:
                print(f"  -> Fehler beim Lesen von '{full_path}': {e}")


    # 4. Endgültige JSON-Struktur in kanonischer Reihenfolge erstellen
    final_json_list = []
    print("\nErstelle JSON-Struktur in kanonischer Reihenfolge...")

    for book_abbr in CANONICAL_BOOK_ORDER:
        if book_abbr in processed_data:
            book_name = BOOK_ABBREVIATION_TO_NAME.get(book_abbr, book_abbr) # Fallback auf Abkürzung
            chapters_data = processed_data[book_abbr]

            # Kapitel numerisch sortieren und Schlüssel in Strings umwandeln für JSON
            sorted_chapters = {
                str(chapter): chunks
                for chapter, chunks in sorted(chapters_data.items())
            }

            book_object = {
                "book_name": book_name,
                "directory_name": book_abbr, # <-- HINZUGEFÜGTE ZEILE
                "chapters": sorted_chapters
            }
            final_json_list.append(book_object)
            print(f"  -> Buch '{book_name}' hinzugefügt.")

    # 5. In eine Datei schreiben
    output_filename = 'bibel_struktur.json'
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(final_json_list, f, ensure_ascii=False, indent=2)
        print(f"\nErfolgreich! Die Struktur wurde in '{output_filename}' gespeichert.")
    except IOError as e:
        print(f"\nFehler beim Schreiben der Datei: {e}")

if __name__ == '__main__':
    create_bible_json_structure()