from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# ==========================================
# /api/cp-stats
# ==========================================
class ParetoItem(BaseModel):
    cp_name: str
    points: int
    contribution_pct: float
    cumulative_pct: float
    gb_pts_ratio: float

class ParetoSummary(BaseModel):
    total_points: int
    average_points: float
    top_cp: str
    total_cps: int

class ParetoData(BaseModel):
    pareto: List[ParetoItem]
    summary: ParetoSummary

class ParetoResponse(BaseModel):
    status: str = "success"
    data: ParetoData


# ==========================================
# /api/timeline
# ==========================================
class CPSnapshotItem(BaseModel):
    cp_name: str
    points: int

class TimelineData(BaseModel):
    current_snapshot: List[CPSnapshotItem]
    timeline: List[Dict[str, str | int]]

class TimelineResponse(BaseModel):
    status: str = "success"
    data: TimelineData


# ==========================================
# /api/epics
# ==========================================
class EpicSummary(BaseModel):
    total_farmed: int
    total_shared: int
    unassigned_count: int
    total_value_gb: int

class UnassignedLootItem(BaseModel):
    farm_date: str
    epic_name: str
    price_gb: Optional[int] = 0

class EpicBreakdownItem(BaseModel):
    total: int
    shared: int
    unassigned: int
    unit_price_gb: Optional[int] = 0

class EpicListItem(BaseModel):
    epic_name: str
    farm_date: str
    share_date: str
    price_gb: Optional[int] = 0

class CPDistributionItem(BaseModel):
    cp_name: str
    total_epics: int
    total_gb: int
    last_share_date: str
    epics_count_by_type: Dict[str, int]
    epics_list: List[EpicListItem]

class AllFarmedEpicItem(BaseModel):
    id: str
    farm_date: str
    epic_name: str
    is_shared: bool
    assigned_cp: Optional[str] = None
    share_date: Optional[str] = None
    price_gb: Optional[int] = 0

class EpicData(BaseModel):
    summary: EpicSummary
    unassigned_loot: List[UnassignedLootItem]
    epics_breakdown: Dict[str, EpicBreakdownItem]
    cp_distribution: List[CPDistributionItem]
    all_farmed_epics: List[AllFarmedEpicItem]
    prices: Optional[Dict[str, int]] = {}

class EpicResponse(BaseModel):
    status: str = "success"
    data: EpicData

# ==========================================
# /api/summary
# ==========================================
class SummaryCardsData(BaseModel):
    weekly_mvp_cp: str
    peak_event_players: int
    peak_event_label: str
    weekly_avg_turnout: float
    total_events: int

class SummaryCardsResponse(BaseModel):
    status: str = "success"
    data: SummaryCardsData

# ==========================================
# /api/push
# ==========================================
class PushKeys(BaseModel):
    p256dh: str
    auth: str

class AlertSettings(BaseModel):
    leadTimeMinutes: int = Field(default=30, ge=5, le=60) # 10, 30, 60 хв

class PushSubscriptionSchema(BaseModel):
    endpoint: str
    keys: PushKeys
    alerts: Dict[str, AlertSettings] = Field(default_factory=dict) # {"zaken": {"leadTimeMinutes": 30}}
    lang: Optional[str] = "en"
    discord_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/...",
                "keys": {
                    "p256dh": "BIP...",
                    "auth": "17X..."
                },
                "alerts": {
                    "zaken": {"leadTimeMinutes": 30},
                    "Capture The Base": {"leadTimeMinutes": 10}
                }
            }
        }