from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from steamer_card_engine.observer import (
    list_mock_sessions,
    observer_bootstrap_payload,
    observer_candles_payload,
    observer_stream_events,
    observer_timeline_payload,
)

from .aggregator import DashboardDataError, build_card_detail, build_day_bundle, list_fixture_dates
from .fixtures import repo_root
from .strategy_pipeline import StrategyPipelineDataError, build_strategy_pipeline_view
from .strategy_powerhouse import StrategyPowerhouseDataError, build_strategy_powerhouse_view


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

    @app.get("/api/strategy-powerhouse")
    def strategy_powerhouse() -> dict:
        return build_strategy_powerhouse_view(root)

    @app.get("/api/strategy-pipeline")
    def strategy_pipeline() -> dict:
        return build_strategy_pipeline_view(root)

    @app.get("/api/observer/sessions")
    def observer_sessions() -> dict:
        return {"items": list_mock_sessions()}

    @app.get("/api/observer/sessions/{session_id}/bootstrap")
    def observer_bootstrap(session_id: str) -> dict:
        if session_id != "aws-live-sim-demo":
            raise HTTPException(status_code=404, detail=f"unknown observer session: {session_id}")
        return observer_bootstrap_payload()

    @app.get("/api/observer/sessions/{session_id}/candles")
    def observer_candles(session_id: str, limit: int = 500) -> dict:
        if session_id != "aws-live-sim-demo":
            raise HTTPException(status_code=404, detail=f"unknown observer session: {session_id}")
        return observer_candles_payload(limit=limit)

    @app.get("/api/observer/sessions/{session_id}/timeline")
    def observer_timeline(session_id: str, limit: int = 200) -> dict:
        if session_id != "aws-live-sim-demo":
            raise HTTPException(status_code=404, detail=f"unknown observer session: {session_id}")
        return observer_timeline_payload(limit=limit)

    @app.websocket("/api/observer/sessions/{session_id}/stream")
    async def observer_stream(websocket: WebSocket, session_id: str) -> None:
        if session_id != "aws-live-sim-demo":
            await websocket.close(code=4404)
            return
        await websocket.accept()
        raw_after_seq = websocket.query_params.get("after_seq", "0")
        try:
            after_seq = int(raw_after_seq)
        except ValueError:
            await websocket.send_json({"type": "error", "detail": f"invalid after_seq: {raw_after_seq}"})
            await websocket.close(code=4400)
            return

        try:
            for event in observer_stream_events(after_seq=after_seq):
                await websocket.send_json(event)
            await websocket.send_json({"type": "stream_end", "after_seq": after_seq})
        except WebSocketDisconnect:
            return
        await websocket.close()

    @app.exception_handler(DashboardDataError)
    async def dashboard_data_error_handler(_request, error: DashboardDataError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(StrategyPowerhouseDataError)
    async def strategy_powerhouse_data_error_handler(
        _request,
        error: StrategyPowerhouseDataError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(StrategyPipelineDataError)
    async def strategy_pipeline_data_error_handler(
        _request,
        error: StrategyPipelineDataError,
    ) -> JSONResponse:
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
