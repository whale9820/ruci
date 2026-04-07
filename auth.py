from typing import Optional

from fastapi import Cookie, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import config

SESSION_COOKIE = "ruci_session"
SESSION_MAX_AGE = 86400 * 7


def create_session_token() -> str:
    s = URLSafeTimedSerializer(config.session_secret)
    return s.dumps({"auth": True})


def verify_session_token(token: str) -> bool:
    s = URLSafeTimedSerializer(config.session_secret)
    try:
        data = s.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("auth") is True
    except (BadSignature, SignatureExpired):
        return False


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    return bool(token and verify_session_token(token))


def login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)


def dashboard_redirect() -> RedirectResponse:
    return RedirectResponse("/dashboard", status_code=302)
