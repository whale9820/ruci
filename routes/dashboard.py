import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from auth import SESSION_COOKIE, create_session_token, is_authenticated
from config import Provider, config
from proxy import fetch_provider_models

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _require_auth(request: Request):
    if not config.is_setup():
        return RedirectResponse("/setup", status_code=302)
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None


def _flash(base: str, success: str = "", error: str = "") -> str:
    params = []
    if success:
        params.append(f"success={success.replace(' ', '+')}")
    if error:
        params.append(f"error={error.replace(' ', '+')}")
    return f"{base}?{'&'.join(params)}" if params else base


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not config.is_setup():
        return RedirectResponse("/setup", status_code=302)
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if config.is_setup():
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "setup.html")


@router.post("/setup")
async def setup_post(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(...),
):
    if config.is_setup():
        return RedirectResponse("/dashboard", status_code=302)
    if not password or len(password) < 6:
        return templates.TemplateResponse(request, "setup.html", {"error": "Password must be at least 6 characters."})
    if password != confirm:
        return templates.TemplateResponse(request, "setup.html", {"error": "Passwords do not match."})
    config.set_password(password)
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(SESSION_COOKIE, create_session_token(), httponly=True, samesite="lax", max_age=604800)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not config.is_setup():
        return RedirectResponse("/setup", status_code=302)
    if is_authenticated(request):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    if not config.verify_password(password):
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid password."})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(SESSION_COOKIE, create_session_token(), httponly=True, samesite="lax", max_age=604800)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    redir = _require_auth(request)
    if redir:
        return redir
    return templates.TemplateResponse(request, "dashboard.html", {
        "providers": config.providers,
        "proxy_api_key": config.proxy_api_key,
        "host": config.host,
        "port": config.port,
        "success": request.query_params.get("success", ""),
        "error": request.query_params.get("error", ""),
    })


@router.post("/dashboard/providers/add")
async def add_provider(
    request: Request,
    name: str = Form(...),
    base_url: str = Form(...),
    api_key: str = Form(...),
    models_raw: str = Form(""),
):
    redir = _require_auth(request)
    if redir:
        return redir
    models = [m.strip() for m in models_raw.replace(",", "\n").splitlines() if m.strip()]
    provider = Provider(id=str(uuid.uuid4()), name=name, base_url=base_url.rstrip("/"), api_key=api_key, models=models)
    config.add_provider(provider)
    return RedirectResponse(_flash("/dashboard", success=f"Provider '{name}' added."), status_code=302)


@router.post("/dashboard/providers/{provider_id}/update")
async def update_provider(
    request: Request,
    provider_id: str,
    name: str = Form(...),
    base_url: str = Form(...),
    api_key: str = Form(...),
    models_raw: str = Form(""),
):
    redir = _require_auth(request)
    if redir:
        return redir
    existing = config.get_provider(provider_id)
    if not existing:
        return RedirectResponse(_flash("/dashboard", error="Provider not found."), status_code=302)
    models = [m.strip() for m in models_raw.replace(",", "\n").splitlines() if m.strip()]
    updated = Provider(id=provider_id, name=name, base_url=base_url.rstrip("/"), api_key=api_key, models=models, enabled=existing.enabled)
    config.update_provider(provider_id, updated)
    return RedirectResponse(_flash("/dashboard", success=f"Provider '{name}' updated."), status_code=302)


@router.post("/dashboard/providers/{provider_id}/delete")
async def delete_provider(request: Request, provider_id: str):
    redir = _require_auth(request)
    if redir:
        return redir
    provider = config.get_provider(provider_id)
    name = provider.name if provider else "Unknown"
    config.delete_provider(provider_id)
    return RedirectResponse(_flash("/dashboard", success=f"Provider '{name}' deleted."), status_code=302)


@router.post("/dashboard/providers/{provider_id}/toggle")
async def toggle_provider(request: Request, provider_id: str):
    redir = _require_auth(request)
    if redir:
        return redir
    provider = config.get_provider(provider_id)
    if not provider:
        return RedirectResponse(_flash("/dashboard", error="Provider not found."), status_code=302)
    provider.enabled = not provider.enabled
    config.update_provider(provider_id, provider)
    state = "enabled" if provider.enabled else "disabled"
    return RedirectResponse(_flash("/dashboard", success=f"Provider '{provider.name}' {state}."), status_code=302)


@router.post("/dashboard/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    redir = _require_auth(request)
    if redir:
        return redir
    if not config.verify_password(current_password):
        return RedirectResponse(_flash("/dashboard", error="Current password is incorrect."), status_code=302)
    if len(new_password) < 6:
        return RedirectResponse(_flash("/dashboard", error="New password must be at least 6 characters."), status_code=302)
    if new_password != confirm_password:
        return RedirectResponse(_flash("/dashboard", error="New passwords do not match."), status_code=302)
    config.set_password(new_password)
    response = RedirectResponse(_flash("/dashboard", success="Password changed successfully."), status_code=302)
    response.set_cookie(SESSION_COOKIE, create_session_token(), httponly=True, samesite="lax", max_age=604800)
    return response


@router.post("/dashboard/api-key")
async def set_api_key(request: Request, proxy_api_key: str = Form("")):
    redir = _require_auth(request)
    if redir:
        return redir
    config.set_proxy_api_key(proxy_api_key.strip())
    msg = "Proxy API key updated." if proxy_api_key.strip() else "Proxy API key cleared (open access)."
    return RedirectResponse(_flash("/dashboard", success=msg), status_code=302)


@router.post("/dashboard/fetch-models")
async def fetch_models_ajax(request: Request):
    redir = _require_auth(request)
    if redir:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    data = await request.json()
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    if not base_url:
        return JSONResponse({"error": "base_url is required"}, status_code=400)
    models = await fetch_provider_models(base_url, api_key)
    return JSONResponse({"models": models})
