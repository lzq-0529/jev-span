"""Full benchmark report: accuracy, precision/recall, latency, cost and resources for every method and dataset.

    uv run python bench/final_report.py > bench/results/FINAL_REPORT.md
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
RES = HERE / "results"
DATASETS = [
    "msra", "resume", "cluener", "weibo", "conll", "wnut", "mitres",
    "crossner_ai", "crossner_literature", "crossner_music", "crossner_politics", "crossner_science",
]
SHORT = {
    "msra": "MSRA", "resume": "Resume", "cluener": "CLUENER", "weibo": "Weibo", "conll": "CoNLL03",
    "wnut": "WNUT17", "mitres": "MIT-Rest", "crossner_ai": "CN-AI", "crossner_literature": "CN-Lit",
    "crossner_music": "CN-Music", "crossner_politics": "CN-Pol", "crossner_science": "CN-Sci",
}
GPU_USD_PER_HOUR = 0.22  # RTX 3090 on AutoDL, about ¥1.6/h
# USD per 1M tokens (input, output), Model Studio Beijing list price, Sep 2026 (DeepSeek: peak-hour price).
API_PRICES = {
    "qwen3.8-27b": (0.424, 1.696),
    "qwen3.8-flash": (0.113, 0.382),
    "qwen3.8-max": (1.696, 5.088),
    "deepseek-v4.1-flash": (0.283, 1.131),
    "glm-5.3": (1.131, 3.958),
    "kimi-k2.6": (0.894, 3.713),
    "MiniMax-M2.5": (0.304, 1.213),
}

# key, display name, accuracy source, speed/cost source
METHODS = [
    ("accurate", "Jev + our pipeline", ("jev", "accurate"), ("jev", "seq_accurate")),
    ("qwen27b", "Qwen3.8-27B prompt (API)", ("api", "qwen3_8_27b"), ("api", "qwen3_8_27b")),
    ("qwen8b", "Qwen3-8B prompt (vLLM, 3090)", ("gpu", "qwen3_8b"), ("gpu", "qwen3_8b")),
    ("gliner25", "GLiNER2.5-multi", ("gpu", "gliner2.5"), ("gpu", "gliner2.5")),
    ("gliner_multi", "GLiNER-multi v2.1", ("gpu", "gliner_multi"), ("gpu", "gliner_multi")),
    ("gliner_large", "GLiNER-large v2.1 (EN only)", ("gpu", "gliner_large"), ("gpu", "gliner_large")),
    ("nuner", "NuNER-Zero (EN only)", ("gpu", "nuner_zero"), ("gpu", "nuner_zero")),
]

RESOURCES = {
    "accurate": ("–", "–", "none (HTTPS client)", "Jev API", "type name + 1-line description"),
    "qwen27b": ("27B", "–", "none (HTTPS client)", "DashScope API", "same prompt / descriptions"),
    "qwen8b": ("8.2B", "15.3 GB", "~21 GB (vLLM pre-allocates 90%)", "RTX 3090 24 GB", "same prompt / descriptions"),
    "gliner25": ("~0.29B", "1.1 GB", "2.8 GB", "RTX 3090 (or CPU)", "label + description"),
    "gliner_multi": ("~0.3B", "2.2 GB", "2.4 GB", "RTX 3090 (or CPU)", "label names"),
    "gliner_large": ("~0.46B", "1.7 GB", "2.8 GB", "RTX 3090 (or CPU)", "label names"),
    "nuner": ("~0.45B", "3.3 GB", "3.3 GB", "RTX 3090 (or CPU)", "label names"),
}


def load(kind: str, tag: str) -> dict[str, dict]:
    out = {}
    for name in DATASETS:
        if kind == "jev":
            path = RES / "jev" / f"{tag}__test__{name}.json"
        elif kind == "jevdev":
            path = RES / "jev" / f"{tag}__dev__{name}.json"
        else:
            path = RES / kind / f"{tag}__{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def pct(x):
    return "–" if x is None else f"{x * 100:.1f}"


def per_doc_cost(key: str, r: dict) -> float | None:
    if key == "accurate":
        return r["usage"]["cost_usd"] / r["n"]
    if key == "qwen27b":
        pin, pout = API_PRICES[r["model"]]
        return (r["usage"]["prompt_tokens"] * pin + r["usage"]["completion_tokens"] * pout) / 1e6 / r["n"]
    if "throughput_docs_per_s" in r:
        return GPU_USD_PER_HOUR / 3600 / r["throughput_docs_per_s"]
    return GPU_USD_PER_HOUR / 3600 * r["latency_avg_s"]


def table(title: str, rows: list[tuple[str, list]], extra_cols: list[str], fmt) -> None:
    print(f"\n### {title}\n")
    print("| Method | " + " | ".join(SHORT[d] for d in DATASETS) + " | " + " | ".join(extra_cols) + " |")
    print("|---|" + "---|" * (len(DATASETS) + len(extra_cols)))
    for name, vals in rows:
        print(f"| {name} | " + " | ".join(fmt(v) for v in vals) + " |")


def main() -> None:
    acc = {k: load(*a) for k, _, a, _ in METHODS}
    speed = {k: load(*s) for k, _, _, s in METHODS}
    names = {k: n for k, n, _, _ in METHODS}
    english = DATASETS[4:]

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    for metric, label in (("strict", "Strict entity F1 (%) — standard metric"), ("relaxed", "Relaxed F1 (%) — overlap + same type")):
        rows = []
        for k, *_ in METHODS:
            vals = [acc[k][d][metric][2] if d in acc[k] else None for d in DATASETS]
            full = all(v is not None for v in vals)
            en = [acc[k][d][metric][2] if d in acc[k] else None for d in english]
            rows.append((names[k], vals + [mean(vals) if full else None, mean(en) if all(v is not None for v in en) else None]))
        table(label, rows, ["Avg 12", "Avg 8 EN"], pct)

    for idx, label in ((0, "Precision (%)"), (1, "Recall (%)")):
        rows = [(names[k], [acc[k][d]["strict"][idx] if d in acc[k] else None for d in DATASETS]) for k, *_ in METHODS]
        table(f"Strict {label}", rows, [], pct)

    rows = []
    for k, *_ in METHODS:
        vals = [speed[k][d]["latency_avg_s"] if d in speed[k] else None for d in DATASETS]
        rows.append((names[k], vals + [mean(vals)]))
    table("Latency per document (seconds, one document at a time)", rows, ["Mean"], lambda v: "–" if v is None else f"{v:.3f}")

    rows = []
    for k, *_ in METHODS:
        vals = [per_doc_cost(k, speed[k][d]) * 1000 if d in speed[k] else None for d in DATASETS]
        rows.append((names[k], vals + [mean(vals)]))
    table("Cost per 1,000 documents (USD)", rows, ["Mean"], lambda v: "–" if v is None else (f"{v:.4f}" if v < 0.1 else f"{v:.3f}"))

    print("\n### Resources and prerequisites\n")
    print("| Method | Parameters | Disk | Peak GPU memory | Runs on | What you provide per task |")
    print("|---|---|---|---|---|---|")
    for k, *_ in METHODS:
        print(f"| {names[k]} | " + " | ".join(RESOURCES[k]) + " |")

    print("\n### Measurement notes\n")
    print("- Accuracy: 200 test sentences per dataset (fixed seed), CLUENER dev as test; same sentences for every method.")
    print("- Jev latency / cost: 30 test sentences per dataset, no cache, one document at a time.")
    print("- Hosted LLMs (DashScope): same prompt and type descriptions as Jev, JSON output, thinking disabled where the model allows it; latency per request at 8 concurrent requests ; cost from returned token counts at Beijing list price.")
    print("- Local LLMs (vLLM on RTX 3090, JSON-constrained decoding, temperature 0): latency = one request at a time; cost from batched throughput at the rental price.")
    print(f"- Local encoders: batch size 1 on RTX 3090; cost = latency × ${GPU_USD_PER_HOUR}/h (an upper bound; batching is cheaper).")


if __name__ == "__main__":
    main()
