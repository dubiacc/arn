# arn-audio

ARN Bibelübersetzung 

## Installation

- Benötigt Python 3.9.x (https://python.org) oder `brew install python3` (MacOS)
- Dann `pip` Paketmanager installieren: `python3 -m ensurepip --upgrade`
- Dann `google.genai` installieren `pip install google-genai`

## Anleitung

Die Rohtexte liegen im Format "ein Vers pro Zeile" in `/txt`, also "Gen1" -> "Genesis 1".

Da lange Kapitel Probleme hatten mit der KI-Audiogenerierung, habe ich die
Kapitel in "Stücke" geteilt, jedes Stück ca. 50 - 100 Zeichen lang (ca. 10 - 30 Sekunden Audio).
Das kann man wiederholen mit `python3 split-chapters.py`

Das Skript funktioniert über die "Gemini Live Stream API", da diese billiger
ist als die reguläre TTS API und zudem auch kein Limit hat, wie viele Audiodateien
man pro Tag erstellt.

D.h. das Skript `chapters-to-audio.py` startet 40 Live-Streams gleichzeitig und nimmt
die "Blöcke" mit dem davor gestellten Prompt `"Lies laut vor: "` - darüber kann man den
Tonfall, Intention, etc. anpassen. Manuell geht das über <https://aistudio.google.com/live>.

Um die Kosten der Konvertierung zu schätzen kann man `python3 cost-calculator.py` laufen
lassen, vorrausgesetzt dass `ffprobe` (von FFmpeg) installiert ist. Das berechnet aufgrund
der Textdateien + Länge der Audiodateien 

## Nachbearbeitung

Leider betont die KI manchmal Wörter, speziell Namen auf einmal mit englischem Akzent,
daher braucht man noch ein wenig Qualitätskontrolle. Die Tabelle für die Qualitätskontrolle
ist hier: 

## Hochladen

Der Videoinhalt lässt sich aus den `.txt`-Blöcken erstellen. Hierbei erstellt man aus 
den 50-Zeichen Blöcken einfach `.html` Dateien und rendert diese mit Google Chrome in `.png`
Dateien.

Um am Ende die Audios zu Videos zu machen, benötigt man noch andere Dinge:

- Automatische Thumbnails für jedes Kapitel
- Liste der Bibelkapitel in Reihenfolge
- Zusammenfassung des Kapitels
- Videoeschreibung, Titel, Tags, SEO 
- Skript zum automatischen Hochladen auf YouTube

Diese Skripte kommen noch.
