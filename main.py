import asyncio

import uvicorn
from fastapi import FastAPI

from config import config
from proxy import fetch_provider_models
from routes.api import router as api_router
from routes.dashboard import router as dashboard_router


async def _refresh_models_once():
    changed = False
    for provider in config.providers:
        if provider.enabled and provider.models_auto:
            models = await fetch_provider_models(provider.base_url, provider.api_key)
            if models and models != provider.models:
                provider.models = models
                changed = True
    if changed:
        config._save_providers()


async def _model_refresh_loop():
    await asyncio.sleep(10)
    while True:
        try:
            await _refresh_models_once()
        except Exception:
            pass
        await asyncio.sleep(3600)


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_model_refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="Ruci", lifespan=lifespan, docs_url=None, redoc_url=None)

app.include_router(dashboard_router)
app.include_router(api_router)


if __name__ == "__main__":
    print(f"  Ruci starting on http://{config.host}:{config.port}")
    print(f"  Dashboard: http://{'localhost' if config.host == '0.0.0.0' else config.host}:{config.port}/")
    print(f"  API base:  http://{'localhost' if config.host == '0.0.0.0' else config.host}:{config.port}/v1")
    uvicorn.run("main:app", host=config.host, port=config.port, reload=False)
