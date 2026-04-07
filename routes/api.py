import json
import time

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from config import config
from proxy import fetch_provider_models, proxy_to_provider

router = APIRouter()


def _check_api_key(request: Request) -> bool:
    if not config.proxy_api_key:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == config.proxy_api_key
    return False


def _api_key_error() -> JSONResponse:
    return JSONResponse(
        {"error": {"message": "Invalid API key", "type": "invalid_request_error", "code": "invalid_api_key"}},
        status_code=401,
    )


async def _get_model_from_request(request: Request, body: bytes) -> str:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            return form.get("model", "")
        except Exception:
            return ""
    if "application/json" in content_type and body:
        try:
            return json.loads(body).get("model", "")
        except Exception:
            pass
    return ""


@router.get("/v1/models")
async def list_models(request: Request):
    if not _check_api_key(request):
        return _api_key_error()

    models = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=10.0, http2=False) as client:
        for provider in config.providers:
            if not provider.enabled:
                continue

            if provider.models:
                for model_id in provider.models:
                    prefixed = f"{provider.name}/{model_id}"
                    if prefixed not in seen_ids:
                        seen_ids.add(prefixed)
                        models.append({
                            "id": prefixed,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": provider.name,
                        })
            else:
                try:
                    resp = await client.get(
                        f"{provider.base_url.rstrip('/')}/models",
                        headers={"Authorization": f"Bearer {provider.api_key}"},
                    )
                    if resp.status_code == 200:
                        for m in resp.json().get("data", []):
                            mid = m.get("id", "")
                            if not mid:
                                continue
                            prefixed = f"{provider.name}/{mid}"
                            if prefixed not in seen_ids:
                                seen_ids.add(prefixed)
                                models.append({
                                    "id": prefixed,
                                    "object": "model",
                                    "created": m.get("created", int(time.time())),
                                    "owned_by": provider.name,
                                })
                except Exception:
                    pass

    return JSONResponse({"object": "list", "data": models})


@router.get("/v1/models/{model_id:path}")
async def get_model(request: Request, model_id: str):
    if not _check_api_key(request):
        return _api_key_error()

    result = config.find_provider_for_model(model_id)
    if not result:
        return JSONResponse(
            {"error": {"message": f"Model '{model_id}' not found", "type": "invalid_request_error"}},
            status_code=404,
        )

    provider, actual_model = result
    return await proxy_to_provider(request, provider, f"models/{actual_model}", b"")


@router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_api(request: Request, path: str):
    if not _check_api_key(request):
        return _api_key_error()

    if not config.providers:
        return JSONResponse(
            {"error": {"message": "No providers configured. Visit the dashboard to add one.", "type": "server_error"}},
            status_code=503,
        )

    body = await request.body()
    model = await _get_model_from_request(request, body)

    provider = None
    model_override = None

    if model:
        result = config.find_provider_for_model(model)
        if result:
            provider, model_override = result
    
    if provider is None:
        provider = next((p for p in config.providers if p.enabled), None)

    if provider is None:
        return JSONResponse(
            {"error": {"message": "No enabled providers available.", "type": "server_error"}},
            status_code=503,
        )

    return await proxy_to_provider(request, provider, path, body, model_override)
