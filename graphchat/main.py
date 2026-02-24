from __future__ import annotations
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .db import connect, init_db
from .llm_client import LlmClient, LlmError
from .models import (
    AskIn,
    AskOut,
    GraphOut,
    InitSessionIn,
    InitSessionOut,
    UpdatePositionIn,
)
from .repository import Repository
from .services.graph_service import GraphService

config = load_config(Path.cwd())
init_db(config.db.path)

app = FastAPI(title="GraphChat API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors.origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _services() -> tuple[Repository, GraphService]:
    conn = connect(config.db.path)
    repo = Repository(conn)
    llm = LlmClient(config.llm)
    return repo, GraphService(repo, llm)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sessions")
def list_sessions(limit: int = 50) -> list[dict]:
    repo, _ = _services()
    try:
        return [s.model_dump() for s in repo.list_sessions(limit=limit)]
    finally:
        repo.conn.close()


@app.post("/api/sessions/init", response_model=InitSessionOut)
def init_session(req: InitSessionIn) -> InitSessionOut:
    repo, graph_svc = _services()
    try:
        session, nodes, edges = graph_svc.init_session(req.topic.strip())
        return InitSessionOut(session=session, nodes=nodes, edges=edges)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=f"LLM_UNAVAILABLE: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        repo.conn.close()


@app.post("/api/sessions/init/stream")
def init_session_stream(req: InitSessionIn) -> StreamingResponse:
    repo, graph_svc = _services()

    def event_stream():
        try:
            gen = graph_svc.init_session_stream(req.topic.strip())
            while True:
                try:
                    event = next(gen)
                    etype = event.get("type")
                    if etype == "start":
                        payload = json.dumps(
                            {
                                "type": "start",
                                "nodes": [n.model_dump() for n in event.get("nodes", [])],
                                "edges": [e.model_dump() for e in event.get("edges", [])],
                                "root_node_id": event.get("root_node_id"),
                            },
                            ensure_ascii=False,
                        )
                    elif etype == "knowledge_start":
                        node = event.get("node")
                        edge = event.get("edge")
                        payload = json.dumps(
                            {
                                "type": "knowledge_start",
                                "node": node.model_dump() if node else None,
                                "edge": edge.model_dump() if edge else None,
                            },
                            ensure_ascii=False,
                        )
                    else:
                        payload = json.dumps(
                            {
                                "type": "token",
                                "node_id": event.get("node_id"),
                                "content": event.get("content", ""),
                            },
                            ensure_ascii=False,
                        )
                    yield f"data: {payload}\n\n"
                except StopIteration as stop:
                    session, nodes, edges = stop.value
                    result = InitSessionOut(session=session, nodes=nodes, edges=edges)
                    payload = json.dumps({"type": "done", "result": result.model_dump()}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    break
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        finally:
            repo.conn.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/sessions/{session_id}/graph", response_model=GraphOut)
def get_graph(session_id: str) -> GraphOut:
    repo, _ = _services()
    try:
        return GraphOut(nodes=repo.list_nodes(session_id), edges=repo.list_edges(session_id))
    finally:
        repo.conn.close()


@app.post("/api/sessions/{session_id}/ask", response_model=AskOut)
def ask(session_id: str, req: AskIn) -> AskOut:
    repo, graph_svc = _services()
    try:
        return graph_svc.ask(
            session_id,
            req.question.strip(),
            req.node_ids,
            [s.model_dump() for s in req.selected_sections],
        )
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=f"LLM_UNAVAILABLE: {exc}") from exc
    finally:
        repo.conn.close()


@app.post("/api/sessions/{session_id}/ask/stream")
def ask_stream(session_id: str, req: AskIn) -> StreamingResponse:
    repo, graph_svc = _services()

    def event_stream():
        try:
            gen = graph_svc.ask_stream(
                session_id,
                req.question.strip(),
                req.node_ids,
                [s.model_dump() for s in req.selected_sections],
            )
            while True:
                try:
                    event = next(gen)
                    etype = event.get("type")
                    if etype == "start":
                        payload = json.dumps(
                            {
                                "type": "start",
                                "nodes": [n.model_dump() for n in event.get("nodes", [])],
                                "question_node_id": event.get("question_node_id"),
                                "answer_node_id": event.get("answer_node_id"),
                                "edges": [e.model_dump() for e in event.get("edges", [])],
                            },
                            ensure_ascii=False,
                        )
                    elif etype == "knowledge_start":
                        node = event.get("node")
                        edge = event.get("edge")
                        payload = json.dumps(
                            {
                                "type": "knowledge_start",
                                "node": node.model_dump() if node else None,
                                "edge": edge.model_dump() if edge else None,
                            },
                            ensure_ascii=False,
                        )
                    elif etype == "question_title":
                        payload = json.dumps(
                            {
                                "type": "question_title",
                                "node_id": event.get("node_id"),
                                "title": event.get("title", ""),
                            },
                            ensure_ascii=False,
                        )
                    else:
                        payload = json.dumps(
                            {
                                "type": "token",
                                "node_id": event.get("node_id"),
                                "content": event.get("content", ""),
                            },
                            ensure_ascii=False,
                        )
                    yield f"data: {payload}\n\n"
                except StopIteration as stop:
                    result = stop.value
                    payload = json.dumps({"type": "done", "result": result.model_dump()}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    break
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        finally:
            repo.conn.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.patch("/api/sessions/{session_id}/nodes/{node_id}/position")
def update_position(session_id: str, node_id: str, req: UpdatePositionIn) -> dict[str, bool]:
    repo, _ = _services()
    try:
        repo.update_node_position(session_id, node_id, req.x, req.y, req.width)
        return {"ok": True}
    finally:
        repo.conn.close()


@app.post("/api/sessions/{session_id}/materials")
async def upload_material(session_id: str, file: UploadFile = File(...)) -> dict[str, str]:
    repo, _ = _services()
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Empty filename.")
        ext = file.filename.lower().split(".")[-1]
        if ext not in {"txt", "md"}:
            raise HTTPException(status_code=400, detail="Only .txt/.md are supported in MVP.")
        data = await file.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="File must be UTF-8 text.") from exc
        material_id = repo.add_material(
            session_id=session_id,
            filename=file.filename,
            mime_type=file.content_type or "text/plain",
            content_text=text,
        )
        return {"id": material_id}
    finally:
        repo.conn.close()


def run() -> None:
    uvicorn.run(app, host=config.server.host, port=config.server.port)


@app.get("/", response_model=None)
def index() -> Response:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return JSONResponse({"message": "Frontend not built. Run `make web-build`."}, status_code=404)


@app.get("/{full_path:path}", response_model=None)
def spa_fallback(full_path: str) -> Response:
    if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json", "redoc"}:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return JSONResponse({"message": "Frontend not built. Run `make web-build`."}, status_code=404)


if __name__ == "__main__":
    run()
