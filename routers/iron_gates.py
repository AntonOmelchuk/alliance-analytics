import os
import pandas as pd
import random
from fastapi import APIRouter
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

load_dotenv()

router = APIRouter(tags=["Iron Gates Dashboard"])

SHEET_1_TAB1_URL = os.getenv("CP_SHEET_TAB1_URL")
SHEET_1_TAB2_URL = os.getenv("CP_SHEET_TAB2_URL")
TABLE_2_URL = os.getenv("VRYO_TABLE_URL")
EPIC_CSV_URL = os.getenv("EPIC_CSV_URL")
CSV_URL = os.getenv("SHEET_CSV_URL")

@router.get("/api/irongates-members")
def get_irongates_members():
    """
    Бере список учасників з Firebase (iron_gates_members),
    зриває дані з VRYO_TABLE_URL (колонки S до X: S - ім'я, T - баланс, W - all_points)
    та збагачує об'єкти учасників.
    """
    try:
        # 1. Отримуємо список учасників з Firebase з гілки iron_gates_members
        ref = db.reference("iron_gates_members")
        firebase_data = ref.get()

        members_list = []
        if firebase_data:
            if isinstance(firebase_data, dict):
                # ВИПРАВЛЕНО: замінено import на in, додано правильний розбір словника
                for key, val in firebase_data.items():
                    if isinstance(val, dict):
                        members_list.append({"id": key, **val})
                    else:
                        members_list.append({"id": key, "name": val})
            elif isinstance(firebase_data, list):
                members_list = [m for m in firebase_data if m is not None]

        # 2. Зчитуємо таблицю VRYO_TABLE_URL
        if not TABLE_2_URL:
            return {"status": "error", "message": "VRYO_TABLE_URL is not configured"}

        df_vryo = pd.read_csv(TABLE_2_URL, header=None)

        extra_data_map = {}

        if df_vryo.shape[1] >= 24:
            for _, row in df_vryo.iterrows():
                name_val = row.iloc[18]       # Колонка S (індекс 18)
                balance_val = row.iloc[19]    # Колонка T (індекс 19)
                all_points_val = row.iloc[22] # Колонка W (індекс 22)

                if pd.notna(name_val):
                    clean_name = str(name_val).strip().lower()

                    try:
                        # Замінюємо кому на крапку для правильного парсингу float
                        balance_str = str(balance_val).replace(',', '.').strip() if pd.notna(balance_val) else "0"
                        balance = float(balance_str)
                        if balance.is_integer():
                            balance = int(balance)
                    except ValueError:
                        balance = 0

                    try:
                        points_str = str(all_points_val).replace(',', '.').strip() if pd.notna(all_points_val) else "0"
                        all_points = float(points_str)
                    except ValueError:
                        all_points = 0.0

                    extra_data_map[clean_name] = {
                        "balance": balance,
                        "all_points": all_points
                    }

        # 3. Зіставляємо дані з Firebase з даними з таблиці за полем 'name'
        enriched_members = []
        for member in members_list:
            if isinstance(member, dict):
                member_name = member.get("name", "")
                if member_name:
                    clean_member_name = str(member_name).strip().lower()

                    if clean_member_name in extra_data_map:
                        member["balance"] = extra_data_map[clean_member_name]["balance"]
                        member["all_points"] = extra_data_map[clean_member_name]["all_points"]
                    else:
                        member["balance"] = 0
                        member["all_points"] = 0

                enriched_members.append(member)

        return {
            "status": "success",
            "data": enriched_members
        }

    except Exception as e:
        print(f"Error fetching iron gates members from Firebase/Table: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": []
        }

def get_iron_gates_points(csv_url):
    """
    Зчитує таблицю total_cp_ap з 3-го рядка (index 2):
    - Колонка B (індекс 1): Назва КП (шукаємо 'IronGates')
    - Колонка C (індекс 2): Поінти (бали) з урахуванням бонусів
    """
    try:
        if not csv_url:
            return 0

        df_points = pd.read_csv(csv_url, header=None)

        total_rows = len(df_points)

        # Перевіряємо, чи в таблиці є хоча б 3 рядки (індекси 0, 1, 2) та мінімум 3 колонки
        if total_rows < 3 or df_points.shape[1] < 3:
            return 0

        # Починаємо з 3-го рядка (індекс 2) до самого кінця таблиці
        for i in range(2, total_rows):
            row = df_points.iloc[i]

            cp_name = row.iloc[1]    # Колонка B (Назва КП)
            points_val = row.iloc[2] # Колонка C (Поінти)

            if pd.notna(cp_name):
                # Очищаємо назву для точного порівняння ('IronGates' / 'Iron Gates')
                clean_cp_name = str(cp_name).replace(" ", "").strip().lower()

                if "irongates" in clean_cp_name:
                    # Безпечно конвертуємо поінти в число (float або int)
                    try:
                        points = float(points_val) if pd.notna(points_val) else 0.0
                        # Якщо це ціле число, можна повернути як int для краси
                        if points.is_integer():
                            points = int(points)

                        return points
                    except ValueError:
                        return 0

        return 0
    except Exception as e:
        print(f"Error fetching Iron Gates points: {e}")
        return 0


def calculate_top_players_last_30(df_tab2, cp_members):
    """
    Рахує кількість відвіданих івентів (чисту кількість '1') за останні 30 завершених івентів.
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

        last_events = valid_events[-30:] if len(valid_events) >= 30 else valid_events

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

        sorted_players = [
              {"name": name, "score": score}
              for name, score in player_attendance.items()
          ]

        sorted_players.sort(key=lambda x: x["score"], reverse=True)

        ranked_players = []
        current_rank = 1
        for i, player in enumerate(sorted_players):
              if i > 0 and player["score"] < sorted_players[i - 1]["score"]:
                  current_rank = i + 1

              ranked_players.append({
                  "name": player["name"],
                  "score": player["score"],
                  "rank": current_rank
              })

        random.shuffle(ranked_players)

        return ranked_players
    except Exception as e:
        print(f"Error calculating top players: {e}")
        return []


def get_last_iron_gates_epic(epic_csv_url):
    """
    Зчитує EPIC_CSV_URL з кінця таблиці.
    Шукає 'irongates' незалежно від пробілів та регістру в колонці D.
    """
    try:
        if not epic_csv_url:
            return None

        df_epics_history = pd.read_csv(epic_csv_url, header=None)

        total_rows = len(df_epics_history)

        if total_rows < 2 or df_epics_history.shape[1] < 5:
            return None

        # Проходимося від останнього рядка до 1 (ігноруючи хедер на 0)
        for i in range(total_rows - 1, 0, -1):
            row = df_epics_history.iloc[i]

            epic_name = row.iloc[1]  # Колонка B
            cp_name = row.iloc[3]    # Колонка D
            date_val = row.iloc[4]   # Колонка E

            if pd.notna(cp_name):
                # Прибираємо пробіли та переводимо в нижній регістр для точного пошуку ('IronGates' або 'Iron Gates')
                clean_cp_name = str(cp_name).replace(" ", "").strip().lower()

                if "irongates" in clean_cp_name:
                    if pd.notna(epic_name):
                        return {
                            "epic_name": str(epic_name).strip(),
                            "date": str(date_val).strip() if pd.notna(date_val) else ""
                        }

        return None
    except Exception as e:
        print(f"Error fetching last Iron Gates epic: {e}")
        return None


def get_dashboard_data():
    try:
        if not SHEET_1_TAB1_URL:
            raise ValueError("CP_SHEET_TAB1_URL is not set in environment variables.")

        # 1. Table 1 / Tab 1 (B2:B11)
        df_tab1 = pd.read_csv(SHEET_1_TAB1_URL, header=None)

        cp_names_raw = df_tab1.iloc[1:11, 1]
        cp_members = [
            str(val).strip()
            for val in cp_names_raw
            if pd.notna(val) and str(val).strip().lower() != 'nan'
        ]
        members_count = len(cp_members)

        # Отримуємо total_cp_ap (з бонусами) через CSV_URL з колонки B та C
        total_cp_ap = get_iron_gates_points(CSV_URL)

        avg_attendance = 0
        try:
            val_c36 = df_tab1.iloc[45, 2]
            if pd.notna(val_c36):
                avg_attendance = float(str(val_c36).replace(',', '').strip())
        except Exception:
            pass

        # 2. Table 1 / Tab 2 (Події, останній івент та топ за 30 івентів)
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

            top_players = calculate_top_players_last_30(df_tab2, cp_members)

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

        # 4. Отримання останнього епіку Iron Gates з EPIC_CSV_URL
        last_epic_data = get_last_iron_gates_epic(EPIC_CSV_URL)

        return {
            "success": True,
            "data": {
                "members_count": members_count,
                "members_list": cp_members,
                "total_cp_ap": total_cp_ap,
                "avg_attendance": avg_attendance,
                "total_events_count": total_events_count,
                "received_epics_count": received_epics_count,
                "last_epic": last_epic_data,
                "last_played_event": last_played_event,
                "top_players_last_30": top_players,
                "all_events": all_events,
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