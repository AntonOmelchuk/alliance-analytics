import os
import json
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from pywebpush import webpush, WebPushException
from firebase_admin import db

PVP_EVENTS = [
    {"name": "Multi Team Battle", "times": ["02:00", "10:00", "18:00"], "type": "mtb"},
    {"name": "Capture The Base", "times": ["04:00", "12:00", "20:00"], "type": "ctb"},
    {"name": "Epic Boss Challenge", "times": ["08:00", "16:00", "00:00"], "type": "ebc"},
    {"name": "Death Match", "times": ["06:00", "14:00", "22:00"], "type": "dm"},
]

EVENT_EMOJIS = {
    "siege": "🏰",
    "ch": "🛡️",
    "mtb": "⚔️",
    "ctb": "🚩",
    "ebc": "🐲",
    "dm": "☠️",
    "qa": "🐜",
    "core": "⚙️",
    "orfen": "🕸️",
    "zaken": "🏴‍☠️",
    "tezza": "🎻",
    "baium": "👑",
    "antharas": "🐉",
    "valakas": "🔥",
}

NOTIFICATIONS_I18N = {
    "en": {
        "title": "{emoji} Reminder: {event_name}",
        "body": "Event starts in {minutes} minutes!",
    },
    "ua": {
        "title": "{emoji} Нагадування: {event_name}",
        "body": "Подія розпочнеться через {minutes} хв!",
    },
}

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS_SUB = os.getenv("VAPID_MAILTO", "mailto:tohaomelchuk@gmail.com")

# Global tracker for deduplication across worker execution cycles
SENT_TRACKER = set()

def get_event_emoji(event_type: str) -> str:
    return EVENT_EMOJIS.get(event_type, "⚡")

def get_notification_text(lang: str, event_name: str, minutes: int, event_type: str = ""):
    lang_code = "ua" if str(lang).lower() in ["ua", "uk"] else "en"
    translations = NOTIFICATIONS_I18N[lang_code]
    emoji = get_event_emoji(event_type)

    title = translations["title"].format(emoji=emoji, event_name=event_name)
    body = translations["body"].format(minutes=minutes)

    return title, body

def remove_invalid_subscription(sub_key: str):
    try:
        db.reference(f"push_subscriptions/{sub_key}").delete()
        print(f"🧹 Successfully removed invalid subscription: {sub_key}")
    except Exception as e:
        print(f"Failed to delete subscription {sub_key}: {e}")

def send_notification(sub_key: str, sub_data: dict, title: str, body: str, event_id: str):
    try:
        if isinstance(sub_data, str):
            sub_data = json.loads(sub_data)

        endpoint = sub_data.get("endpoint")
        keys = sub_data.get("keys")

        if isinstance(keys, str):
            keys = json.loads(keys)

        if not endpoint or not keys or not isinstance(keys, dict):
            print(f"⚠️ Missing or invalid endpoint/keys for {sub_key}")
            return

        parsed_url = urlparse(endpoint)
        aud_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

        vapid_claims = {
            "sub": VAPID_CLAIMS_SUB,
            "aud": aud_origin
        }

        payload = json.dumps({
            "title": title,
            "body": body,
            "eventId": event_id
        })

        headers = {
            "Urgency": "high",
            "TTL": "300"
        }

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": keys.get("p256dh"),
                    "auth": keys.get("auth")
                }
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            headers=headers,
            ttl=300
        )
        print(f"✅ Push sent for event '{event_id}' -> target: {sub_key[:10]}...")

    except WebPushException as ex:
        print(f"❌ WebPushException for {sub_key}: {ex}")

        if ex.response and ex.response.status_code in [400, 403, 404, 410]:
            remove_invalid_subscription(sub_key)
    except Exception as err:
        print(f"Failed to send notification to {sub_key}: {err}")


async def check_and_send_push_notifications():
    global SENT_TRACKER
    print("\n⏰ --- [CRON WORKER RUN] Checking Push Notifications ---")

    # Clear memory cache if it grows too large
    if len(SENT_TRACKER) > 2000:
        SENT_TRACKER.clear()

    now_utc = datetime.now(timezone.utc)
    current_timestamp_ms = int(now_utc.timestamp() * 1000)

    print(f"🕒 Current UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} | MS: {current_timestamp_ms}")

    try:
        events_ref = db.reference("regroups/events").get() or {}
        subs_ref = db.reference("push_subscriptions").get() or {}
    except Exception as e:
        print(f"❌ [WORKER ERROR] Failed to fetch data from Firebase: {e}")
        return

    if not subs_ref:
        print("⚠️ [WORKER WARN] No active subscriptions found in Firebase. Exiting worker.")
        return

    events_schedule = {}

    # 1. Parse Firebase Dynamic Events (Epic Bosses, Sieges, Clan Halls)
    if isinstance(events_ref, dict):
        events_iterator = events_ref.items()
    elif isinstance(events_ref, list):
        events_iterator = [(str(idx), item) for idx, item in enumerate(events_ref) if item]
    else:
        events_iterator = []

    for event_id, event_data in events_iterator:
        if not event_data or not isinstance(event_data, dict):
            continue
        respawn_ts = event_data.get("respawnTimestamp")
        if respawn_ts:
            try:
                ts_val = int(respawn_ts)
                # Convert seconds to milliseconds if timestamp is 10-digit
                if ts_val < 10000000000:
                    ts_val *= 1000

                # Determine correct title for notifications
                title_val = (
                    event_data.get("event") or
                    event_data.get("name") or
                    event_data.get("title") or
                    event_id
                )

                payload = {
                    "title": title_val,
                    "timestamp": ts_val,
                    "type": event_data.get("type", ""),
                    "is_pvp": False  # Dynamic event (auto-deletes after push)
                }

                # Map primary ID (e.g. "ch-4")
                if event_data.get("id"):
                    events_schedule[event_data["id"]] = payload

                # Map event name aliases (e.g. "Fortress of the Dead", "Bandit Stronghold")
                if event_data.get("event"):
                    events_schedule[event_data["event"]] = payload
                if event_data.get("name"):
                    events_schedule[event_data["name"]] = payload

                # Fallback to dictionary key
                events_schedule[str(event_id)] = payload

            except ValueError:
                continue

    # 2. Parse PVP_EVENTS (Recurring daily events - UTC strictly)
    for event in PVP_EVENTS:
        event_name = event["name"]
        event_type = event["type"]

        for t_str in event["times"]:
            hours, minutes = map(int, t_str.split(":"))

            event_dt = now_utc.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if event_dt < now_utc:
                event_dt += timedelta(days=1)

            ts_ms = int(event_dt.timestamp() * 1000)

            payload = {
                "title": f"{event_name} ({t_str})",
                "timestamp": ts_ms,
                "type": event_type,
                "is_pvp": True  # Recurring daily PVP event
            }

            # Map full key with time (e.g. "Capture The Base-12:00")
            events_schedule[f"{event_name}-{t_str}"] = payload

            # Fallback for base event key without time
            if event_name not in events_schedule or ts_ms < events_schedule[event_name]["timestamp"]:
                events_schedule[event_name] = payload

    total_subs = len(subs_ref)
    print(f"\n📱 Processing {total_subs} subscription(s)...")

    for sub_key, sub_data in subs_ref.items():
        if not isinstance(sub_data, dict):
            continue

        endpoint = sub_data.get("endpoint", "")
        alerts = sub_data.get("alerts", {})
        user_lang = sub_data.get("lang", "en")

        print(f"\n🔍 [Sub: {sub_key[:12]}...] Subscribed alerts count: {len(alerts)}")

        # Create a static list of keys to safely iterate while potentially deleting keys
        alert_keys = list(alerts.keys())

        for event_key in alert_keys:
            alert_info = alerts[event_key]

            if event_key in events_schedule:
                event = events_schedule[event_key]
                respawn_ts = event["timestamp"]
                is_pvp = event.get("is_pvp", False)

                # Deduplicate by unique endpoint + target event timestamp
                dedup_key = f"{endpoint}_{respawn_ts}"

                if dedup_key in SENT_TRACKER:
                    print(f"   ⏩ Skipping duplicate push for '{event_key}' to sub {sub_key[:8]}")
                    continue

                lead_time_min = alert_info.get("leadTimeMinutes", 30)

                diff_seconds = (respawn_ts - current_timestamp_ms) / 1000
                diff_minutes = round(diff_seconds / 60)

                print(f"   👉 Alert '{event_key}': target lead={lead_time_min}m | current diff={diff_minutes}m ({diff_seconds:.1f}s)")

                # Target window: from 2 minutes late (-120s) up to 1 minute early (+60s)
                target_seconds = lead_time_min * 60
                is_time_to_send = -120 <= (target_seconds - diff_seconds) <= 60

                if is_time_to_send:
                    print(f"   🚀 MATCH! Sending push for '{event_key}' (Lead: {lead_time_min}m)...")
                    event_title = event["title"]

                    title, body = get_notification_text(
                        lang=user_lang,
                        event_name=event_title,
                        minutes=lead_time_min,
                        event_type=event.get("type", "")
                    )

                    # 1. Dispatch WebPush notification
                    send_notification(
                        sub_key=sub_key,
                        sub_data=sub_data,
                        title=title,
                        body=body,
                        event_id=event_key
                    )

                    SENT_TRACKER.add(dedup_key)

                    # 2. Cleanup: Remove alert if it's a dynamic event (Epic Boss, Siege, Clan Hall)
                    if not is_pvp:
                        try:
                            alert_ref = db.reference(f"push_subscriptions/{sub_key}/alerts/{event_key}")
                            alert_ref.delete()
                            print(f"   🧹 Removed dynamic alert '{event_key}' from Firebase for sub {sub_key[:8]}")
                        except Exception as del_err:
                            print(f"   ❌ Failed to remove dynamic alert '{event_key}' from Firebase: {del_err}")
                    else:
                        print(f"   🔄 Retained recurring PVP alert '{event_key}' in Firebase for future events.")
            else:
                print(f"   ❓ Alert '{event_key}' configured by user, but NOT found in active events_schedule")

    print("\n✅ --- [CRON WORKER COMPLETE] ---")