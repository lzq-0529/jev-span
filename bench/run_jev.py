"""Run the Jev recognizer with given settings on bench datasets and store per-dataset metrics.

    uv run python bench/run_jev.py --split dev --limit 20 --tag baseline
    uv run python bench/run_jev.py --split test --tag final --opts '{"type_gate": true}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "eval"))
from evaluate import load_dataset, match, prf  # noqa: E402

from jevspan import JevClient, Recognizer, Schema  # noqa: E402

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


async def run_one(name: str, split: str, limit: int | None, opts: dict, client: JevClient, conc: int) -> dict:
    items = load_dataset(HERE / "sets" / f"{name}_{split}.jsonl")[:limit]
    schema = Schema.load(HERE / "schemas" / f"{name}.json")
    rec = Recognizer(client, schema=schema, **opts)
    sem = asyncio.Semaphore(conc)
    lat: list[float] = []

    async def one(it: dict) -> list[tuple]:
        async with sem:
            t = time.perf_counter()
            r = await rec.recognize(it["text"])
            lat.append(time.perf_counter() - t)
            return [(e.start, e.end, e.label, e.text) for e in r.entities]

    before = client.usage.as_dict()
    t0 = time.perf_counter()
    preds = await asyncio.gather(*(one(it) for it in items))
    wall = time.perf_counter() - t0
    after = client.usage.as_dict()
    usage = {k: round(after[k] - before[k], 6) for k in ("requests", "questions", "input_tokens", "cost_usd", "cache_hits")}
    lat.sort()
    return {
        "dataset": name, "split": split, "n": len(items), **score(items, preds), "usage": usage,
        "cost_per_1k_docs": round(usage["cost_usd"] / len(items) * 1000, 4),
        "wall_s": round(wall, 2), "latency_avg_s": round(sum(lat) / len(lat), 3),
        "latency_p90_s": round(lat[int(0.9 * (len(lat) - 1))], 3),
        "predictions": [[list(p) for p in pr] for pr in preds],
    }


async def main() -> None:
    load_dotenv(HERE.parent / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="*", default=ALL)
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--opts", default="{}", help="Recognizer keyword arguments as JSON")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--concurrency", type=int, default=6, help="documents in flight")
    ap.add_argument("--client-concurrency", type=int, default=8, help="HTTP requests in flight")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--coalesce-ms", type=float, default=10.0)
    args = ap.parse_args()
    opts = json.loads(args.opts)
    out_dir = HERE / "results" / "jev"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    async with JevClient(
        concurrency=args.client_concurrency,
        cache_path=None if args.no_cache else HERE.parent / ".cache/jev.sqlite",
        coalesce_ms=args.coalesce_ms,
    ) as client:
        for name in args.datasets:
            r = await run_one(name, args.split, args.limit, opts, client, args.concurrency)
            r["opts"] = opts
            (out_dir / f"{args.tag}__{args.split}__{name}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            rows.append(r)
            s, rl = r["strict"], r["relaxed"]
            print(
                f"{name:20} n={r['n']:3} strict P/R/F1 {s[0]:.3f}/{s[1]:.3f}/{s[2]:.3f}  relaxed F1 {rl[2]:.3f}  "
                f"${r['cost_per_1k_docs']:.3f}/1k  q={r['usage']['questions']:5}  lat {r['latency_avg_s']:.2f}s",
                flush=True,
            )
    f1 = [r["strict"][2] for r in rows]
    cost = sum(r["usage"]["cost_usd"] for r in rows)
    reqs = sum(r["usage"]["requests"] for r in rows)
    toks = sum(r["usage"]["input_tokens"] for r in rows)
    lat = sum(r["latency_avg_s"] for r in rows) / len(rows)
    print(f"== {args.tag}: mean strict F1 {sum(f1) / len(f1):.3f}  total ${cost:.4f}  requests {reqs}  tokens {toks}  mean latency {lat:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
