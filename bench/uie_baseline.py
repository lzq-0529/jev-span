"""Baidu UIE (schema-driven zero-shot extraction, PaddleNLP Taskflow) on the bench test sets.

    python bench/uie_baseline.py --model uie-m-base --out bench/results/gpu
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
from bench_common import ALL, load_items, score  # noqa: E402

from jevspan.schema import Schema  # noqa: E402


def main() -> None:
    from paddlenlp import Taskflow

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="uie-m-base")
    ap.add_argument("--tag", default="uie_m_base")
    ap.add_argument("--datasets", nargs="*", default=ALL)
    ap.add_argument("--out", default=str(HERE / "results" / "gpu"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ie = None
    for name in args.datasets:
        items = load_items(name)
        schema = Schema.load(HERE / "schemas" / f"{name}.json")
        # UIE prompts are type names; the schema titles are the natural-language names.
        prompt2key = {t.title: t.name for t in schema.types}
        if ie is None:
            ie = Taskflow("information_extraction", schema=list(prompt2key), model=args.model, device_id=0)
        else:
            ie.set_schema(list(prompt2key))
        ie(items[0]["text"])  # warm-up
        lat, preds = [], []
        for it in items:
            t = time.perf_counter()
            res = ie(it["text"])[0]
            lat.append(time.perf_counter() - t)
            spans = []
            for prompt, ents in res.items():
                for e in ents:
                    spans.append((int(e["start"]), int(e["end"]), prompt2key[prompt], e["text"]))
            preds.append(spans)
        r = {
            "method": args.tag, "model": f"paddlenlp/{args.model}", "dataset": name, "n": len(items), **score(items, preds),
            "latency_avg_s": round(sum(lat) / len(lat), 4), "device": "cuda",
            "predictions": [[list(p) for p in pr] for pr in preds],
        }
        (out / f"{args.tag}__{name}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        print(f"{args.tag:12} {name:20} strict F1 {r['strict'][2]:.3f}  relaxed {r['relaxed'][2]:.3f}  {r['latency_avg_s']*1000:.1f} ms/doc", flush=True)


if __name__ == "__main__":
    main()
