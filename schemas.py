from typing import List, Dict
from pydantic import BaseModel, Field

# ==========================================
# 1. /api/cp-stats
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
# 2. /api/timeline
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
# 3 /api/epics
# ==========================================
class EpicSummary(BaseModel):
    total_farmed: int
    total_shared: int
    unassigned_count: int

class UnassignedLootItem(BaseModel):
    farm_date: str
    epic_name: str

class EpicBreakdownItem(BaseModel):
    total: int
    shared: int
    unassigned: int

class EpicListItem(BaseModel):
    epic_name: str
    farm_date: str
    share_date: str

class CPDistributionItem(BaseModel):
    cp_name: str
    total_epics: int
    last_share_date: str
    epics_count_by_type: Dict[str, int]
    epics_list: List[EpicListItem]

class EpicData(BaseModel):
    summary: EpicSummary
    unassigned_loot: List[UnassignedLootItem]
    epics_breakdown: Dict[str, EpicBreakdownItem]
    cp_distribution: List[CPDistributionItem]

class EpicResponse(BaseModel):
    status: str = "success"
    data: EpicData

# ==========================================
# 1. /api/summary
# ==========================================
class SummaryCardsData(BaseModel):
    total_epics_farmed: int
    unassigned_epics: int
    weekly_mvp_cp: str
    peak_event_players: int
    peak_event_label: str
    weekly_avg_turnout: float

class SummaryCardsResponse(BaseModel):
    status: str = "success"
    data: SummaryCardsData