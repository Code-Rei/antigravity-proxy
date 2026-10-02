import time
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from config import REDIRECT_URI, BASE_URL
from app.auth.oauth import generate_auth_url, exchange_code, get_user_email, discover_project_id
from app.auth.manager import account_manager
from app.auth.models import AntigravityAccount
from app.core.headers import generate_fingerprint

router = APIRouter(tags=["oauth"])

@router.get("/oauth/start")
async def oauth_start(request: Request):
    base_url = str(request.base_url).rstrip("/") or BASE_URL
    callback_uri = f"{base_url}/oauth-callback"
    url = generate_auth_url(redirect_uri=callback_uri)
    return RedirectResponse(url)

@router.get("/oauth-callback")
async def oauth_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    if error:
        return HTMLResponse(
            f"<h2>Google OAuth Error</h2><p>{error}</p><a href='/'>Return to Dashboard</a>",
            status_code=400
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    base_url = str(request.base_url).rstrip("/") or BASE_URL
    callback_uri = f"{base_url}/oauth-callback"

    try:
        token_data = await exchange_code(code, redirect_uri=callback_uri)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not refresh_token:
            return HTMLResponse(
                "<h3>No Refresh Token Received</h3>"
                "<p>Please revoke access to Antigravity at <a href='https://myaccount.google.com/permissions' target='_blank'>Google Account Permissions</a> and log in again to generate an offline refresh token.</p>"
                "<a href='/oauth/start'>Try Again</a> | <a href='/'>Return Home</a>",
                status_code=400
            )

        email = await get_user_email(access_token)
        project_id = await discover_project_id(access_token)

        account = AntigravityAccount(
            email=email,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=int(time.time()) + expires_in,
            project_id=project_id,
            health_score=100,
            fingerprint=generate_fingerprint()
        )
        await account_manager.add_account(account)
        print(f"[OAuth] Successfully connected account: {email} (project: {project_id})")

        return RedirectResponse("/?added=" + email)
    except Exception as e:
        return HTMLResponse(
            f"<h2>Failed to exchange OAuth token</h2><p>{str(e)}</p><a href='/'>Back to Dashboard</a>",
            status_code=500
        )
