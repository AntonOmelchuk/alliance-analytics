from fastapi import FastAPI
import numpy as np
from data_processor import get_data_from_csv, analyze_clan_data, get_clan_timeline_data, get_epic_data, get_summary_cards_data
from schemas import ParetoResponse, TimelineResponse, EpicResponse, SummaryCardsResponse

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://eternal-respawn.netlify.app", "https://dev--eternal-respawn.netlify.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

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

@app.get("/api/cp-stats", response_model=ParetoResponse)
def get_cp_stats():
    df = get_data_from_csv()
    stats = analyze_clan_data(df)
    clean_stats = convert_types(stats)
    return {"status": "success", "data": clean_stats}

@app.get("/api/timeline", response_model=TimelineResponse)
def get_timeline():
    timeline_data = get_clan_timeline_data()
    clean_timeline = convert_types(timeline_data)
    return {"status": "success", "data": clean_timeline}

@app.get("/api/epics", response_model=EpicResponse)
def get_epics():
    epic_data = get_epic_data()
    clean_epic_data = convert_types(epic_data)
    return {"status": "success", "data": clean_epic_data}

@app.get("/api/summary", response_model=SummaryCardsResponse)
def get_summary():
    timeline_res = get_clan_timeline_data()
    epic_res = get_epic_data()
    pareto_res = analyze_clan_data(get_data_from_csv())

    summary_data = get_summary_cards_data(
        timeline_res.get("timeline", []),
        epic_res,
        pareto_res.get("pareto", [])
    )
    return {"status": "success", "data": summary_data}