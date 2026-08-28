import os
import re
import pandas as pd
import requests
from datetime import timedelta
from dotenv import load_dotenv
from fastapi import APIRouter, Query, HTTPException

load_dotenv()

CP_SHEET_TAB2_URL = os.getenv("CP_SHEET_TAB2_URL")

router = APIRouter(prefix="/api/ig-analytics", tags=["Iron Gates CP Analytics"])

def fetch_tab2_csv_data():
    """Fetch CSV data directly from CP_SHEET_TAB2_URL using pandas."""
    try:
        if not CP_SHEET_TAB2_URL:
            print("Error: CP_SHEET_TAB2_URL is not set in environment variables.")
            return pd.DataFrame()

        df = pd.read_csv(CP_SHEET_TAB2_URL, header=None)
        return df
    except Exception as e:
        print(f"Error fetching Tab 2 CSV data: {e}")
        return pd.DataFrame()

def process_cp_analytics(days_filter=None):
    """
    Process CP analytics based on Tab 2 spreadsheet structure:
    - Row 0 (index 0): Headers (Col A: Ally Action, Col B: Date, Col C: Window, Col D: Points, Col E: Dominator, Col F-P: Member names)
    - Strictly restricts members to columns F through P (indices 5 to 15 max), ignoring anything beyond like 'Driver'.
    - Calculates Dominator events percentage.
    """
    df = fetch_tab2_csv_data()
    if df.empty or df.shape[0] < 2:
        return {
            "members": [],
            "timeline": [],
            "points_history": [],
            "event_performance": [],
            "summary": {}
        }

    # 1. Extract member names from row index 0, strictly from columns F to P (indices 5 to 15)
    header_row = df.iloc[0]
    member_cols = []
    member_names = []

    max_member_col = min(16, df.shape[1])

    ignored_members = {"winson"}

    for col_idx in range(5, max_member_col):
        name = header_row.iloc[col_idx]
        if pd.notna(name) and str(name).strip() != "" and str(name).lower() != "nan":
            clean_name = str(name).strip()

            if clean_name.lower() in ignored_members:
                continue

            member_names.append(clean_name)
            member_cols.append(col_idx)

    # 2. Process event rows (starting from index 1)
    raw_events = []
    date_pattern = re.compile(r'^\d{1,2}/\d{2}/\d{2}$', re.IGNORECASE)

    for row_idx in range(1, df.shape[0]):
        row = df.iloc[row_idx]

        action = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        date_str = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        window = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""

        # Skip summary or empty rows where date or action is missing
        if not action or action.lower() == "nan" or not date_str or date_str.lower() == "nan":
            continue

        # Basic date validation check
        if not date_pattern.match(date_str):
            continue

        try:
            points = int(float(str(row.iloc[3]).replace(",", ""))) if pd.notna(row.iloc[3]) else 0
        except (ValueError, TypeError):
            points = 0

        # Dominator column (Col E, index 4) check (True if contains checkmark or non-empty string like True/x/✔️)
        dominator_val = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        is_dominator = False
        if dominator_val and dominator_val.lower() not in ["nan", "false", "", "0", "none"]:
            is_dominator = True

        # Parse member attendance (1 = attended, empty/0 = missed) - strictly for columns F to P
        attendance = {}
        attended_count = 0
        for name, col_idx in zip(member_names, member_cols):
            val = row.iloc[col_idx] if col_idx < len(row) else ""
            is_present = 0
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str == "1" or val_str.lower() == "true":
                    is_present = 1

            attendance[name] = is_present
            attended_count += is_present

        raw_events.append({
            "row_index": row_idx,
            "date": date_str,
            "parsed_date": pd.to_datetime(date_str, format="%d/%m/%y", errors="coerce"),
            "action": action,
            "window": window,
            "points": points,
            "is_dominator": is_dominator,
            "attended_count": attended_count,
            "attendance": attendance
        })

    # Filter out rows with invalid parsed dates
    valid_events = [e for e in raw_events if pd.notna(e["parsed_date"])]

    # Sort chronologically just to be safe
    valid_events.sort(key=lambda x: x["parsed_date"])

    # Apply time window filter if specified (e.g., 7 or 30 days from the latest event)
    if days_filter and valid_events:
        latest_date = valid_events[-1]["parsed_date"]
        cutoff_date = latest_date - timedelta(days=int(days_filter))
        valid_events = [e for e in valid_events if e["parsed_date"] >= cutoff_date]

    total_events = len(valid_events)
    if total_events == 0:
        return {
            "members": member_names,
            "total_events": 0,
            "dominator_events_count": 0,
            "dominator_pct": 0,
            "timeline": [],
            "event_performance": [],
            "points_history": [],
            "members_analytics": []
        }

    # Calculate Dominator stats
    dominator_events_count = sum(1 for e in valid_events if e["is_dominator"])
    dominator_pct = round((dominator_events_count / total_events) * 100, 1)

    # 3. Calculate metrics per member
    member_stats = {name: {"attended": 0, "points": 0, "current_streak": 0, "max_streak": 0} for name in member_names}

    timeline = []
    points_history_map = {name: [] for name in member_names}
    event_performance = []

    total_points_sum = sum(e["points"] for e in valid_events)
    avg_event_points = total_points_sum / total_events if total_events > 0 else 0

    for idx, event in enumerate(valid_events):
        event_label = f"{event['action']} ({event['date']})"

        # Timeline item
        timeline_item = {
            "id": f"event_{idx}",
            "date": event["date"],
            "action": event["action"],
            "window": event["window"],
            "points": event["points"],
            "is_dominator": event["is_dominator"],
            "total_participants": event["attended_count"],
            "event_label": event_label,
            "present_members": [name for name, present in event["attendance"].items() if present == 1]
        }
        timeline.append(timeline_item)

        # Event performance item for bar chart
        event_performance.append({
            "event_label": event_label,
            "date": event["date"],
            "action": event["action"],
            "points": event["points"],
            "is_dominator": event["is_dominator"],
            "is_above_average": event["points"] >= avg_event_points
        })

        # Process member specific achievements per event
        for name in member_names:
            is_present = event["attendance"].get(name, 0)
            if is_present == 1:
                member_stats[name]["attended"] += 1
                member_stats[name]["points"] += event["points"]
                member_stats[name]["current_streak"] += 1
                if member_stats[name]["current_streak"] > member_stats[name]["max_streak"]:
                    member_stats[name]["max_streak"] = member_stats[name]["current_streak"]
            else:
                member_stats[name]["current_streak"] = 0

            # Points history mapping for line chart
            points_history_map[name].append({
                "event_label": event_label,
                "date": event["date"],
                "action": event["action"],
                "accumulated_points": member_stats[name]["points"],
                "event_points": event["points"] if is_present == 1 else 0
            })

    # Finalize members summary array
    members_analytics = []
    for name in member_names:
        stats = member_stats[name]
        attendance_pct = round((stats["attended"] / total_events) * 100, 1) if total_events > 0 else 0
        members_analytics.append({
            "name": name,
            "attended_events": stats["attended"],
            "total_events": total_events,
            "attendance_pct": attendance_pct,
            "max_streak": stats["max_streak"],
            "total_points": stats["points"]
        })

    members_analytics.sort(key=lambda x: (x["attended_events"], x["total_points"]), reverse=True)

    for index, member in enumerate(members_analytics):
        member["rank"] = index + 1

    return {
        "members": member_names,
        "total_events": total_events,
        "dominator_events_count": dominator_events_count,
        "dominator_pct": dominator_pct,
        "average_event_points": round(avg_event_points, 1),
        "members_analytics": members_analytics,
        "timeline": timeline,
        "event_performance": event_performance,
        "points_history": points_history_map
    }

@router.get("/cp-stats")
def get_ig_cp_analytics(days: int = Query(None, description="Filter by number of days: 7, 30, etc.")):
    try:
        data = process_cp_analytics(days_filter=days)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))