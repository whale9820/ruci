import uvicorn
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from config import config
from routes.api import router as api_router
from routes.dashboard import router as dashboard_router

app = FastAPI(title="Ruci", docs_url=None, redoc_url=None)

app.include_router(dashboard_router)
app.include_router(api_router)


if __name__ == "__main__":
    print(f"  Ruci starting on http://{config.host}:{config.port}")
    print(f"  Dashboard: http://{'localhost' if config.host == '0.0.0.0' else config.host}:{config.port}/")
    print(f"  API base:  http://{'localhost' if config.host == '0.0.0.0' else config.host}:{config.port}/v1")
    uvicorn.run("main:app", host=config.host, port=config.port, reload=False)
