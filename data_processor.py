import os
import re
import uuid
import pandas as pd
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DEFAULT_EPIC_PRICES = {
    "Core": 7,
    "Orfen": 15,
    "QA": 45,
    "Queen Ant": 45,
    "Zaken": 50,
    "Tezza": 72,
    "Frintezza": 72,
    "Baium": 100,
    "Antharas": 110,
    "Valakas": 200,
}

CSV_URL = os.getenv("SHEET_CSV_URL")
TIME_SERIES_CSV_URL = os.getenv("TIME_SERIES_CSV_URL")
EPIC_CSV_URL = os.getenv("EPIC_CSV_URL")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL")

# ===========================
# Helper: Fetch Firebase Lists
# ===========================
def _fetch_firebase_name_set(endpoint_path: str) -> set:
    """Helper to fetch and normalize list of CP names from Firebase endpoint."""
    try:
        if not FIREBASE_DATABASE_URL:
            return set()

        firebase_url = f"{FIREBASE_DATABASE_URL.rstrip('/')}/{endpoint_path.lstrip('/')}"
        response = requests.get(firebase_url, timeout=5)

        if response.status_code == 200 and response.json():
            data = response.json()
            names = set()

            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, dict) and "name" in val:
                        names.add(str(val["name"]).strip().lower())
                    elif isinstance(val, str):
                        names.add(val.strip().lower())
            elif isinstance(data, list):
                for val in data:
                    if isinstance(val, dict) and "name" in val:
                        names.add(str(val["name"]).strip().lower())
                    elif isinstance(val, str):
                        names.add(val.strip().lower())

            return names
    except Exception as e:
        print(f"Warning: Failed to fetch {endpoint_path} from Firebase. Error: {e}")

    return set()


def get_cp_ignore_list() -> set:
    """Fetch CP ignore list from Firebase (/cp_ignore_list.json)."""
    return _fetch_firebase_name_set("cp_ignore_list.json")


def get_inactive_cp_list() -> set:
    """Fetch Inactive CP list from Firebase (/inactive_cp.json)."""
    return _fetch_firebase_name_set("inactive_cp.json")


def get_data_from_csv():
    """Fetch CSV data directly using pandas."""
    try:
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

# ===========================
# Get CP List
# ===========================
def get_cp_list():
    """
    Fetch CP list from Google Sheets CSV starting from Column B (index 1), Row 3 (index 2).
    Returns a list of unique, cleaned CP records excluding ignored and inactive CPs.
    """
    try:
        if not CSV_URL:
            print("Error: SHEET_CSV_URL is not set in environment variables.")
            return []

        ignore_list = get_cp_ignore_list()
        inactive_list = get_inactive_cp_list()
        # Full exclusion list for active CP options
        excluded_cps = ignore_list.union(inactive_list)

        df = pd.read_csv(CSV_URL, header=None)

        if df.empty or df.shape[1] < 2:
            return []

        cp_column = df.iloc[2:, 1]

        cp_list = []
        seen_names = set()

        for idx, val in enumerate(cp_column):
            if pd.notna(val):
                name_str = str(val).strip()
                if (
                    name_str
                    and name_str.lower() != "nan"
                    and name_str not in seen_names
                    and name_str.lower() not in excluded_cps
                ):
                    seen_names.add(name_str)
                    cp_list.append({
                        "id": f"cp_{idx + 1}_{uuid.uuid4().hex[:6]}",
                        "name": name_str,
                        "active": True
                    })

        return cp_list

    except Exception as e:
        print(f"Error fetching CP list: {e}")
        return []

# ===========================
# Get Alliance Point Data
# ===========================
def analyze_clan_data(df):
    """Analyze CP Alliance points with ignore_list and inactive_cp filtering applied to CP metrics."""
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

    ignore_list = get_cp_ignore_list()
    inactive_list = get_inactive_cp_list()
    excluded_cps = ignore_list.union(inactive_list)

    max_col_index = max(2, 11)
    if df.shape[1] <= max_col_index:
        df_subset = df.iloc[1:, 1:3].copy()
        df_subset.columns = ['cp_name', 'points']
        df_subset['gb_pts_ratio'] = 0.0
    else:
        df_subset = df.iloc[:, [1, 2, 11]].copy()
        df_subset = df_subset.iloc[1:].copy()
        df_subset.columns = ['cp_name', 'points', 'gb_pts_ratio']

    df_subset = df_subset.dropna(subset=['cp_name'])
    df_subset = df_subset[df_subset['cp_name'].astype(str).str.lower() != 'nan']

    # 🛑 Filter out ignored & inactive CPs from active CP analytics
    df_subset['cp_name_clean'] = df_subset['cp_name'].astype(str).str.strip()
    df_subset = df_subset[~df_subset['cp_name_clean'].str.lower().isin(excluded_cps)].copy()

    df_subset['points'] = pd.to_numeric(df_subset['points'], errors='coerce').fillna(0)
    df_subset['gb_pts_ratio'] = pd.to_numeric(df_subset['gb_pts_ratio'], errors='coerce').fillna(0.0)

    total = df_subset['points'].sum()
    df_subset['contribution_pct'] = (df_subset['points'] / total) * 100 if total > 0 else 0

    df_sorted = df_subset.sort_values(by='points', ascending=False).copy()
    df_sorted['cumulative_pct'] = df_sorted['contribution_pct'].cumsum().round(2)
    df_sorted['contribution_pct'] = df_sorted['contribution_pct'].round(2)

    pareto_list = [
        {
            "cp_name": str(row['cp_name_clean']),
            "points": int(row['points']),
            "contribution_pct": float(row['contribution_pct']),
            "cumulative_pct": float(row['cumulative_pct']),
            "gb_pts_ratio": float(row['gb_pts_ratio'])
        }
        for _, row in df_sorted.iterrows()
    ]

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
    Fetch and process time-series data for CP activity.
    Inactive CPs are removed from current_snapshot and historical CP columns, but preserved in total_players.
    """
    try:
        df = pd.read_csv(TIME_SERIES_CSV_URL, header=None)
        if df.empty:
            return {"current_snapshot": [], "timeline": []}

        ignore_list = get_cp_ignore_list()
        inactive_list = get_inactive_cp_list()
        cp_exclusions = ignore_list.union(inactive_list)

        # 1. CP Names
        cp_names = df.iloc[3, 5:33].tolist()

        # 2. Current CP Points
        cp_points_raw = df.iloc[2, 5:33].tolist()

        current_cp_snapshot = []
        for name, pts in zip(cp_names, cp_points_raw):
            if pd.notna(name) and str(name).strip() != "" and str(name).lower() != "nan":
                clean_name = str(name).strip()
                # Exclude ignored and inactive CPs from current snapshot
                if clean_name.lower() in cp_exclusions:
                    continue
                try:
                    clean_pts = int(float(str(pts).replace(",", "")))
                except (ValueError, TypeError):
                    clean_pts = 0
                current_cp_snapshot.append({
                    "cp_name": clean_name,
                    "points": clean_pts
                })

        # 3. History by events
        history_slice = df.iloc[4:].copy()

        timeline_records = []
        for _, row in history_slice.iterrows():
            date_val = row.iloc[2]
            action_val = row.iloc[1]
            players_val = row.iloc[0]

            if pd.isna(date_val) or str(date_val).strip() == "" or str(date_val).lower() == "nan":
                continue

            date_str = str(date_val).strip()
            action_str = str(action_val).strip() if pd.notna(action_val) else "Event"
            event_label = f"{date_str} - {action_str}"

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
                    clean_cp = str(cp_name).strip()

                    # 🛑 Filter out both ignored and inactive CPs from timeline details
                    if clean_cp.lower() in cp_exclusions:
                        continue

                    col_index = 5 + idx
                    raw_val = row.iloc[col_index] if col_index < len(row) else 0
                    try:
                        val = int(float(str(raw_val).replace(",", "")))
                    except (ValueError, TypeError):
                        val = 0
                    record[clean_cp] = val
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

# ======================================
# Get Epic Prices & Historical Epic Data
# ======================================
def fetch_epic_prices():
    """Get Epic Price from Firebase Database."""
    try:
        firebase_url = f"{FIREBASE_DATABASE_URL.rstrip('/')}/epicPrices.json"
        response = requests.get(firebase_url, timeout=5)

        if response.status_code == 200 and response.json():
            return response.json()
    except Exception as e:
        print(f"Warning: Failed to fetch prices from Firebase, using defaults. Error: {e}")

    return DEFAULT_EPIC_PRICES


def get_epic_data():
    """
    Fetch and process Epic Boss drops and distribution data.
    Inactive CPs are excluded from active CP distribution list (cp_distribution),
    but historical drops and total farmed metrics are kept accurate.
    """
    try:
        if not EPIC_CSV_URL:
            return {
                "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0},
                "unassigned_loot": [],
                "epics_breakdown": {},
                "cp_distribution": []
            }

        ignore_list = get_cp_ignore_list()
        inactive_list = get_inactive_cp_list()
        cp_exclusions = ignore_list.union(inactive_list)

        df = pd.read_csv(EPIC_CSV_URL)

        if df.empty or df.shape[1] < 3:
            return {
                "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0},
                "unassigned_loot": [],
                "epics_breakdown": {},
                "cp_distribution": []
            }

        epic_prices = fetch_epic_prices()

        df_slice = df.iloc[:, :5].copy()
        df_slice.columns = ['farm_date', 'epic_name', 'is_shared', 'cp_name', 'share_date']

        df_slice = df_slice.dropna(subset=['epic_name'])
        df_slice = df_slice[df_slice['epic_name'].astype(str).str.strip() != ""]

        date_pattern = re.compile(r'^\d{1,2}-[A-Za-z]{3}$', re.IGNORECASE)

        unassigned_loot = []
        epics_breakdown = {}
        cp_dict = {}

        total_farmed = 0
        total_shared = 0
        total_value_gb = 0

        all_farmed_epics = []

        for idx, row in df_slice.iterrows():
            farm_date = str(row['farm_date']).strip() if pd.notna(row['farm_date']) else ""

            if not farm_date or not date_pattern.match(farm_date):
                continue

            epic_name = str(row['epic_name']).strip()
            raw_shared = str(row['is_shared']).strip().upper() if pd.notna(row['is_shared']) else "FALSE"
            is_shared = raw_shared in ["TRUE", "1", "YES"]

            cp_name = str(row['cp_name']).strip() if pd.notna(row['cp_name']) else ""
            share_date = str(row['share_date']).strip() if pd.notna(row['share_date']) else ""

            # Check ignore & inactive status
            is_cp_ignored = cp_name.lower() in ignore_list
            is_cp_inactive = cp_name.lower() in inactive_list

            total_farmed += 1
            epic_price = epic_prices.get(epic_name, 0)

            all_farmed_epics.append({
                "id": f"epic_{idx}_{uuid.uuid4().hex[:8]}",
                "farm_date": farm_date,
                "epic_name": epic_name,
                "is_shared": is_shared and not is_cp_ignored,
                "assigned_cp": cp_name if (is_shared and cp_name and cp_name.lower() != "nan" and not is_cp_ignored) else None,
                "share_date": share_date if (is_shared and not is_cp_ignored) else None,
                "price_gb": epic_price
            })

            if epic_name not in epics_breakdown:
                epics_breakdown[epic_name] = {"total": 0, "shared": 0, "unassigned": 0}

            epics_breakdown[epic_name]["total"] += 1

            if is_shared and not is_cp_ignored:
                total_shared += 1
                total_value_gb += epic_price
                epics_breakdown[epic_name]["shared"] += 1

                # 🛑 Include in CP distribution stats ONLY if CP is not in inactive_list
                if cp_name and cp_name.lower() != "nan" and not is_cp_inactive:
                    if cp_name not in cp_dict:
                        cp_dict[cp_name] = {
                            "cp_name": cp_name,
                            "total_epics": 0,
                            "total_gb": 0,
                            "last_share_date": share_date,
                            "epics_list": [],
                            "epics_count_by_type": {}
                        }

                    cp_dict[cp_name]["total_epics"] += 1
                    cp_dict[cp_name]["total_gb"] += epic_price
                    cp_dict[cp_name]["last_share_date"] = share_date

                    cp_dict[cp_name]["epics_list"].append({
                        "epic_name": epic_name,
                        "farm_date": farm_date,
                        "share_date": share_date,
                        "price_gb": epic_price
                    })

                    current_count = cp_dict[cp_name]["epics_count_by_type"].get(epic_name, 0)
                    cp_dict[cp_name]["epics_count_by_type"][epic_name] = current_count + 1

            else:
                epics_breakdown[epic_name]["unassigned"] += 1
                unassigned_loot.append({
                    "farm_date": farm_date,
                    "epic_name": epic_name,
                    "price_gb": epic_price
                })

        cp_distribution = list(cp_dict.values())
        cp_distribution.sort(key=lambda x: x["total_epics"], reverse=True)

        return {
            "summary": {
                "total_farmed": total_farmed,
                "total_shared": total_shared,
                "unassigned_count": len(unassigned_loot),
                "total_value_gb": total_value_gb
            },
            "unassigned_loot": unassigned_loot,
            "epics_breakdown": epics_breakdown,
            "cp_distribution": cp_distribution, # Contains active CPs distribution
            "all_farmed_epics": all_farmed_epics,
            "prices": epic_prices
        }

    except Exception as e:
        print(f"Error fetching epic data: {e}")
        return {
            "summary": {"total_farmed": 0, "total_shared": 0, "unassigned_count": 0, "total_value_gb": 0},
            "unassigned_loot": [],
            "epics_breakdown": {},
            "cp_distribution": []
        }

# =================================
# Calculate Data for Summary Cards
# =================================
def get_summary_cards_data(timeline_records):
    """
    Calculate metrics for Summary Cards excluding ignored and inactive CPs from Weekly MVP calculation.
    """
    if not timeline_records:
        return {
            "weekly_mvp_cp": "N/A",
            "peak_event_players": 0,
            "peak_event_label": "N/A",
            "weekly_avg_turnout": 0,
            "total_events": 0
        }

    ignore_list = get_cp_ignore_list()
    inactive_list = get_inactive_cp_list()
    cp_exclusions = ignore_list.union(inactive_list)

    total_events = len(timeline_records)

    peak_record = max(timeline_records, key=lambda x: x.get("total_players", 0))
    peak_players = peak_record.get("total_players", 0)
    peak_label = peak_record.get("event_label", "N/A")

    RECENT_EVENTS_COUNT = 10
    recent_events = (
        timeline_records[-RECENT_EVENTS_COUNT:]
        if len(timeline_records) >= RECENT_EVENTS_COUNT
        else timeline_records
    )

    total_recent_players = sum(e.get("total_players", 0) for e in recent_events)
    weekly_avg_turnout = round(total_recent_players / len(recent_events), 1) if recent_events else 0

    cp_recent_attendance = {}
    system_keys = ["date", "action", "event_label", "total_players"]

    for event in recent_events:
        for key, val in event.items():
            # 🛑 Filter out ignored & inactive CPs from Weekly MVP
            if key not in system_keys and key.lower() not in cp_exclusions:
                try:
                    num_val = int(val)
                except (ValueError, TypeError):
                    num_val = 0
                cp_recent_attendance[key] = cp_recent_attendance.get(key, 0) + num_val

    weekly_mvp = "N/A"
    if cp_recent_attendance:
        weekly_mvp = max(cp_recent_attendance, key=cp_recent_attendance.get)

    return {
        "weekly_mvp_cp": weekly_mvp,
        "peak_event_players": peak_players,
        "peak_event_label": peak_label,
        "weekly_avg_turnout": weekly_avg_turnout,
        "total_events": total_events
    }