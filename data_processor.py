import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CSV_URL = os.getenv("SHEET_CSV_URL")

def get_data_from_csv():
    """Fetch CSV data directly using pandas."""
    try:
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

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