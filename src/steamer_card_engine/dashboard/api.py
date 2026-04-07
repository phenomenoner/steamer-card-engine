from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .aggregator import DashboardDataError, build_card_detail, build_day_bundle, list_fixture_dates
from .fixtures import repo_root


def create_app() -> FastAPI:
    root = repo_root()
    frontend_dist = root / "frontend" / "dist"

    app = FastAPI(
        title="Steamer Card Engine Mission Control",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dates")
    def dates() -> list[dict]:
        return list_fixture_dates(root)

    @app.get("/api/days/{date}/deck")
    def deck(date: str) -> dict:
        return build_day_bundle(date, root)["deck_view"]

    @app.get("/api/days/{date}/summary")
    def summary(date: str) -> dict:
        return build_day_bundle(date, root)["daily_summary"]

    @app.get("/api/days/{date}/cards")
    def cards(date: str) -> list[dict]:
        return build_day_bundle(date, root)["strategy_card_summaries"]

    @app.get("/api/days/{date}/lanes/{lane}/cards/{card_id}")
    def card_detail(date: str, lane: str, card_id: str) -> dict:
        return build_card_detail(date, lane, card_id, root)

    @app.get("/api/days/{date}/compare")
    def compare(date: str) -> dict:
        return build_day_bundle(date, root)["compare"]

    @app.get("/api/days/{date}/events")
    def events(date: str) -> dict:
        bundle = build_day_bundle(date, root)
        return {
            "date": date,
            "fixture": bundle["fixture"],
            "event_timeline": bundle["event_timeline"],
            "anomalies": bundle["anomalies"],
        }

    @app.get("/api/days/{date}/transactions")
    def transactions(date: str) -> dict:
        return build_day_bundle(date, root)["transaction_surface"]

    @app.get("/api/days/{date}/snapshots/{snapshot_id}")
    def snapshot(date: str, snapshot_id: str) -> dict:
        bundle = build_day_bundle(date, root)
        try:
            payload = bundle["snapshots"][snapshot_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"unknown snapshot: {snapshot_id}") from error
        return {"date": date, "snapshot_id": snapshot_id, "payload": payload}

    @app.exception_handler(DashboardDataError)
    async def dashboard_data_error_handler(_request, error: DashboardDataError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/")
    def root_index():
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {
            "message": "Mission Control frontend is not built yet.",
            "next_step": "Run `npm install && npm run build` in ./frontend, then reload /.",
        }

    return app
