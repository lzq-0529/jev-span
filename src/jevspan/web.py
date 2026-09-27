"""Small web UI: `uv run jevspan-web` then open http://127.0.0.1:47321."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .jev_client import JevClient, JevError
from .recognizer import Recognizer
from .schema import DEFAULT_SCHEMA, Schema

HERE = Path(__file__).parent
STATIC = HERE / "static"
PRESETS = HERE / "presets"
MAX_CHARS = 5000


class RecognizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    schema_: dict | None = Field(default=None, alias="schema")
    use_context: bool = True
    window: bool = True
    refine: str = "choice"
    propagate: bool = True


def presets() -> dict[str, dict]:
    out = {"default": {"name": "人名 / 机构 / 地址", **DEFAULT_SCHEMA.to_dict()}}
    names = {"medical": "医疗：药品 / 疾病 / 检查项目", "ecommerce": "电商：品牌 / 产品型号 / 价格"}
    for path in sorted(PRESETS.glob("*.json")):
        out[path.stem] = {"name": names.get(path.stem, path.stem), **json.loads(path.read_text(encoding="utf-8"))}
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    try:
        app.state.client = JevClient()
        app.state.error = None
    except JevError as exc:
        app.state.client = None
        app.state.error = str(exc)
    yield
    if app.state.client:
        await app.state.client.aclose()


app = FastAPI(title="JevSpan", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": app.state.client is not None, "error": app.state.error}


@app.get("/api/presets")
async def get_presets() -> dict:
    return presets()


@app.post("/api/recognize")
async def recognize(req: RecognizeRequest) -> dict:
    client: JevClient | None = app.state.client
    if client is None:
        raise HTTPException(503, app.state.error or "Jev client unavailable")
    if not req.text.strip():
        raise HTTPException(422, "文本为空")
    try:
        schema = Schema.from_dict(req.schema_) if req.schema_ else DEFAULT_SCHEMA
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(422, f"实体类型定义有误：{exc}") from exc
    if req.refine not in ("choice", "scan"):
        raise HTTPException(422, "refine 只能是 choice 或 scan")
    before = client.usage.as_dict()
    recognizer = Recognizer(
        client,
        schema=schema,
        use_context=req.use_context,
        ngram=req.window,
        refine=req.refine,
        propagate=req.propagate,
    )
    try:
        result = await recognizer.recognize(req.text)
    except JevError as exc:
        raise HTTPException(502, str(exc)) from exc
    after = client.usage.as_dict()
    payload = result.as_dict()
    payload["usage"] = {
        k: round(after[k] - before[k], 6) for k in ("requests", "questions", "cache_hits", "input_tokens", "cost_usd")
    }
    payload["model"] = after["models"]
    payload["labels"] = {t.name: t.title for t in schema.types}
    return payload


def main() -> None:
    import uvicorn

    uvicorn.run(
        "jevspan.web:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "47321")),
    )


if __name__ == "__main__":
    main()
