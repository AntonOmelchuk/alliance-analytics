import re
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from firebase_admin import db

router = APIRouter(prefix="/api", tags=["cp"])


def extract_spreadsheet_id(url: str) -> str:
    """
    Extracts the Google Spreadsheet ID from any standard Google Sheets URL format.
    """
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Google Spreadsheet URL format.")


@router.get("/cp-players")
async def get_cp_players(cp: str):
    """
    Fetches the roster of players for a selected CP by reading its Google Sheet.
    The spreadsheet URL is retrieved from Firebase Realtime Database.
    Players are extracted from Row 3 (Excel index 3 = Pandas index 2) starting from Column F (index 5) onwards.
    """
    print(f"\n🔍 [DEBUG] Searching players for CP: '{cp}'")

    if not cp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CP name parameter is required."
        )

    # 1. Fetch spreadsheet URL from Firebase by CP key
    cp_ref = db.reference(f"cp_list/{cp}")
    sheet_url = cp_ref.get()

    if not sheet_url:
        # Fallback check if cp_list is stored as a dictionary of objects { "IronGates": { "url": "..." } }
        cp_ref_alt = db.reference("cp_list")
        all_cps = cp_ref_alt.get() or {}

        if isinstance(all_cps, dict) and cp in all_cps:
            sheet_data = all_cps[cp]
            sheet_url = sheet_data.get("url") if isinstance(sheet_data, dict) else sheet_data

    print(f"🔗 [DEBUG] Retrieved URL from Firebase for '{cp}': {sheet_url}")

    if not sheet_url or not isinstance(sheet_url, str):
        print(f"❌ [DEBUG] Spreadsheet URL not found or invalid for CP '{cp}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spreadsheet URL for CP '{cp}' not found in Firebase database."
        )

    try:
        # 2. Extract Spreadsheet ID and construct Direct CSV Export URL
        spreadsheet_id = extract_spreadsheet_id(sheet_url)
        # Using /export?format=csv guarantees formula evaluation and exact cell values
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        print(f"🌐 [DEBUG] Direct CSV Export URL: {csv_url}")

        # 3. Read CSV stream without headers
        df = pd.read_csv(csv_url, header=None)
        print(f"📊 [DEBUG] DataFrame shape (rows, cols): {df.shape}")

        if len(df) < 3 or df.shape[1] < 6:
            print(f"⚠️ [DEBUG] Table too small: {len(df)} rows, {df.shape[1]} cols")
            return []

        # 4. Target Row 3 (Pandas index 2) and Column F onwards (Pandas index 5+)
        # We clean string values directly
        row_3_from_f = df.iloc[2, 5:].dropna().tolist()
        print(f"🎯 [DEBUG] Raw extracted Row 3 (Col F+): {row_3_from_f}")

        # 5. Filter out empty spaces, 'nan', and non-player labels
        players = []
        for val in row_3_from_f:
            cleaned_val = str(val).strip()
            if cleaned_val and cleaned_val.lower() not in ["nan", "none", "null", ""]:
                players.append(cleaned_val)

        print(f"✅ [DEBUG] FinalParsed Players ({len(players)} found): {players}\n")
        return players

    except Exception as e:
        print(f"❌ Error parsing Google Sheet for CP '{cp}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse players from Google Sheet: {str(e)}"
        )