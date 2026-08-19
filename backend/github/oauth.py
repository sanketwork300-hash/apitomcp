
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode


router = APIRouter(prefix="/auth/github", tags=["GitHub OAuth"])


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = os.getenv(
    "GITHUB_CALLBACK_URL",
    "http://localhost:8001/auth/github/callback",
)


@router.get("/login")
async def github_login() -> RedirectResponse:
    """
    Redirect the user to GitHub's OAuth authorization page.
    """

    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_CLIENT_ID is not configured",
        )

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_CALLBACK_URL,
        "scope": "repo",
    }

    authorization_url = (
        f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
    )

    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def github_callback(code: str) -> dict[str, Any]:
    """
    GitHub redirects the user here after authorization.

    Exchanges the temporary authorization code for an access token.
    """

    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth credentials are not configured",
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing GitHub authorization code",
        )

    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_CALLBACK_URL,
    }

    headers = {
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data=payload,
            headers=headers,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Failed to exchange GitHub authorization code",
        )

    token_data = response.json()

    if "error" in token_data:
        raise HTTPException(
            status_code=400,
            detail={
                "error": token_data.get("error"),
                "description": token_data.get("error_description"),
            },
        )

    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=502,
            detail="GitHub did not return an access token",
        )

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(
        url=f"{frontend_url}/#access_token={access_token}"
    )

