"""Evaluate the recognizer on eval/dataset.jsonl against the live Jev API.

    uv run python eval/evaluate.py                 # all configurations
    uv run python eval/evaluate.py --config full   # one configuration
    uv run python eval/evaluate.py --errors        # also list every miss / false alarm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from jevspan import DEFAULT_SCHEMA, JevClient, Recognizer, Schema

HERE = Path(__file__).parent
CONFIGS = {
    "choice": dict(refine="choice", propagate=True),
    "choice-no-propagate": dict(refine="choice", propagate=False),
    "choice-sequential": dict(refine="choice", propagate=True, speculative=False),
    "choice-explore": dict(refine="choice", propagate=True, explore_threshold=0.0),
    "choice-no-vote": dict(refine="choice", propagate=True, vote_variants=0),
    "scan-vote": dict(refine="scan", propagate=True),
    "scan": dict(refine="scan", propagate=False),
    "no-context": dict(refine="choice", propagate=True, use_context=False),
    "punctuation-only": dict(ngram=False, propagate=False),
}
DEFAULT_CONFIGS = ["choice", "scan", "punctuation-only"]


def load_dataset(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cursor = 0
        spans = []
        if item["entities"] and len(item["entities"][0]) == 4:
            item["gold"] = [(s, e, label, text) for text, label, s, e in item["entities"]]
            items.append(item)
            continue
        for text, label in item["entities"]:
            start = item["text"].find(text, cursor)
            if start < 0:
                start = item["text"].find(text)
            if start < 0:
                raise ValueError(f"{item['id']}: gold entity {text!r} not in text")
            spans.append((start, start + len(text), label, text))
            cursor = start + len(text)
        item["gold"] = spans
        items.append(item)
    return items


def overlaps(a: tuple, b: tuple) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def match(gold: list[tuple], pred: list[tuple], relaxed: bool) -> tuple[list, list, list]:
    """Returns (true positives, false negatives, false positives) with one-to-one matching."""
    used: set[int] = set()
    tp, fn = [], []
    for g in gold:
        hit = None
        for i, p in enumerate(pred):
            if i in used or p[2] != g[2]:
                continue
            if (relaxed and overlaps(g, p)) or (not relaxed and (g[0], g[1]) == (p[0], p[1])):
                hit = i
                break
        if hit is None:
            fn.append(g)
        else:
            used.add(hit)
            tp.append(g)
    fp = [p for i, p in enumerate(pred) if i not in used]
    return tp, fn, fp


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


async def run_config(
    name: str, items: list[dict], client: JevClient, doc_concurrency: int, schema: Schema
) -> dict:
    recognizer = Recognizer(client, schema=schema, **CONFIGS[name])
    labels = schema.names
    sem = asyncio.Semaphore(doc_concurrency)
    before = client.usage.as_dict()
    latencies: list[float] = []

    async def one(item: dict) -> list[tuple]:
        async with sem:
            t = time.perf_counter()
            result = await recognizer.recognize(item["text"])
            latencies.append(time.perf_counter() - t)
            return [(e.start, e.end, e.label, e.text) for e in result.entities]

    t0 = time.perf_counter()
    preds = await asyncio.gather(*(one(it) for it in items))
    wall = time.perf_counter() - t0
    after = client.usage.as_dict()

    latencies.sort()
    report: dict = {
        "config": name,
        "wall_seconds": round(wall, 2),
        "doc_latency_avg": round(sum(latencies) / len(latencies), 3),
        "doc_latency_p90": round(latencies[int(0.9 * (len(latencies) - 1))], 3),
    }
    report["usage"] = {
        k: round(after[k] - before[k], 6) for k in ("requests", "questions", "cache_hits", "input_tokens", "cost_usd")
    }
    errors = []
    for mode in ("strict", "relaxed"):
        counts = {lab: Counter() for lab in labels}
        clean_negatives = 0
        negatives = 0
        for item, pred in zip(items, preds):
            tp, fn, fp = match(item["gold"], pred, relaxed=(mode == "relaxed"))
            for g in tp:
                counts[g[2]]["tp"] += 1
            for g in fn:
                counts[g[2]]["fn"] += 1
            for p in fp:
                counts.setdefault(p[2], Counter())["fp"] += 1
            if not item["gold"]:
                negatives += 1
                clean_negatives += int(not pred)
            if mode == "strict" and (fn or fp):
                errors.append({"id": item["id"], "text": item["text"], "missed": fn, "false": fp})
        per_label = {}
        total = Counter()
        for lab, c in counts.items():
            per_label[lab] = [round(x, 3) for x in prf(c["tp"], c["fp"], c["fn"])]
            total.update(c)
        report[mode] = {
            "micro_prf": [round(x, 3) for x in prf(total["tp"], total["fp"], total["fn"])],
            "per_label_prf": per_label,
            "tp": total["tp"], "fp": total["fp"], "fn": total["fn"],
        }
        report["no_entity_texts_clean"] = f"{clean_negatives}/{negatives}"
    report["errors"] = errors
    return report


def print_report(r: dict, show_errors: bool) -> None:
    print(
        f"\n=== {r['config']} ===  wall {r['wall_seconds']}s  per-doc avg {r['doc_latency_avg']}s "
        f"p90 {r['doc_latency_p90']}s  usage {r['usage']}"
    )
    for mode in ("strict", "relaxed"):
        m = r[mode]
        p, rc, f = m["micro_prf"]
        print(f"  {mode:8} P={p:.3f} R={rc:.3f} F1={f:.3f}  (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
        for lab, (lp, lr, lf) in m["per_label_prf"].items():
            print(f"           {lab:13} P={lp:.3f} R={lr:.3f} F1={lf:.3f}")
    print(f"  texts with no entities left clean: {r['no_entity_texts_clean']}")
    if show_errors:
        for e in r["errors"]:
            miss = ", ".join(f"{g[3]}/{g[2]}" for g in e["missed"]) or "-"
            fa = ", ".join(f"{p[3]}/{p[2]}" for p in e["false"]) or "-"
            print(f"  [{e['id']}] missed: {miss} | predicted: {fa}")


def print_summary(name: str, runs: list[dict]) -> None:
    def stat(values: list[float]) -> str:
        return f"{sum(values) / len(values):.3f} [{min(values):.3f}-{max(values):.3f}]"

    strict = [r["strict"]["micro_prf"][2] for r in runs]
    relaxed = [r["relaxed"]["micro_prf"][2] for r in runs]
    p = [r["strict"]["micro_prf"][0] for r in runs]
    rc = [r["strict"]["micro_prf"][1] for r in runs]
    cost = sum(r["usage"]["cost_usd"] for r in runs) / len(runs)
    questions = sum(r["usage"]["questions"] for r in runs) / len(runs)
    lat = sum(r["doc_latency_avg"] for r in runs) / len(runs)
    print(
        f"{name:22} x{len(runs)}  strict F1 {stat(strict)}  P {stat(p)}  R {stat(rc)}  "
        f"relaxed F1 {stat(relaxed)}  questions {questions:.0f}  ${cost:.4f}  per-doc {lat:.3f}s"
    )


async def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=list(CONFIGS), action="append")
    ap.add_argument("--dataset", default=str(HERE / "dataset.jsonl"))
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--schema", help="zero-shot schema JSON (default: person / organization / address)")
    ap.add_argument("--doc-concurrency", type=int, default=6)
    ap.add_argument("--repeat", type=int, default=1, help="run each config N times (implies --no-cache) and average")
    args = ap.parse_args()

    items = load_dataset(Path(args.dataset))
    schema = Schema.load(args.schema) if args.schema else DEFAULT_SCHEMA
    no_cache = args.no_cache or args.repeat > 1
    reports = []
    async with JevClient(cache_path=None if no_cache else ".cache/jev.sqlite") as client:
        for name in args.config or DEFAULT_CONFIGS:
            runs = []
            for _ in range(args.repeat):
                report = await run_config(name, items, client, args.doc_concurrency, schema)
                if args.repeat == 1:
                    print_report(report, args.errors)
                runs.append(report)
            if args.repeat > 1:
                print_summary(name, runs)
            reports.extend(runs)
    out = HERE / "runs"
    out.mkdir(exist_ok=True)
    path = out / f"report-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfull report: {path}")


if __name__ == "__main__":
    asyncio.run(main())
