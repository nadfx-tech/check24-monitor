"""
Check24 Hotel-Monitor — Verwaltungstool
Verwendung:
  python manage.py list                  — Alle Hotels anzeigen
  python manage.py add <URL>             — Hotel hinzufügen (Check24-URL)
  python manage.py remove <Hotel-ID>     — Hotel entfernen
  python manage.py summary <H1,H2,...>   — Zusammenfassungs-Uhrzeiten ändern
  python manage.py push                  — Änderungen in die Cloud pushen
"""

import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
REMOVE_PARAMS = {"hotelListId", "budgetMax", "bestSeller"}


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Konfiguration gespeichert.")


def clean_url(url):
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v[0] for k, v in params.items() if k not in REMOVE_PARAMS}
    new_query = urllib.parse.urlencode(cleaned)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def extract_hotel_id(url):
    match = re.search(r'hotelId=(\d+)', url)
    return match.group(1) if match else None


def cmd_list():
    config = load_config()
    print(f"\n{'='*60}")
    print(f"  Check24 Monitor — {len(config['hotels'])} Hotels")
    print(f"  Intervall: alle {config['check_interval_min']} Min.")
    print(f"  Zusammenfassungen: {', '.join(f'{h}:00' for h in config['summary_hours'])}")
    print(f"{'='*60}\n")
    for i, h in enumerate(config["hotels"], 1):
        name = h.get("name", "Unbekannt")
        print(f"  {i}. [{h['id']}] {name}")
    print()


def cmd_add(url):
    if "check24.de" not in url:
        print("Fehler: Das ist keine Check24-URL.")
        return

    hotel_id = extract_hotel_id(url)
    if not hotel_id:
        print("Fehler: Keine Hotel-ID in der URL gefunden.")
        return

    config = load_config()

    # Prüfen ob Hotel schon existiert
    existing_ids = [h["id"] for h in config["hotels"]]
    if hotel_id in existing_ids:
        print(f"Hotel {hotel_id} wird bereits überwacht.")
        return

    clean = clean_url(url)
    hotel = {
        "id": hotel_id,
        "name": f"Hotel {hotel_id}",
        "url": clean,
    }
    config["hotels"].append(hotel)
    save_config(config)
    print(f"\nHotel {hotel_id} hinzugefügt!")
    print(f"(Der Name wird beim nächsten Check automatisch erkannt.)")
    print(f"\nVergiss nicht: python manage.py push")


def cmd_remove(hotel_id):
    config = load_config()
    before = len(config["hotels"])
    config["hotels"] = [h for h in config["hotels"] if h["id"] != hotel_id]

    if len(config["hotels"]) == before:
        print(f"Hotel {hotel_id} nicht gefunden.")
        return

    save_config(config)
    print(f"Hotel {hotel_id} entfernt.")
    print(f"\nVergiss nicht: python manage.py push")


def cmd_summary(hours_str):
    try:
        hours = sorted([int(h.strip()) for h in hours_str.split(",")])
        if not all(0 <= h <= 23 for h in hours):
            raise ValueError
    except ValueError:
        print("Fehler: Uhrzeiten als kommagetrennte Zahlen (0-23), z.B.: 8,12,20")
        return

    config = load_config()
    config["summary_hours"] = hours
    save_config(config)
    print(f"Zusammenfassungen um: {', '.join(f'{h}:00' for h in hours)}")
    print(f"\nVergiss nicht: python manage.py push")


def cmd_push():
    print("Pushe Änderungen in die Cloud...")
    try:
        subprocess.run(["git", "add", "config.json"], cwd=CONFIG_PATH.parent, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Config aktualisiert"],
            cwd=CONFIG_PATH.parent,
            check=True,
        )
        subprocess.run(["git", "push"], cwd=CONFIG_PATH.parent, check=True)
        print("Erfolgreich in die Cloud gepusht!")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in str(e):
            print("Keine Änderungen zum Pushen.")
        else:
            print(f"Fehler beim Push: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "list":
        cmd_list()
    elif cmd == "add" and len(sys.argv) >= 3:
        cmd_add(sys.argv[2])
    elif cmd == "remove" and len(sys.argv) >= 3:
        cmd_remove(sys.argv[2])
    elif cmd == "summary" and len(sys.argv) >= 3:
        cmd_summary(sys.argv[2])
    elif cmd == "push":
        cmd_push()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
