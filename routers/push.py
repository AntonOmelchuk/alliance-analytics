import os
import base64
from fastapi import APIRouter, HTTPException, status
from firebase_admin import db
from schemas import PushSubscriptionSchema
from pydantic import BaseModel
from pywebpush import WebPushException
from services.push_worker import send_notification

router = APIRouter(prefix="/api/push", tags=["Push Notifications"])

def get_subscription_key(endpoint: str) -> str:
    """Generates a safe Firebase RTDB key from the endpoint URL"""
    return base64.urlsafe_b64encode(endpoint.encode()).decode().replace("=", "")

@router.post("/subscribe")
async def subscribe_to_push(data: PushSubscriptionSchema):
    if len(data.alerts) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 5 active alerts reached."
        )

    sub_key = get_subscription_key(data.endpoint)
    ref = db.reference(f"push_subscriptions/{sub_key}")

    payload = {
        "endpoint": data.endpoint,
        "keys": data.keys.model_dump(),
        "alerts": {k: v.model_dump() for k, v in data.alerts.items()},
        "lang": data.lang
    }
    print("payload lang:", payload["lang"])
    ref.set(payload)
    return {"status": "ok", "message": "Subscription saved successfully"}

@router.delete("/unsubscribe")
async def unsubscribe_push(endpoint: str):
    sub_key = get_subscription_key(endpoint)
    ref = db.reference(f"push_subscriptions/{sub_key}")
    ref.delete()
    return {"status": "ok", "message": "Subscription removed"}

class BroadcastSchema(BaseModel):
    title: str
    body: str
    admin_secret: str

@router.post("/broadcast")
async def send_broadcast_push(data: BroadcastSchema):
    if data.admin_secret != os.getenv("ADMIN_SECRET_KEY", "my_super_secret_clan_pass_2026"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        subs_ref = db.reference("push_subscriptions").get() or {}
    except Exception as e:
        print(f"Firebase DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase error: {str(e)}")

    if not subs_ref:
        return {"status": "ok", "sent_count": 0, "message": "No active subscriptions found"}

    sent_count = 0
    failed_count = 0

    if isinstance(subs_ref, dict):
        items = subs_ref.items()
    elif isinstance(subs_ref, list):
        items = [(str(idx), val) for idx, val in enumerate(subs_ref) if val]
    else:
        items = []

    for sub_key, sub_data in items:
        try:
            if not isinstance(sub_data, dict):
                failed_count += 1
                continue

            subscription_info = sub_data.get("subscription") or sub_data

            send_notification(
                sub_key=str(sub_key),
                sub_data=subscription_info,
                title=data.title,
                body=data.body,
                event_id="admin_broadcast"
            )
            sent_count += 1
        except Exception as err:
            print(f"Unexpected error for {sub_key}: {err}")
            failed_count += 1

    return {
        "status": "ok",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "message": f"Sent: {sent_count}, Failed: {failed_count}"
    }