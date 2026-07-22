import os
import uuid
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CSV_URL = os.getenv("SHEET_CSV_URL")
TIME_SERIES_CSV_URL = os.getenv("TIME_SERIES_CSV_URL")
EPIC_CSV_URL = os.getenv("EPIC_CSV_URL")

def get_data_from_csv():
    """Fetch CSV data directly using pandas."""
    try:
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

# ===========================
# Get Alliance Point Data
# ===========================
def analyze_clan_data(df):
    """Final stage: Adding full summary, top performer, and GB/PTs Ratio from column L."""
    if df.empty:
        return {
            "pareto": [],
            "summary": {
                "total_points": 0,
                "average_points": 0,
                "top_cp": "N/A",
                "total_cps": 0
            }
        }

    # 1. Get main data: B (index 1) — cp_name, C (index 2) — points
    # Take L (index 11) — GB/PTs Ratio
    # Check if dataset contains enough cell (to avoid IndexError)
    max_col_index = max(2, 11)
    if df.shape[1] <= max_col_index:
        # if there is no L cell in table
        df_subset = df.iloc[1:, 1:3].copy()
        df_subset.columns = ['cp_name', 'points']
        df_subset['gb_pts_ratio'] = 0.0
    else:
        df_subset = df.iloc[:, [1, 2, 11]].copy()
        df_subset = df_subset.iloc[1:].copy() # Remove header (1st data cell)
        df_subset.columns = ['cp_name', 'points', 'gb_pts_ratio']

    # 2. Clean from empty values and NaN rows
    df_subset = df_subset.dropna(subset=['cp_name'])
    df_subset = df_subset[df_subset['cp_name'].astype(str).str.lower() != 'nan']

    # 3. Convert values to numbers
    df_subset['points'] = pd.to_numeric(df_subset['points'], errors='coerce').fillna(0)
    df_subset['gb_pts_ratio'] = pd.to_numeric(df_subset['gb_pts_ratio'], errors='coerce').fillna(0.0)

    # 4. Calculate percents for each CP and data for Pareto
    total = df_subset['points'].sum()
    df_subset['contribution_pct'] = (df_subset['points'] / total) * 100 if total > 0 else 0

    df_sorted = df_subset.sort_values(by='points', ascending=False).copy()
    df_sorted['cumulative_pct'] = df_sorted['contribution_pct'].cumsum().round(2)
    df_sorted['contribution_pct'] = df_sorted['contribution_pct'].round(2)

    # Prepare Pareto list (with gb_pts_ratio)
    pareto_list = [
        {
            "cp_name": str(row['cp_name']),
            "points": int(row['points']),
            "contribution_pct": float(row['contribution_pct']),
            "cumulative_pct": float(row['cumulative_pct']),
            "gb_pts_ratio": float(row['gb_pts_ratio'])
        }
        for _, row in df_sorted.iterrows()
    ]

    # Take metrics for Summary cards
    avg_points = float(df_subset['points'].mean()) if not df_subset.empty else 0
    top_cp_name = pareto_list[0]["cp_name"] if pareto_list else "N/A"

    return {
        "pareto": pareto_list,
        "summary": {
            "total_points": int(total),
            "average_points": round(avg_points, 2),
            "top_cp": top_cp_name,
            "total_cps": len(pareto_list)
        }
    }

# ===========================
# Get Historical Events Data
# ===========================
def get_clan_timeline_data():
    """
    Fetch and process time-series data for CP activity and total players from column A.
    """
    try:
        df = pd.read_csv(TIME_SERIES_CSV_URL, header=None)
        if df.empty:
            return {"current_snapshot": [], "timeline": []}

        # 1. CP Name — 4th row (index 3), cells from F (index 5) to AE (index 32)
        cp_names = df.iloc[3, 5:33].tolist()

        # 2. Current CP Points — 3rd row (index 2)
        cp_points_raw = df.iloc[2, 5:33].tolist()

        current_cp_snapshot = []
        for name, pts in zip(cp_names, cp_points_raw):
            if pd.notna(name) and str(name).strip() != "" and str(name).lower() != "nan":
                try:
                    clean_pts = int(float(str(pts).replace(",", "")))
                except (ValueError, TypeError):
                    clean_pts = 0
                current_cp_snapshot.append({
                    "cp_name": str(name).strip(),
                    "points": clean_pts
                })

        # 3. History by events (from 5th row, index 4)
        history_slice = df.iloc[4:].copy()

        timeline_records = []
        for _, row in history_slice.iterrows():
            date_val = row.iloc[2] # Cell C (Date)
            action_val = row.iloc[1] # Cell B (Ally Action)
            players_val = row.iloc[0] # Cell A (Total Players)

            if pd.isna(date_val) or str(date_val).strip() == "" or str(date_val).lower() == "nan":
                continue

            date_str = str(date_val).strip()
            action_str = str(action_val).strip() if pd.notna(action_val) else "Event"
            event_label = f"{date_str} - {action_str}"

            # Convert Total Players to Number
            try:
                total_players = int(float(str(players_val).replace(",", "")))
            except (ValueError, TypeError):
                total_players = 0

            record = {
                "date": date_str,
                "action": action_str,
                "event_label": event_label,
                "total_players": total_players
            }

            has_data = False
            for idx, cp_name in enumerate(cp_names):
                if pd.notna(cp_name) and str(cp_name).strip() != "":
                    col_index = 5 + idx
                    raw_val = row.iloc[col_index] if col_index < len(row) else 0
                    try:
                        val = int(float(str(raw_val).replace(",", "")))
                    except (ValueError, TypeError):
                        val = 0
                    record[str(cp_name).strip()] = val
                    if val > 0:
                        has_data = True

            if has_data:
                timeline_records.append(record)

        return {
            "current_snapshot": current_cp_snapshot,
            "timeline": timeline_records
        }

    except Exception as e:
        print(f"Error fetching timeline data: {e}")
        return {"current_snapshot": [], "timeline": []}

# ===========================
# Get Historical Epic Data
# ===========================
def get_epic_data():
    """
    Fetch and process Epic Boss drops and distribution data.
    """
    try:
        if not EPIC_CSV_URL:
            return {
                "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0},
                "unassigned_loot": [],
                "epics_breakdown": {},
                "cp_distribution": []
            }

        # Read CSV
        df = pd.read_csv(EPIC_CSV_URL)

        if df.empty or df.shape[1] < 3:
            return {
                "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0},
                "unassigned_loot": [],
                "epics_breakdown": {},
                "cp_distribution": []
            }

        # Take first 5 cells (A, B, C, D, E)
        df_slice = df.iloc[:, :5].copy()
        df_slice.columns = ['farm_date', 'epic_name', 'is_shared', 'cp_name', 'share_date']

        # Remove spaces in epic name
        df_slice = df_slice.dropna(subset=['epic_name'])
        df_slice = df_slice[df_slice['epic_name'].astype(str).str.strip() != ""]

        unassigned_loot = []
        epics_breakdown = {}
        cp_dict = {}

        total_farmed = 0
        total_shared = 0

        all_farmed_epics = []

        for idx, row in df_slice.iterrows():
            farm_date = str(row['farm_date']).strip() if pd.notna(row['farm_date']) else ""
            epic_name = str(row['epic_name']).strip()

            # Handle Shared checkbox (can be TRUE/False, "TRUE", "True", True, or 1)
            raw_shared = str(row['is_shared']).strip().upper() if pd.notna(row['is_shared']) else "FALSE"
            is_shared = raw_shared in ["TRUE", "1", "YES", "TRUE"]

            cp_name = str(row['cp_name']).strip() if pd.notna(row['cp_name']) else ""
            share_date = str(row['share_date']).strip() if pd.notna(row['share_date']) else ""

            total_farmed += 1

            # Store all epic data
            all_farmed_epics.append({
                "id": f"epic_{idx}_{uuid.uuid4().hex[:8]}",
                "farm_date": farm_date,
                "epic_name": epic_name,
                "is_shared": is_shared,
                "assigned_cp": cp_name if (is_shared and cp_name and cp_name.lower() != "nan") else None,
                "share_date": share_date if is_shared else None
            })

            # 1. Main statistics for each boss (breakdown)
            if epic_name not in epics_breakdown:
                epics_breakdown[epic_name] = {"total": 0, "shared": 0, "unassigned": 0}

            epics_breakdown[epic_name]["total"] += 1

            if is_shared:
                total_shared += 1
                epics_breakdown[epic_name]["shared"] += 1

                # 2. Group by CP
                if cp_name and cp_name.lower() != "nan":
                    if cp_name not in cp_dict:
                        cp_dict[cp_name] = {
                            "cp_name": cp_name,
                            "total_epics": 0,
                            "last_share_date": share_date,
                            "epics_list": [],
                            "epics_count_by_type": {}
                        }

                    cp_dict[cp_name]["total_epics"] += 1
                    cp_dict[cp_name]["last_share_date"] = share_date # Last date update

                    # Detailed list of shared epics
                    cp_dict[cp_name]["epics_list"].append({
                        "epic_name": epic_name,
                        "farm_date": farm_date,
                        "share_date": share_date
                    })

                    # Count epics for this CP (e.x. {"QueenAnt": 3, "Valakas": 1})
                    current_count = cp_dict[cp_name]["epics_count_by_type"].get(epic_name, 0)
                    cp_dict[cp_name]["epics_count_by_type"][epic_name] = current_count + 1

            else:
                # 3. Non shared epic in warehouse
                epics_breakdown[epic_name]["unassigned"] += 1
                unassigned_loot.append({
                    "farm_date": farm_date,
                    "epic_name": epic_name
                })

        # Convert cp_dict to serted array (from CP with more epics to CP with less epics)
        cp_distribution = list(cp_dict.values())
        cp_distribution.sort(key=lambda x: x["total_epics"], reverse=True)

        return {
            "summary": {
                "total_farmed": total_farmed,
                "total_shared": total_shared,
                "unassigned_count": len(unassigned_loot)
            },
            "unassigned_loot": unassigned_loot,  # Epics in warehouse
            "epics_breakdown": epics_breakdown,  # Epics statistics
            "cp_distribution": cp_distribution,  # CP statistics
            "all_farmed_epics": all_farmed_epics # Array with all epic & date
        }

    except Exception as e:
        print(f"Error fetching epic data: {e}")
        return {
            "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0},
            "unassigned_loot": [],
            "epics_breakdown": {},
            "cp_distribution": []
        }

# =================================
# Callculate Data for Summary Cards
# =================================
def get_summary_cards_data(timeline_records, epic_data, pareto_list):
    """
    Calculate metrics for Summary Cards:
    1. Total Epics Farmed & Treasury
    2. Weekly MVP CP
    3. Peak Event Record (max players/points)
    4. Weekly Avg Turnout (середній онлайн за останні 7 днів)
    """
    if not timeline_records:
        return {
            "total_epics_farmed": 0,
            "unassigned_epics": 0,
            "weekly_mvp_cp": "N/A",
            "peak_event_players": 0,
            "peak_event_label": "N/A",
            "weekly_avg_turnout": 0
        }

    # 1. Epics
    epic_summary = epic_data.get("summary", {})
    total_epics = epic_summary.get("total_farmed", 0)
    unassigned_epics = epic_summary.get("unassigned_count", 0)

    # 2. Peak Event Record
    peak_record = max(timeline_records, key=lambda x: x.get("total_players", 0))
    peak_players = peak_record.get("total_players", 0)
    peak_label = peak_record.get("event_label", "N/A")

    # 3. Find the most active CP during last 10 events
    RECENT_EVENTS_COUNT = 10
    recent_events = (
        timeline_records[-RECENT_EVENTS_COUNT:]
        if len(timeline_records) >= RECENT_EVENTS_COUNT
        else timeline_records
    )

    # Weekly Avg Turnout
    total_recent_players = sum(e.get("total_players", 0) for e in recent_events)
    weekly_avg_turnout = round(total_recent_players / len(recent_events), 1) if recent_events else 0

    # Weekly MVP CP
    cp_recent_attendance = {}
    system_keys = ["date", "action", "event_label", "total_players"]

    for event in recent_events:
        for key, val in event.items():
            if key not in system_keys:
                try:
                    num_val = int(val)
                except (ValueError, TypeError):
                    num_val = 0
                cp_recent_attendance[key] = cp_recent_attendance.get(key, 0) + num_val

    weekly_mvp = "N/A"
    if cp_recent_attendance:
        weekly_mvp = max(cp_recent_attendance, key=cp_recent_attendance.get)

    return {
        "total_epics_farmed": total_epics,
        "unassigned_epics": unassigned_epics,
        "weekly_mvp_cp": weekly_mvp,
        "peak_event_players": peak_players,
        "peak_event_label": peak_label,
        "weekly_avg_turnout": weekly_avg_turnout
    }