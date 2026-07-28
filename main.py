import os
import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from data_processor import get_data_from_csv, analyze_clan_data, get_clan_timeline_data, get_epic_data, get_summary_cards_data
from schemas import ParetoResponse, TimelineResponse, EpicResponse, SummaryCardsResponse
from routers import push
from services.push_worker import check_and_send_push_notifications

# ====================
#  FIREBASE & SCHEDULER
# ====================
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred, {
        "databaseURL": FIREBASE_DATABASE_URL
    })

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs the push worker every 1 minute
    scheduler.add_job(check_and_send_push_notifications, 'interval', minutes=1)
    scheduler.start()
    print("🚀 Push Notification Worker started successfully!")
    yield
    scheduler.shutdown()

# ====================
#   APP INITIALIZATION (ЕДИНИЙ ЕКЗЕМПЛЯР)
# ====================
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://eternal-respawn.netlify.app", "https://iron-gates.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(push.router)

# ====================
#      ROUTES
# ====================
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
    summary_data = get_summary_cards_data(
        timeline_res.get("timeline", []),
    )
    return {"status": "success", "data": summary_data}



@app.api_route("/api/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok", "message": "Backend is awake!"}