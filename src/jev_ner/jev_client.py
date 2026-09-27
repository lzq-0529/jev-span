"""Minimal async client for TypeSafe's Jev System One API (POST /v1/systemone)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 529}


class JevError(RuntimeError):
    pass


@dataclass
class Usage:
    requests: int = 0
    questions: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    retries: int = 0
    seconds: float = 0.0
    models: set[str] = field(default_factory=set)

    @property
    def cost_usd(self) -> float:
        return self.input_tokens * PRICE_PER_INPUT_TOKEN

    def as_dict(self) -> dict:
        return {
            "requests": self.requests,
            "questions": self.questions,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "retries": self.retries,
            "api_seconds": round(self.seconds, 3),
            "cost_usd": round(self.cost_usd, 6),
            "models": sorted(self.models),
        }


class _Cache:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS answers (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        self._db.commit()

    def get(self, key: str) -> dict | None:
        row = self._db.execute("SELECT v FROM answers WHERE k = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_many(self, items: list[tuple[str, dict]]) -> None:
        self._db.executemany(
            "INSERT OR REPLACE INTO answers (k, v) VALUES (?, ?)",
            [(k, json.dumps(v, ensure_ascii=False)) for k, v in items],
        )
        self._db.commit()


class JevClient:
    """Asks many `choice` questions about one `state` and returns each option's probability."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        concurrency: int = 8,
        max_questions_per_request: int = 40,
        timeout: float = 60.0,
        max_attempts: int = 6,
        cache_path: str | Path | None = ".cache/jev.sqlite",
        coalesce_ms: float = 10.0,
        max_chars_per_request: int = 40000,
    ):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
        if not self.api_key:
            raise JevError("Missing API key: set TYPESAFE_API_KEY (or JEV_API_KEY).")
        self.base_url = (base_url or os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("TYPESAFE_DEFAULT_MODEL") or DEFAULT_MODEL
        self.max_questions_per_request = max_questions_per_request
        self.max_attempts = max_attempts
        self.usage = Usage()
        self._sem = asyncio.Semaphore(concurrency)
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        self._cache = _Cache(cache_path) if cache_path else None
        # Questions about the same state issued within `coalesce_ms` share one request (and its state tokens).
        self.coalesce_s = coalesce_ms / 1000
        self.max_chars_per_request = max_chars_per_request
        self._batches: dict[str, list[tuple[str, dict, asyncio.Future]]] = {}
        self._flush_scheduled: set[str] = set()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "JevClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    def _key(self, state: str, instructions: str, criteria: dict[str, str]) -> str:
        blob = json.dumps([self.model, state, instructions, criteria], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    async def choose_many(
        self, state: str, instructions: list[str], criteria: dict[str, str]
    ) -> list[dict[str, float]]:
        """One probability map per instruction, in order. Identical instructions are asked once."""
        results: dict[str, dict[str, float]] = {}
        pending: list[str] = []
        for ins in dict.fromkeys(instructions):
            cached = self._cache.get(self._key(state, ins, criteria)) if self._cache else None
            if cached is not None:
                results[ins] = cached
                self.usage.cache_hits += 1
            else:
                pending.append(ins)

        if self.coalesce_s > 0:
            answered = await asyncio.gather(*(self._enqueue(state, ins, criteria) for ins in pending))
        else:
            size = self.max_questions_per_request
            chunks = [pending[i : i + size] for i in range(0, len(pending), size)]
            per_chunk = await asyncio.gather(*(self._ask(state, [(ins, criteria) for ins in chunk]) for chunk in chunks))
            answered = [p for probs_list in per_chunk for p in probs_list]
        fresh: list[tuple[str, dict]] = []
        for ins, probs in zip(pending, answered):
            results[ins] = probs
            if self._cache:
                fresh.append((self._key(state, ins, criteria), probs))
        if fresh and self._cache:
            self._cache.put_many(fresh)
        return [results[ins] for ins in instructions]

    def _enqueue(self, state: str, instruction: str, criteria: dict) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._batches.setdefault(state, []).append((instruction, criteria, fut))
        if state not in self._flush_scheduled:
            self._flush_scheduled.add(state)
            loop.call_later(self.coalesce_s, lambda: asyncio.ensure_future(self._flush(state)))
        return fut

    async def _flush(self, state: str) -> None:
        self._flush_scheduled.discard(state)
        items = self._batches.pop(state, [])
        chunks: list[list[tuple[str, dict, asyncio.Future]]] = []
        current: list[tuple[str, dict, asyncio.Future]] = []
        chars = 0
        for item in items:
            size = len(item[0]) + sum(len(k) + len(v or "") for k, v in item[1].items())
            if current and (len(current) >= self.max_questions_per_request or chars + size > self.max_chars_per_request):
                chunks.append(current)
                current, chars = [], 0
            current.append(item)
            chars += size
        if current:
            chunks.append(current)
        await asyncio.gather(*(self._send(state, chunk) for chunk in chunks))

    async def _send(self, state: str, chunk: list[tuple[str, dict, asyncio.Future]]) -> None:
        try:
            answers = await self._ask(state, [(ins, crit) for ins, crit, _ in chunk])
        except Exception as exc:  # delivered to every caller waiting on this request
            for *_, fut in chunk:
                if not fut.done():
                    fut.set_exception(exc)
            return
        for (*_, fut), probs in zip(chunk, answers):
            if not fut.done():
                fut.set_result(probs)

    async def _ask(self, state: str, questions: list[tuple[str, dict]]) -> list[dict[str, float]]:
        try:
            return await self._ask_once(state, questions)
        except JevError as exc:
            if "max_tokens_exceeded" not in str(exc) or len(questions) < 2:
                raise
        mid = len(questions) // 2
        first, second = await asyncio.gather(self._ask(state, questions[:mid]), self._ask(state, questions[mid:]))
        return first + second

    async def _ask_once(self, state: str, questions: list[tuple[str, dict]]) -> list[dict[str, float]]:
        body = {
            "model": self.model,
            "state": state,
            "questions": {
                f"q{i}": {"type": "choice", "instructions": ins, "criteria": crit}
                for i, (ins, crit) in enumerate(questions)
            },
        }
        data = await self._post(body)
        out = []
        for i, (_, crit) in enumerate(questions):
            ans = data["answers"].get(f"q{i}")
            if not ans or "probabilities" not in ans:
                raise JevError(f"Jev returned no answer for question q{i}: {ans!r}")
            out.append({k: float(ans["probabilities"].get(k, 0.0)) for k in crit})
        self.usage.questions += len(questions)
        return out

    async def _post(self, body: dict) -> dict:
        url = f"{self.base_url}/v1/systemone"
        last_error: str = ""
        for attempt in range(self.max_attempts):
            async with self._sem:
                t0 = time.perf_counter()
                try:
                    resp = await self._http.post(url, json=body)
                except httpx.TransportError as exc:
                    resp, last_error = None, f"{type(exc).__name__}: {exc}"
                finally:
                    self.usage.seconds += time.perf_counter() - t0
            if resp is not None:
                if resp.status_code == 200:
                    data = resp.json()
                    self.usage.requests += 1
                    self.usage.input_tokens += int(data.get("usage", {}).get("input_tokens", 0))
                    if data.get("model"):
                        self.usage.models.add(data["model"])
                    return data
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                if resp.status_code not in RETRY_STATUS:
                    raise JevError(last_error)
                retry_after = resp.headers.get("retry-after")
            else:
                retry_after = None
            if attempt == self.max_attempts - 1:
                break
            self.usage.retries += 1
            delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 0.5 * 2**attempt
            await asyncio.sleep(delay + random.uniform(0, 0.25))
        raise JevError(f"Jev request failed after {self.max_attempts} attempts: {last_error}")
