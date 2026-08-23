import os
import pandas as pd
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=["Iron Gates Dashboard"])

SHEET_1_TAB1_URL = os.getenv("CP_SHEET_TAB1_URL")
SHEET_1_TAB2_URL = os.getenv("CP_SHEET_TAB2_URL")
TABLE_2_URL = os.getenv("VRYO_TABLE_URL")


def calculate_top_players_last_15(df_tab2, cp_members):
    """
    Рахує кількість відвіданих івентів (чисту кількість '1') за останні 15 завершених івентів.
    Зберігає оригінальний порядок гравців (як у колонках таблиці).
    """
    try:
        if df_tab2.empty or df_tab2.shape[1] < 6:
            return []

        ignored_players = ["winson"]

        history_slice = df_tab2.iloc[4:].copy()
        valid_events = []
        for _, row in history_slice.iterrows():
            date_val = row.iloc[1]
            action_val = row.iloc[0]
            pts_activity_val = row.iloc[3]

            if pd.notna(date_val) and pd.notna(action_val) and pd.notna(pts_activity_val):
                try:
                    pts_num = float(str(pts_activity_val).replace(',', '').strip())
                    if pts_num > 0:
                        valid_events.append(row)
                except ValueError:
                    pass

        last_events = valid_events[-15:] if len(valid_events) >= 15 else valid_events

        header_row = df_tab2.iloc[0]
        player_col_indexes = {}

        for col_idx in range(5, df_tab2.shape[1]):
            col_name = str(header_row.iloc[col_idx]).strip()

            if not col_name or "driver" in col_name.lower():
                break

            if col_name.lower() in ignored_players:
                continue

            player_col_indexes[col_name] = col_idx

        player_attendance = {name: 0 for name in player_col_indexes.keys()}

        for row in last_events:
            for player, col_idx in player_col_indexes.items():
                val = row.iloc[col_idx]
                if pd.notna(val):
                    try:
                        cell_num = float(str(val).replace(',', '').strip())
                        if cell_num > 0:
                            player_attendance[player] += 1
                    except ValueError:
                        pass

        return [
            {"name": name, "score": score}
            for name, score in player_attendance.items()
        ]
    except Exception as e:
        print(f"Error calculating top players: {e}")
        return []

def get_dashboard_data():
    try:
        if not SHEET_1_TAB1_URL:
            raise ValueError("CP_SHEET_TAB1_URL is not set in environment variables.")

        # 1. Table 1 / Tab 1 (B2:B11, D18, C36)
        df_tab1 = pd.read_csv(SHEET_1_TAB1_URL, header=None)

        cp_names_raw = df_tab1.iloc[1:11, 1]
        cp_members = [
            str(val).strip()
            for val in cp_names_raw
            if pd.notna(val) and str(val).strip().lower() != 'nan'
        ]
        members_count = len(cp_members)

        total_cp_ap = 0
        try:
            val_d18 = df_tab1.iloc[17, 3]
            if pd.notna(val_d18):
                total_cp_ap = float(str(val_d18).replace(',', '').strip())
        except Exception:
            pass

        avg_attendance = 0
        try:
            val_c36 = df_tab1.iloc[35, 2]
            if pd.notna(val_c36):
                avg_attendance = float(str(val_c36).replace(',', '').strip())
        except Exception:
            pass

        # 2. Table 1 / Tab 2 (Події, останній івент та топ за 15 івентів)
        total_events_count = 0
        last_played_event = None
        top_players = []
        all_events = []

        if SHEET_1_TAB2_URL:
            df_tab2 = pd.read_csv(SHEET_1_TAB2_URL, header=None)

            if df_tab2.shape[1] > 0:
                events_col = df_tab2.iloc[1:, 0]
                total_events_count = sum(
                    1 for val in events_col
                    if pd.notna(val) and str(val).strip().lower() != 'nan'
                )

            if df_tab2.shape[1] > 5:
                history_slice = df_tab2.iloc[4:].copy()
                for _, row in history_slice.iterrows():
                    date_val = row.iloc[1]
                    action_val = row.iloc[0]
                    pts_val = row.iloc[3]

                    try:
                        p_val = float(str(pts_val).replace(',', '').strip()) if pd.notna(pts_val) else 0
                    except ValueError:
                        p_val = 0

                    if pd.notna(date_val) and pd.notna(action_val) and p_val > 0:
                        event_item = {
                            "name": str(action_val).strip(),
                            "date": str(date_val).strip(),
                            "points": str(p_val).strip()
                        }
                        all_events.append(event_item)

                if all_events:
                    last_played_event = all_events[-1]

            top_players = calculate_top_players_last_15(df_tab2, cp_members)

        # 3. Table 2 (V3:V26 - епіки)
        received_epics_count = 0
        if TABLE_2_URL:
            df_epics = pd.read_csv(TABLE_2_URL, header=None)
            if df_epics.shape[1] > 21:
                epics_cells = df_epics.iloc[2:26, 21]
                for cell_val in epics_cells:
                    if pd.notna(cell_val):
                        words = str(cell_val).split()
                        received_epics_count += len(words)

        return {
            "success": True,
            "data": {
                "members_count": members_count,
                "members_list": cp_members,
                "total_cp_ap": total_cp_ap,
                "avg_attendance": avg_attendance,
                "total_events_count": total_events_count,
                "received_epics_count": received_epics_count,
                "last_played_event": last_played_event,
                "top_players_last_15": top_players,
                "all_events": all_events
            }
        }

    except Exception as e:
        print(f"Error generating Iron Gates dashboard data: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/api/dashboard")
def get_dashboard():
    result = get_dashboard_data()
    if not result.get("success", False):
        return {"status": "error", "data": {}}

    return {"status": "success", "data": result.get("data", {})}