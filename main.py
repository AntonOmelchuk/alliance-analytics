from fastapi import FastAPI
import json
import numpy as np
from data_processor import get_data_from_csv, analyze_clan_data

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all sources only for test
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/api/cp-stats")
def get_cp_stats():
    df = get_data_from_csv()
    stats = analyze_clan_data(df)

    def convert_types(obj):
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_types(i) for i in obj]
        return obj

    clean_stats = convert_types(stats)
    return {"status": "success", "data": clean_stats}