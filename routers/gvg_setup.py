import os
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

load_dotenv()

GVG_SETUP_SHEET_URL = os.getenv("GVG_SETUP_SHEET_URL")

router = APIRouter(prefix="/api/gvg-setup", tags=["GvG Setup"])

def fetch_gvg_csv_data():
    """Fetch CSV data directly from GVG_SETUP_SHEET_URL using pandas."""
    try:
        if not GVG_SETUP_SHEET_URL:
            print("Error: GVG_SETUP_SHEET_URL is not set in environment variables.")
            return pd.DataFrame()

        df = pd.read_csv(GVG_SETUP_SHEET_URL, header=None)
        return df
    except Exception as e:
        print(f"Error fetching GvG Setup CSV data: {e}")
        return pd.DataFrame()

@router.get("/roster")
def get_gvg_setup_roster():
    try:
        df = fetch_gvg_csv_data()
        if df.empty:
            raise HTTPException(status_code=500, detail="Could not load GvG setup spreadsheet data.")

        roster = []
        cardinal_heals = {}  # Словник для групування: хто якого персонажа хіляє

        # Рядки з 3 по 23 (у pandas це індекси від 2 до 22 включно)
        # Переконуємося, що DataFrame має достатньо рядків та колонку R (індекс 17)
        # Рядки з 3 по 23 (у pandas це індекси від 2 до 22 включно)
        start_row = 2
        end_row = min(23, df.shape[0])

        for row_idx in range(start_row, end_row):
            row = df.iloc[row_idx]

            # Col A (index 0) - Перевіряємо, чи значення є числом від 1 до 10
            x_col_val = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else ""

            try:
                # Перетворюємо на число (на випадок, якщо там float типу "1.0")
                num_val = int(float(x_col_val))
                if not (1 <= num_val <= 9):
                    continue
            except (ValueError, TypeError):
                # Якщо це не число (наприклад, порожньо або текст), пропускаємо рядок
                continue

            # Col B (index 1) - Ім'я учасника
            name = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            if not name or name.lower() in ["nan", ""]:
                continue

            # Col O (index 14) - Ігровий клас
            gvg_class = str(row.iloc[14]).strip() if len(row) > 14 and pd.notna(row.iloc[14]) else ""
            if gvg_class.lower() in ["nan", ""]:
                gvg_class = "Unknown"

            # Col Q (index 16) - Додаткова інформація
            info = str(row.iloc[16]).strip() if len(row) > 16 and pd.notna(row.iloc[16]) else ""
            if info.lower() in ["nan", ""]:
                info = ""

            # Col R (index 17) - Біш, який має хіляти
            assigned_bishop = str(row.iloc[17]).strip() if len(row) > 17 and pd.notna(row.iloc[17]) else ""
            if assigned_bishop.lower() in ["nan", ""]:
                assigned_bishop = ""

            member_entry = {
                "name": name,
                "class": gvg_class,
                "info": info,
                "assigned_bishop": assigned_bishop
            }
            roster.append(member_entry)

            # Якщо вказано біша, додаємо цього учасника до загального масиву підзвітних для цього біша
            if assigned_bishop:
                if assigned_bishop not in cardinal_heals:
                    cardinal_heals[assigned_bishop] = []
                cardinal_heals[assigned_bishop].append(name)

        # Додаємо список підопічних (heal_targets) для кожного учасника, особливо для тих, хто Cardinal
        final_roster = []
        for member in roster:
            name = member["name"]
            # Перевіряємо, чи є для цього гравця список кого він хіляє (або якщо це Cardinal)
            targets = cardinal_heals.get(name, [])

            final_roster.append({
                **member,
                "heal_targets": targets
            })

        return {
            "status": "success",
            "total_members": len(final_roster),
            "roster": final_roster
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))