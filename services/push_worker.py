import os
import json
from datetime import datetime, timezone, timedelta
from pywebpush import webpush, WebPushException
from firebase_admin import db

PVP_EVENTS = [
    {"name": "Multi Team Battle", "times": ["02:00", "10:00", "18:00"], "type": "mtb" },
    {"name": "Capture The Base", "times": ["04:00", "12:00", "20:00"], "type": "ctb" },
    {"name": "Epic Boss Challenge", "times": ["08:00", "16:00", "00:00"], "type": "ebc" },
    {"name": "Death Match", "times": ["06:00", "14:00", "22:00"], "type": "dm" },
]

EVENT_EMOJIS = {
    "siege": "🏰",      # Siege
    "ch": "🛡️",         # Clan Hall
    "mtb": "⚔️",        # Multi Team Battle
    "ctb": "🚩",        # Capture The Base
    "ebc": "🐲",        # Epic Boss Challenge
    "dm": "☠️",         # Death Match
    # Epic Bosses
    "qa": "🐜",         # Queen Ant
    "core": "⚙️",       # Core
    "orfen": "🕸️",      # Orfen
    "zaken": "🏴‍☠️",      # Zaken
    "tezza": "🎻",      # Frintezza
    "baium": "👑",      # Baium
    "antharas": "🐉",   # Antharas
    "valakas": "🔥",     # Valakas
}

NOTIFICATIONS_I18N = {
    "en": {
        "title": "⚡ Reminder: {event_name}",
        "body": "Event starts in {minutes} minutes!",
    },
    "ua": {
        "title": "⚡ Нагадування: {event_name}",
        "body": "Подія розпочнеться через {minutes} хв!",
    },
}

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = os.getenv("VAPID_CLAIMS")

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
        payload = json.dumps({"title": title, "body": body, "eventId": event_id})
        webpush(
            subscription_info={"endpoint": sub_data["endpoint"], "keys": sub_data["keys"]},
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            ttl=300
        )
        print(f"✅ Push sent for event '{event_id}' -> target: {sub_key[:10]}...")
    except WebPushException as ex:
        if ex.response and ex.response.status_code in [404, 410]:
            remove_invalid_subscription(sub_key)

async def check_and_send_push_notifications():
    now_utc = datetime.now(timezone.utc)
    current_timestamp_ms = int(now_utc.timestamp() * 1000)

    events_ref = db.reference("regroups/events").get() or {}
    subs_ref = db.reference("push_subscriptions").get() or {}

    if not subs_ref:
        return

    events_schedule = {}

    # Process events from Firebase RTDB (Bosses / Sieges / Clan Halls)
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
            key = event_data.get("id") or event_data.get("name") or event_id
            events_schedule[key] = {
                "title": event_data.get("name") or event_data.get("title") or key,
                "timestamp": int(respawn_ts),
                "type": event_data.get("type", "")
            }

    # Process recurring daily PvP events
    for event in PVP_EVENTS:
        event_name = event["name"]
        event_type = event["type"]
        upcoming_timestamps = []
        for t_str in event["times"]:
            hours, minutes = map(int, t_str.split(":"))
            event_dt = now_utc.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if event_dt < now_utc:
                event_dt += timedelta(days=1)
            upcoming_timestamps.append(int(event_dt.timestamp() * 1000))

        if upcoming_timestamps:
            events_schedule[event_name] = {
                "title": event_name,
                "timestamp": min(upcoming_timestamps),
                "type": event_type
            }

    # Check alert conditions
    for sub_key, sub_data in subs_ref.items():
        alerts = sub_data.get("alerts", {})
        # Get language (default = en)
        user_lang = sub_data.get("lang", "en")

        for event_key, alert_info in alerts.items():
            if event_key in events_schedule:
                event = events_schedule[event_key]
                respawn_ts = event["timestamp"]
                lead_time_min = alert_info.get("leadTimeMinutes", 30)
                diff_minutes = round((respawn_ts - current_timestamp_ms) / (1000 * 60))

                if diff_minutes == lead_time_min:
                    event_title = event["title"]

                    title, body = get_notification_text(
                        lang=user_lang,
                        event_name=event_title,
                        minutes=lead_time_min,
                        event_type=event.get("type", "")
                    )

                    send_notification(
                        sub_key=sub_key,
                        sub_data=sub_data,
                        title=title,
                        body=body,
                        event_id=event_key
                    )