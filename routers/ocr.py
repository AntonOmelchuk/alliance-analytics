import os
import re
from datetime import datetime, timezone
import requests
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/api/ocr", tags=["OCR"])

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld") # "helloworld" is default demo key

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

        # Send image file directly to OCR.space API
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": (file.filename, contents, file.content_type)},
            data={
                "apikey": OCR_SPACE_API_KEY,
                "language": "eng",
                "isTable": True,
                "scale": True,
                "OCREngine": "2"  # Engine 2 is optimized for tables and numbers
            },
            timeout=15
        )

        result_json = response.json()

        if result_json.get("IsErroredOnProcessing"):
            error_msg = result_json.get("ErrorMessage", ["OCR Processing error"])[0]
            return {"status": "error", "message": error_msg}

        parsed_results_data = result_json.get("ParsedResults", [])
        if not parsed_results_data:
            return {"status": "success", "data": []}

        ocr_text = parsed_results_data[0].get("ParsedText", "")
        lines = [line.strip() for line in ocr_text.split("\r\n") if line.strip()]

        parsed_results = []

        # Regex for dates and time formats
        epic_regex = re.compile(
            r"(\d{1,2})[.s/-](\d{1,2})[.s/-](\d{2,4})\s+(\d{1,2})[:;.s](\d{2})"
        )
        siege_ch_regex = re.compile(
            r"(\d{1,2})[:;.s](\d{2})\s+(\d{1,2})[.s/-](\d{1,2})[.s/-](\d{2,4})"
        )

        for i, line in enumerate(lines):
            clean_line = line.lower()

            matched_db_key = None
            for keyword, db_key in EVENT_MAPPING.items():
                if keyword in clean_line:
                    matched_db_key = db_key
                    break

            if not matched_db_key:
                continue

            # Look at current line and next 2 lines for date context
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

        return {"status": "success", "data": parsed_results}

    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"OCR API request failed: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}