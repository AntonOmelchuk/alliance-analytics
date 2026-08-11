# routers/proof.py
import time
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import Optional
from firebase_admin import db

router = APIRouter(prefix="/api/proof", tags=["proof"])


class ProofSubmitPayload(BaseModel):
    cp_name: str = Field(..., description="Selected CP name")
    char_name: str = Field(..., description="Selected or manually entered Character name")
    discord_id: Optional[str] = Field(None, description="Discord ID if logged in")
    secret_code: Optional[str] = Field(None, description="Optional 4-digit verification code")
    device_info: Optional[dict] = Field(default_factory=dict, description="Client device details")


def get_client_ip(request: Request) -> str:
    """Extracts client IP considering reverse proxies (Render, Vercel, Nginx, Cloudflare)"""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/submit")
async def submit_afk_proof(payload: ProofSubmitPayload, request: Request):
    """
    Validates active AFK proof check, captures real client IP on server side,
    and writes confirmed response into proof_history node in Firebase Realtime DB.
    """
    now_ms = int(time.time() * 1000)

    # 1. Fetch current active proof check state
    active_check_ref = db.reference("active_proof_check")
    active_check = active_check_ref.get()

    if not active_check or not active_check.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is no active AFK check at the moment."
        )

    # 2. Check expiration timestamp
    expires_at = active_check.get("expires_at", 0)
    if expires_at and now_ms > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The active AFK check has expired."
        )

    # 3. Validate secret code if required by active check
    required_code = active_check.get("secret_code")
    if required_code:
        provided_code = payload.secret_code.strip() if payload.secret_code else ""
        if provided_code != str(required_code).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid secret code provided."
            )

    # 4. Extract required fields for database key format
    event_date = active_check.get("event_date")
    event_name = active_check.get("event_name")

    if not event_date or not event_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Active proof check lacks event date or event name."
        )

    history_key = f"{event_date}_{event_name}"
    response_key = payload.discord_id if payload.discord_id else f"guest_{now_ms}"
    client_ip = get_client_ip(request)

    # 5. Build response record matching proof_history schema
    response_data = {
        "char_name": payload.char_name.strip(),
        "cp_name": payload.cp_name.strip(),
        "discord_id": payload.discord_id if payload.discord_id else None,
        "ip": client_ip,
        "timestamp": now_ms,
        "is_guest": not bool(payload.discord_id),
        "device_info": payload.device_info or {}
    }

    # 6. Save directly into proof_history/{history_key}/responses/{response_key}
    response_ref = db.reference(f"proof_history/{history_key}/responses/{response_key}")
    response_ref.set(response_data)

    return {
        "status": "success",
        "message": "AFK presence confirmed successfully.",
        "data": response_data
    }