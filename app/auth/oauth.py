import urllib.parse
import httpx
from typing import Dict, Any, Optional
from config import (
    ANTIGRAVITY_CLIENT_ID,
    ANTIGRAVITY_CLIENT_SECRET,
    ANTIGRAVITY_SCOPES,
    DEFAULT_PROJECT_ID,
    REDIRECT_URI,
)
from app.core.headers import get_antigravity_headers

TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
LOAD_CODE_ASSIST_URL = "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"

def generate_auth_url(redirect_uri: str = REDIRECT_URI) -> str:
    params = {
        "client_id": ANTIGRAVITY_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(ANTIGRAVITY_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

async def exchange_code(code: str, redirect_uri: str = REDIRECT_URI) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "client_id": ANTIGRAVITY_CLIENT_ID,
                "client_secret": ANTIGRAVITY_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        res.raise_for_status()
        return res.json()

async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "client_id": ANTIGRAVITY_CLIENT_ID,
                "client_secret": ANTIGRAVITY_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        res.raise_for_status()
        return res.json()

async def get_user_email(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        res.raise_for_status()
        data = res.json()
        return data.get("email", "unknown@user.com")

async def discover_project_id(access_token: str) -> str:
    headers = get_antigravity_headers(access_token)
    payload = {
        "metadata": {
            "ideType": "ANTIGRAVITY",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI"
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                LOAD_CODE_ASSIST_URL,
                headers=headers,
                json=payload
            )
            if res.is_success:
                data = res.json()
                cloudaicompanion_project = data.get("cloudaicompanionProject")
                if cloudaicompanion_project:
                    return str(cloudaicompanion_project)
                # Check for alternate project fields
                if "project" in data:
                    return str(data["project"])
    except Exception as e:
        print(f"[OAuth] Project discovery error: {e}")

    return DEFAULT_PROJECT_ID
