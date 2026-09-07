"""Authentication: signed session cookie (login form) or bearer token for programmatic access. No anonymous access.
CSRF token required for cookie-authenticated mutations. Rate limit for manual job triggers."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from hashlib import sha256

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from director.config import Settings

SESSION_COOKIE = "director_session"
SESSION_MAX_AGE = 12 * 3600


class Auth:
    def __init__(self, settings: Settings):
        if not settings.app_auth_secret:
            raise RuntimeError("APP_AUTH_SECRET must be set to run the API (no anonymous access)")
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(settings.app_auth_secret, salt="director-session")
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    # -- credentials -----------------------------------------------------------------------------
    def check_password(self, user: str, password: str) -> bool:
        if not self.settings.app_admin_password:
            return False  # login disabled until an admin password is configured
        return hmac.compare_digest(user, self.settings.app_admin_user) and hmac.compare_digest(
            password, self.settings.app_admin_password
        )

    def check_token(self, token: str) -> bool:
        return bool(self.settings.app_api_token) and hmac.compare_digest(token, self.settings.app_api_token)

    # -- sessions --------------------------------------------------------------------------------
    def issue_session(self, user: str) -> str:
        return self.serializer.dumps({"u": user, "csrf": secrets.token_urlsafe(24)})

    def read_session(self, cookie: str | None) -> dict | None:
        if not cookie:
            return None
        try:
            return self.serializer.loads(cookie, max_age=SESSION_MAX_AGE)
        except BadSignature:
            return None

    def current_user(self, request: Request) -> dict:
        authz = request.headers.get("authorization", "")
        if authz.lower().startswith("bearer ") and self.check_token(authz[7:].strip()):
            return {"u": "api-token", "csrf": None, "kind": "token"}
        sess = self.read_session(request.cookies.get(SESSION_COOKIE))
        if sess:
            return {**sess, "kind": "cookie"}
        if request.url.path.startswith("/api/") or "text/html" not in request.headers.get("accept", ""):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    def require_csrf(self, request: Request, user: dict, token: str | None) -> None:
        if user.get("kind") == "token":
            return
        if not token or not user.get("csrf") or not hmac.compare_digest(token, user["csrf"]):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid CSRF token")

    # -- rate limit (manual triggers) ---------------------------------------------------------------
    def rate_limit(self, key: str, limit: int = 10, window: int = 60) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
        q.append(now)


def fingerprint(value: str) -> str:
    return sha256(value.encode()).hexdigest()[:12]
