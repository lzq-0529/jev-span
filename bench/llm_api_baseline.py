"""Zero-shot NER through a hosted OpenAI-compatible chat API (e.g. Alibaba Model Studio / DashScope).

Same prompt and type descriptions as the local vLLM baseline and as Jev.

    uv run python bench/llm_api_baseline.py --model qwen3.8-27b
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE.parent / "eval"))
from evaluate import load_dataset, match, prf  # noqa: E402
from llm_common import PROMPT, to_spans  # noqa: E402

from jev_ner.schema import Schema  # noqa: E402

ALL = [
    "msra", "resume", "cluener", "weibo", "conll", "wnut", "mitres",
    "crossner_ai", "crossner_literature", "crossner_music", "crossner_politics", "crossner_science",
]


def score(items: list[dict], preds: list[list[tuple]]) -> dict:
    out = {}
    for mode in ("strict", "relaxed"):
        tp = fp = fn = 0
        for it, pr in zip(items, preds):
            a, b, c = match(it["gold"], pr, relaxed=(mode == "relaxed"))
            tp, fn, fp = tp + len(a), fn + len(b), fp + len(c)
        out[mode] = [round(x, 4) for x in prf(tp, fp, fn)]
    return out


OPTIONAL_FIELDS = ("response_format", "enable_thinking")


def parse_entities(content: str) -> list:
    """Accept plain JSON, fenced JSON or JSON after a reasoning preamble."""
    if not content:
        return []
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return []
    ents = data.get("entities", []) if isinstance(data, dict) else []
    return ents if isinstance(ents, list) else []


async def call(http: httpx.AsyncClient, url: str, model: str, prompt: str, sem: asyncio.Semaphore, dropped: set) -> tuple[dict, float]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    for attempt in range(8):
        for f in dropped:
            body.pop(f, None)
        async with sem:
            t = time.perf_counter()
            try:
                resp = await http.post(url, json=body)
            except httpx.TransportError:
                resp = None
            elapsed = time.perf_counter() - t
        if resp is not None and resp.status_code == 200:
            return resp.json(), elapsed
        if resp is not None and resp.status_code == 400:
            # Some providers reject JSON mode or the thinking switch: drop the optional field and retry.
            text = resp.text.lower()
            culprit = next((f for f in OPTIONAL_FIELDS if f in body and (f in text or f.split("_")[0] in text)), None)
            culprit = culprit or next((f for f in OPTIONAL_FIELDS if f in body), None)
            if culprit:
                dropped.add(culprit)
                continue
        if resp is not None and resp.status_code not in (429, 500, 502, 503, 504):
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        await asyncio.sleep(1.5 * 2**attempt + random.random())
    raise RuntimeError("API request failed after retries")


async def main() -> None:
    load_dotenv(HERE.parent / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.8-27b")
    ap.add_argument("--tag")
    ap.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    ap.add_argument("--datasets", nargs="*", default=ALL)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    tag = args.tag or args.model.replace(".", "_").replace("-", "_")
    key = os.environ["QWEN_API_KEY"]
    out = HERE / "results" / "api"
    out.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    dropped: set[str] = set()
    url = f"{args.base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=120, headers={"Authorization": f"Bearer {key}"}) as http:
        for name in args.datasets:
            items = load_dataset(HERE / "sets" / f"{name}_test.jsonl")[: args.limit]
            schema = Schema.load(HERE / "schemas" / f"{name}.json")
            types = "\n".join(f"- {t.name}: {t.criterion()}" for t in schema.types)
            t0 = time.perf_counter()
            results = await asyncio.gather(
                *(call(http, url, args.model, PROMPT.format(types=types, text=it["text"]), sem, dropped) for it in items)
            )
            wall = time.perf_counter() - t0
            preds, lat, usage = [], [], {"prompt_tokens": 0, "completion_tokens": 0}
            for it, (data, elapsed) in zip(items, results):
                lat.append(elapsed)
                for k in ("prompt_tokens", "completion_tokens"):
                    usage[k] += int(data.get("usage", {}).get(k, 0))
                try:
                    ents = parse_entities(data["choices"][0]["message"].get("content") or "")
                except (KeyError, IndexError, AttributeError):
                    ents = []
                preds.append(to_spans(it["text"], ents, set(schema.names)))
            r = {
                "method": tag, "model": args.model, "dataset": name, "n": len(items), **score(items, preds),
                "latency_avg_s": round(sum(lat) / len(lat), 3), "wall_s": round(wall, 1),
                "usage": {**usage, "dropped_params": sorted(dropped)},
                "predictions": [[list(p) for p in pr] for pr in preds],
            }
            (out / f"{tag}__{name}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            print(f"{tag:14} {name:20} strict F1 {r['strict'][2]:.3f}  relaxed {r['relaxed'][2]:.3f}  "
                  f"{r['latency_avg_s']:.2f}s/doc  tokens in/out {usage['prompt_tokens']}/{usage['completion_tokens']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
