import os
import time
import httpx
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from firebase_admin import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5173/auth/callback")


class DiscordAuthPayload(BaseModel):
    code: str


def get_client_ip(request: Request) -> str:
    """Extracts client IP considering reverse proxies (Vercel, Nginx, Cloudflare)"""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/discord")
async def auth_discord(payload: DiscordAuthPayload, request: Request):
    code = payload.code

    # 1. Exchange code for access_token
    token_url = "https://discord.com/api/oauth2/token"
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=data, headers=headers)
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from Discord."
            )

        token_data = token_res.json()
        access_token = token_data.get("access_token")

        # 2. Fetch User Profile
        user_url = "https://discord.com/api/users/@me"
        user_headers = {"Authorization": f"Bearer {access_token}"}
        user_res = await client.get(user_url, headers=user_headers)
        if user_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user profile from Discord."
            )

        discord_user = user_res.json()

    discord_id = str(discord_user["id"])
    username = discord_user.get("username")
    avatar_hash = discord_user.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
        if avatar_hash
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    # Extract IP & User-Agent Device Info
    current_ip = get_client_ip(request)
    current_device = request.headers.get("user-agent", "Unknown Device")
    now_ms = int(time.time() * 1000)

    user_ref = db.reference(f"users/{discord_id}")
    existing_user = user_ref.get()

    if not existing_user:
        # 🆕 First sign up
        user_data = {
            "discord_id": discord_id,
            "username": username,
            "avatar_url": avatar_url,
            "char_name": "",
            "cp_name": "",
            "is_setup_complete": False, # Done onboarding or not
            "role": "MEMBER",
            "created_at": now_ms,

            # Tracking Fields
            "originalIP": current_ip,
            "originalDevice": current_device,
            "IPlist": [current_ip],
            "devicesList": [current_device],
            "last_login_at": now_ms
        }
        user_ref.set(user_data)
    else:
        # 🔄 New Login -> Update IPlist and devicesList if have new one
        user_data = existing_user

        # Update IP List
        ip_list = user_data.get("IPlist", [])
        if current_ip not in ip_list:
            ip_list.append(current_ip)

        # Update devices list
        devices_list = user_data.get("devicesList", [])
        if current_device not in devices_list:
            devices_list.append(current_device)

        user_ref.update({
            "username": username,
            "avatar_url": avatar_url,
            "IPlist": ip_list,
            "devicesList": devices_list,
            "last_login_at": now_ms
        })

        user_data["IPlist"] = ip_list
        user_data["devicesList"] = devices_list

    return {
        "status": "success",
        "user": user_data,
        "token": access_token
    }