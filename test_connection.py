import os
from dotenv import load_dotenv
# Import the function we defined in data_processor.py
from data_processor import get_data_from_csv, process_cp_points

load_dotenv()

# Get the URL from .env
csv_url = os.getenv("SHEET_CSV_URL")

if not csv_url:
    print("❌ Error: SHEET_CSV_URL not found in .env!")
else:
    print(f"✅ URL found: {csv_url}")
    print("⏳ Attempting to fetch data...")

    df = get_data_from_csv()
    points = process_cp_points(df)

    print("--- СТАДИСТИКА ПО CP ---")
    for cp, pts in points.items():
        print(f"{cp}: {pts} балів")

    if not df.empty:
        print(f"🎉 Success! Data loaded. Rows: {len(df)}")
    else:
        print("❌ Failed to load data.")