"""Zero-shot NER by prompting an open LLM through vLLM (JSON-constrained output), same type descriptions as Jev.

    python bench/llm_baseline.py --model Qwen/Qwen3-8B --out bench/results/gpu
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.sampling_params import StructuredOutputsParams

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
from baselines_gpu import ALL, load_items, score  # noqa: E402
from llm_common import PROMPT, json_schema, to_spans  # noqa: E402

from jev_ner.schema import Schema  # noqa: E402

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--tag", default="qwen3_8b")
    ap.add_argument("--datasets", nargs="*", default=ALL)
    ap.add_argument("--out", default=str(HERE / "results" / "gpu"))
    ap.add_argument("--latency-sample", type=int, default=20, help="documents timed one at a time")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len, gpu_memory_utilization=args.gpu_memory_utilization,
        enable_prefix_caching=True, trust_remote_code=True,
    )
    tok = llm.get_tokenizer()
    for name in args.datasets:
        items = load_items(name)
        schema = Schema.load(HERE / "schemas" / f"{name}.json")
        types = "\n".join(f"- {t.name}: {t.criterion()}" for t in schema.types)
        params = SamplingParams(
            temperature=0.0, max_tokens=1024,
            structured_outputs=StructuredOutputsParams(json=json_schema(schema.names)),
        )
        prompts = [
            tok.apply_chat_template(
                [{"role": "user", "content": PROMPT.format(types=types, text=it["text"])}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False,
            )
            for it in items
        ]
        t0 = time.perf_counter()
        outs = llm.generate(prompts, params, use_tqdm=False)
        batch_s = time.perf_counter() - t0
        lat = []
        for p in prompts[: args.latency_sample]:
            t = time.perf_counter()
            llm.generate([p], params, use_tqdm=False)
            lat.append(time.perf_counter() - t)
        preds = []
        for it, o in zip(items, outs):
            try:
                ents = json.loads(o.outputs[0].text).get("entities", [])
            except (json.JSONDecodeError, AttributeError):
                ents = []
            preds.append(to_spans(it["text"], ents, set(schema.names)))
        r = {
            "method": args.tag, "model": args.model, "dataset": name, "n": len(items), **score(items, preds),
            "latency_avg_s": round(sum(lat) / len(lat), 4), "throughput_docs_per_s": round(len(items) / batch_s, 2),
            "device": "cuda", "predictions": [[list(p) for p in pr] for pr in preds],
        }
        (out / f"{args.tag}__{name}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        print(f"{args.tag:12} {name:20} strict F1 {r['strict'][2]:.3f}  relaxed {r['relaxed'][2]:.3f}  {r['latency_avg_s']*1000:.0f} ms/doc  {r['throughput_docs_per_s']} docs/s", flush=True)


if __name__ == "__main__":
    main()
