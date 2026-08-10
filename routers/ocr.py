import re
from datetime import datetime, timezone
import cv2
import numpy as np
import easyocr
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/api/ocr", tags=["OCR"])

# Ініціалізуємо ридер один раз при старті сервера
reader = easyocr.Reader(['en'], gpu=False)

EVENT_MAPPING = {
    # Epic Bosses
    "queen ant": "Queen Ant",
    "core": "Core",
    "orfen": "Orfen",
    "zaken": "Zaken",
    "frintezza": "Frintezza",
    "antharas": "Antharas",
    "valakas": "Valakas",
    "baium": "Baium",
    
    # Clan Halls (CH)
    "devastated castle": "CH Devastated Castle",
    "rainbow spring": "CH Rainbow Spring Chateau",
    "fortress of the dead": "CH Fortress of the Dead",
    "bandit stronghold": "CH Bandit Stronghold",
    "wild beast": "CH Wild Beast Reserve",
    "fortress of resistance": "CH Fortress of Resistance",
    
    # Castles (Siege)
    "gludio": "Siege Gludio",
    "dion": "Siege Dion",
    "giran": "Siege Giran",
    "oren": "Siege Oren",
    "aden": "Siege Aden",
    "innadril": "Siege Innadril",
    "goddard": "Siege Goddard",
    "rune": "Siege Rune",
    "schuttgart": "Siege Schuttgart",
}

@router.post("/parse-respawn")
async def parse_respawn(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # EasyOCR зчитує текст прямо з масиву зображення
        lines = reader.readtext(img, detail=0)

        parsed_results = []

        epic_regex = re.compile(
            r"(\d{1,2})[\.\/-](\d{1,2})[\.\/-](\d{4})\s+(\d{1,2})[\.:](\d{2})"
        )
        siege_ch_regex = re.compile(
            r"(\d{1,2})[\.:](\d{2})\s+(\d{1,2})[\.\/-](\d{1,2})[\.\/-](\d{4})"
        )

        for line in lines:
            clean_line = line.strip().lower()
            if not clean_line:
                continue

            matched_db_key = None
            for keyword, db_key in EVENT_MAPPING.items():
                if keyword in clean_line:
                    matched_db_key = db_key
                    break

            if not matched_db_key:
                continue

            dt = None

            # Спроба 1: Парсинг як Епік (dd.mm.yyyy hh.mm)
            epic_match = epic_regex.search(clean_line)
            if epic_match:
                day, month, year, hours, minutes = map(int, epic_match.groups())
                dt = datetime(year, month, day, hours, minutes, tzinfo=timezone.utc)

            # Спроба 2: Парсинг як CH / Замок (hh.mm dd.mm.yyyy)
            if not dt:
                siege_match = siege_ch_regex.search(clean_line)
                if siege_match:
                    hours, minutes, day, month, year = map(int, siege_match.groups())
                    dt = datetime(year, month, day, hours, minutes, tzinfo=timezone.utc)

            if dt:
                timestamp_sec = int(dt.timestamp())
                parsed_results.append({
                    "dbKey": matched_db_key,
                    "eventName": matched_db_key,
                    "timestampSeconds": timestamp_sec,
                    "formattedUtc": dt.strftime("%Y-%m-%d %H:%M UTC"),
                    "utcInputString": dt.strftime("%Y-%m-%dT%H:%M")
                })

        return {"status": "success", "data": parsed_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}