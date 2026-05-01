from __future__ import annotations

from importlib import resources
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(title="why?", docs_url=None, redoc_url=None)

    from why.web.csrf import CSRFMiddleware
    app.add_middleware(CSRFMiddleware)

    static_dir = Path(str(resources.files("why.web").joinpath("static")))
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/installs", status_code=307)

    from why.web.routes.installs import router as installs_router
    app.include_router(installs_router)

    from why.web.routes.share import router as share_router
    app.include_router(share_router)

    from why.web.routes.export import router as export_router
    app.include_router(export_router)

    from why.web.routes.dashboard import router as dashboard_router
    app.include_router(dashboard_router)

    from why.web.routes.review import router as review_router
    app.include_router(review_router)

    from why.web.routes.settings import router as settings_router
    app.include_router(settings_router)

    return app
