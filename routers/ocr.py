import re
from datetime import datetime, timezone
import cv2
import numpy as np
import easyocr
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/api/ocr", tags=["OCR"])

reader = easyocr.Reader(['en'], gpu=False)

EVENT_MAPPING = {
    # Epic Bosses
    "queen ant": "Queen Ant",
    "queenant": "Queen Ant",
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

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        ocr_results = reader.readtext(gray, detail=0)

        full_text = "\n".join(ocr_results)
        lines = full_text.split("\n")

        parsed_results = []

        epic_regex = re.compile(
            r"(\d{1,2})[\.\/,\-s](\d{1,2})[\.\/,\-s](\d{2,4})\s+(\d{1,2})[\.:;,s](\d{2})"
        )
        siege_ch_regex = re.compile(
            r"(\d{1,2})[\.:;,s](\d{2})\s+(\d{1,2})[\.\/,\-s](\d{1,2})[\.\/,\-s](\d{2,4})"
        )

        for i, line in enumerate(lines):
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

            context_window = " ".join(lines[i:min(i + 3, len(lines))]).lower()

            dt = None

            epic_match = epic_regex.search(context_window)
            if epic_match:
                day, month, year, hours, minutes = map(int, epic_match.groups())
                if year < 100:
                    year += 2000
                dt = datetime(year, month, day, hours, minutes, tzinfo=timezone.utc)

            if not dt:
                siege_match = siege_ch_regex.search(context_window)
                if siege_match:
                    hours, minutes, day, month, year = map(int, siege_match.groups())
                    if year < 100:
                        year += 2000
                    dt = datetime(year, month, day, hours, minutes, tzinfo=timezone.utc)

            if dt:
                timestamp_sec = int(dt.timestamp())

                if not any(r["dbKey"] == matched_db_key for r in parsed_results):
                    parsed_results.append({
                        "dbKey": matched_db_key,
                        "eventName": matched_db_key,
                        "timestampSeconds": timestamp_sec,
                        "formattedUtc": dt.strftime("%Y-%m-%d %H:%M UTC"),
                        "utcInputString": dt.strftime("%Y-%m-%dT%H:%M")
                    })

        return {"status": "success", "data": parsed_results, "raw_text_debug": ocr_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}