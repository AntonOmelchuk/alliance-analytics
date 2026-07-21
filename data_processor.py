import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# We use the CSV export URL
CSV_URL = os.getenv("SHEET_CSV_URL")

def get_data_from_csv():
    """Fetch CSV data directly using pandas."""
    try:
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def process_cp_points(df):
    """Extract data specifically from column B (CP Name) and C (Attendance Points)."""
    if df.empty:
        return {}

    df_subset = df.iloc[1:, 1:3].copy()
    df_subset.columns = ['CP Name', 'Attendance Points']

    df_subset['Attendance Points'] = pd.to_numeric(df_subset['Attendance Points'], errors='coerce')
    df_subset = df_subset.dropna()

    return df_subset.set_index('CP Name')['Attendance Points'].to_dict()

def analyze_clan_data(df):
    """Final stage: Adding full summary and top performer for frontend dashboard."""
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

    # 1. Витягуємо дані та одразу призначаємо колонки
    df_subset = df.iloc[1:, 1:3].copy()
    df_subset.columns = ['cp_name', 'points']

    # 2. Очищуємо від порожніх значень та рядків "nan"
    df_subset = df_subset.dropna(subset=['cp_name'])
    df_subset = df_subset[df_subset['cp_name'].astype(str).str.lower() != 'nan']

    # 3. Конвертуємо бали в числа
    df_subset['points'] = pd.to_numeric(df_subset['points'], errors='coerce').fillna(0)

    # 4. Рахуємо відсотки внеску та кумулятивну суму для Парето-кривої
    total = df_subset['points'].sum()
    df_subset['contribution_pct'] = (df_subset['points'] / total) * 100 if total > 0 else 0

    df_sorted = df_subset.sort_values(by='points', ascending=False).copy()
    df_sorted['cumulative_pct'] = df_sorted['contribution_pct'].cumsum().round(2)
    df_sorted['contribution_pct'] = df_sorted['contribution_pct'].round(2)

    # Формуємо Pareto list
    pareto_list = [
        {
            "cp_name": str(row['cp_name']),
            "points": int(row['points']),
            "contribution_pct": float(row['contribution_pct']),
            "cumulative_pct": float(row['cumulative_pct'])
        }
        for _, row in df_sorted.iterrows()
    ]

    # Збираємо метрики для Summary карток
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