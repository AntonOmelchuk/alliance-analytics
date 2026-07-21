import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# We use the CSV export URL
CSV_URL = os.getenv("SHEET_CSV_URL")

def get_data_from_csv():
    """Fetch CSV data directly using pandas."""
    try:
        # Read the CSV directly from the Google export URL
        # We assume the header is in the first row (index 0)
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

import pandas as pd

def process_cp_points(df):
    """Extract data specifically from column B (CP Name) and C (Attendance Points)."""
    if df.empty:
        return {}

    # 1. Беремо тільки колонки з індексами 1 (B) та 2 (C)
    # iloc[:, 1:3] означає "всі рядки, колонки від 1 до 2 включно"
    df_subset = df.iloc[1:, 1:3].copy()

    # 2. Присвоюємо їм зрозумілі назви, щоб ми могли з ними працювати
    df_subset.columns = ['CP Name', 'Attendance Points']

    # 3. Чистимо дані
    df_subset['Attendance Points'] = pd.to_numeric(df_subset['Attendance Points'], errors='coerce')
    df_subset = df_subset.dropna()

    # 4. Повертаємо результат
    return df_subset.set_index('CP Name')['Attendance Points'].to_dict()

# analytic enhancement
def get_analytics_for_frontend(df):
    """
    Prepare structured JSON for frontend charts.
    Returns data split into categories for different types of diagrams.
    """
    if df.empty:
        return {}

    # Slice and clean as we established
    df_subset = df.iloc[1:, 1:3].copy()
    df_subset.columns = ['cp_name', 'points']
    df_subset['points'] = pd.to_numeric(df_subset['points'], errors='coerce').fillna(0)

    # Sort for better chart presentation (descending)
    df_sorted = df_subset.sort_values(by='points', ascending=False)

    # 1. Prepare data for Bar/Pie charts
    chart_data = df_sorted.to_dict(orient='records')

    # 2. Add extra metrics for "Clan Overview" widget
    total_points = df_sorted['points'].sum()
    top_cp = df_sorted.iloc[0].to_dict() if not df_sorted.empty else {}

    return {
        "summary": {
            "total_clan_points": int(total_points),
            "top_performer": top_cp,
            "total_cp_count": len(df_sorted)
        },
        "chart_data": chart_data
    }

def analyze_clan_data(df):
    """Final stage: Adding full summary and top performer."""
    df_subset = df.iloc[1:, 1:3].copy()
    df_subset.columns = ['cp_name', 'points']
    df_subset = df_subset.dropna(subset=['cp_name']) # Remove rows without CP Name
    df_subset = df_subset[df_subset['cp_name'] != 'nan']
    df_subset['points'] = pd.to_numeric(df_subset['points'], errors='coerce').fillna(0)

    total = df_subset['points'].sum()
    df_subset['contribution_pct'] = (df_subset['points'] / total) * 100 if total > 0 else 0
    df_sorted = df_subset.sort_values(by='points', ascending=False).copy()
    df_sorted['cumulative_pct'] = df_sorted['contribution_pct'].cumsum()

    # Pareto list (cleaned)
    pareto_list = [
        {
            "cp_name": str(row['cp_name']),
            "points": int(row['points']),
            "contribution_pct": float(row['contribution_pct']),
            "cumulative_pct": float(row['cumulative_pct'])
        }
        for _, row in df_sorted.iterrows()
    ]

    # Summary (cleaned)
    avg_points = float(df_subset['points'].mean())
    top_cp = pareto_list[0] if pareto_list else {}

    return {
        "pareto": pareto_list,
        "summary": {
            "total_points": int(total),
            "average_points": round(avg_points, 2),
            "top_cp": top_cp
        }
    }
