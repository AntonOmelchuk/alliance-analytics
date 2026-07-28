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
    encoded_key = base64.urlsafe_b64encode(endpoint.encode()).decode().replace("=", "")
    print(f"[DEBUG] Generated sub_key: {encoded_key} for endpoint: {endpoint[:40]}...")
    return encoded_key

@router.post("/subscribe")
async def subscribe_to_push(data: PushSubscriptionSchema):
    print("\n--- [DEBUG] POST /api/push/subscribe ---")
    print(f"[DEBUG] Incoming data: endpoint={data.endpoint[:40]}..., lang={data.lang}, alerts_count={len(data.alerts)}")
    print(f"[DEBUG] Alerts payload: {data.alerts}")

    if len(data.alerts) > 5:
        print("[DEBUG ERROR] Validation failed: Limit of 5 active alerts exceeded")
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
    
    print(f"[DEBUG] Writing payload to Firebase path 'push_subscriptions/{sub_key}'...")
    try:
        ref.set(payload)
        print("[DEBUG SUCCESS] Subscription saved successfully to Firebase!")
    except Exception as e:
        print(f"[DEBUG ERROR] Failed to write to Firebase: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase write error: {str(e)}")

    return {"status": "ok", "message": "Subscription saved successfully"}

@router.delete("/unsubscribe")
async def unsubscribe_push(endpoint: str):
    print("\n--- [DEBUG] DELETE /api/push/unsubscribe ---")
    print(f"[DEBUG] Unsubscribing endpoint: {endpoint[:40]}...")
    
    sub_key = get_subscription_key(endpoint)
    ref = db.reference(f"push_subscriptions/{sub_key}")
    
    try:
        ref.delete()
        print(f"[DEBUG SUCCESS] Deleted sub_key '{sub_key}' from Firebase.")
    except Exception as e:
        print(f"[DEBUG ERROR] Failed to delete from Firebase: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase delete error: {str(e)}")

    return {"status": "ok", "message": "Subscription removed"}

class BroadcastSchema(BaseModel):
    title: str
    body: str
    admin_secret: str

@router.post("/broadcast")
async def send_broadcast_push(data: BroadcastSchema):
    print("\n--- [DEBUG] POST /api/push/broadcast ---")
    print(f"[DEBUG] Broadcast request: title='{data.title}', body='{data.body}'")

    expected_secret = os.getenv("ADMIN_SECRET_KEY", "my_super_secret_clan_pass_2026")
    if data.admin_secret != expected_secret:
        print("[DEBUG ERROR] Broadcast authentication failed: Invalid admin_secret")
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        print("[DEBUG] Fetching subscriptions from Firebase ('push_subscriptions')...")
        subs_ref = db.reference("push_subscriptions").get() or {}
        print(f"[DEBUG] Subscriptions fetched from DB. Type: {type(subs_ref)}")
    except Exception as e:
        print(f"[DEBUG ERROR] Firebase DB fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase error: {str(e)}")

    if not subs_ref:
        print("[DEBUG WARN] No active subscriptions found in Firebase")
        return {"status": "ok", "sent_count": 0, "message": "No active subscriptions found"}

    sent_count = 0
    failed_count = 0

    if isinstance(subs_ref, dict):
        items = list(subs_ref.items())
    elif isinstance(subs_ref, list):
        items = [(str(idx), val) for idx, val in enumerate(subs_ref) if val]
    else:
        items = []

    print(f"[DEBUG] Total items to process for broadcast: {len(items)}")

    for idx, (sub_key, sub_data) in enumerate(items, start=1):
        print(f"\n[DEBUG] Processing item {idx}/{len(items)} | sub_key: {sub_key}")
        try:
            if not isinstance(sub_data, dict):
                print(f"[DEBUG WARN] Skipping invalid sub_data format for key {sub_key}: {type(sub_data)}")
                failed_count += 1
                continue

            subscription_info = sub_data.get("subscription") or sub_data
            print(f"[DEBUG] Subscription info endpoint: {subscription_info.get('endpoint', 'MISSING')[:40]}...")

            print(f"[DEBUG] Attempting send_notification for {sub_key}...")
            send_notification(
                sub_key=str(sub_key),
                sub_data=subscription_info,
                title=data.title,
                body=data.body,
                event_id="admin_broadcast"
            )
            print(f"[DEBUG SUCCESS] Notification sent successfully for {sub_key}")
            sent_count += 1
        except Exception as err:
            print(f"[DEBUG ERROR] Failed to send notification for {sub_key}: {err}")
            failed_count += 1

    print(f"\n[DEBUG SUMMARY] Broadcast finished. Sent: {sent_count}, Failed: {failed_count}")
    return {
        "status": "ok",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "message": f"Sent: {sent_count}, Failed: {failed_count}"
    }