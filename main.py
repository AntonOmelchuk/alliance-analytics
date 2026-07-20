import pandas as pd
from fastapi import FastAPI

app = FastAPI()

url = "https://docs.google.com/spreadsheets/d/19F-fN-Tz42zVq4KJeAk3kb8uZjk0g9PKHK7xs-4tcJM/edit?gid=1275563143#gid=1275563143"

def load_data():
    df = pd.read_csv(url)

    return df

@app.get("/stats/cp")
def get_cp_stats():
    df = load_data()

    df['Attendance Points'] = pd.to_numeric(df['Attendance Points'], errors='coerce') # Conver errors to NaN
    df = df.dropna(subset=['Attendance Points'])
    return stats