import json
from typing import Optional

import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from config import Provider

_HOP_BY_HOP = {
    "transfer-encoding",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}


def _build_headers(request: Request, api_key: str) -> dict:
    headers = {}
    for k, v in request.headers.items():
        if k.lower() not in ("host", "content-length", "transfer-encoding", "connection"):
            headers[k] = v
    headers["authorization"] = f"Bearer {api_key}"
    return headers


def _filter_response_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def _patch_model_in_body(body: bytes, model: str, content_type: str) -> bytes:
    if "application/json" not in content_type:
        return body
    try:
        data = json.loads(body)
        if "model" in data:
            data["model"] = model
            return json.dumps(data).encode()
    except Exception:
        pass
    return body


def _is_streaming(body: bytes, content_type: str) -> bool:
    if "application/json" not in content_type:
        return False
    try:
        return bool(json.loads(body).get("stream"))
    except Exception:
        return False


async def proxy_to_provider(
    request: Request,
    provider: Provider,
    path: str,
    body: bytes,
    model_override: Optional[str] = None,
) -> Response:
    target_url = f"{provider.base_url.rstrip('/')}/{path.lstrip('/')}"
    content_type = request.headers.get("content-type", "")
    headers = _build_headers(request, provider.api_key)

    if model_override is not None:
        body = _patch_model_in_body(body, model_override, content_type)

    if body:
        headers["content-length"] = str(len(body))

    if _is_streaming(body, content_type):
        async def generate():
            async with httpx.AsyncClient(timeout=None, http2=False) as client:
                async with client.stream(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    follow_redirects=True,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    async with httpx.AsyncClient(timeout=300.0, http2=False) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            follow_redirects=True,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_filter_response_headers(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


async def fetch_provider_models(base_url: str, api_key: str) -> list:
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=10.0, http2=False) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception:
        pass
    return []
