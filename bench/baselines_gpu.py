"""Encoder baselines on the bench test sets: fine-tuned token classifiers, GLiNER family, NuNER-Zero.

Runs on a GPU box with torch + transformers + gliner + gliner2:
    python bench/baselines_gpu.py --methods all --out bench/results/gpu
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "src"))
from jev_ner.schema import Schema  # noqa: E402

ZH = {"msra", "resume", "cluener", "weibo"}
ALL = [
    "msra", "resume", "cluener", "weibo", "conll", "wnut", "mitres",
    "crossner_ai", "crossner_literature", "crossner_music", "crossner_politics", "crossner_science",
]
FINETUNED = {
    "msra": ("PassbyGrocer/bert-ner-msra", ["O", "B-LOC", "I-LOC", "B-ORG", "I-ORG", "B-PER", "I-PER"]),
    "resume": ("PassbyGrocer/hreb-resume", None),
    "cluener": ("uer/roberta-base-finetuned-cluener2020-chinese", None),
    "weibo": ("PassbyGrocer/bert-ner-weibo", None),
    "conll": ("dslim/bert-base-NER", None),
    "wnut": ("tner/roberta-large-wnut2017", None),
    "mitres": ("tner/roberta-large-mit-restaurant", None),
}


def label_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


def load_items(name: str) -> list[dict]:
    items = []
    for line in (HERE / "sets" / f"{name}_test.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            it = json.loads(line)
            it["gold"] = [(s, e, lab, t) for t, lab, s, e in it["entities"]]
            items.append(it)
    return items


def prf(tp: int, fp: int, fn: int) -> list[float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return [round(p, 4), round(r, 4), round(f, 4)]


def score(items: list[dict], preds: list[list[tuple]]) -> dict:
    out = {}
    for mode in ("strict", "relaxed"):
        tp = fp = fn = 0
        for it, pr in zip(items, preds):
            used = set()
            for g in it["gold"]:
                hit = next(
                    (i for i, p in enumerate(pr) if i not in used and p[2] == g[2] and (
                        (p[0], p[1]) == (g[0], g[1]) if mode == "strict" else (p[0] < g[1] and g[0] < p[1]))),
                    None,
                )
                if hit is None:
                    fn += 1
                else:
                    used.add(hit)
                    tp += 1
            fp += len(pr) - len(used)
        out[mode] = prf(tp, fp, fn)
    return out


def words_of(name: str, text: str) -> list[tuple[int, int]]:
    if name in ZH:
        return [(i, i + 1) for i in range(len(text))]
    out, pos = [], 0
    for tok in text.split(" "):
        out.append((pos, pos + len(tok)))
        pos += len(tok) + 1
    return out


def bio_decode(tags: list[str], words: list[tuple[int, int]], text: str) -> list[tuple]:
    spans, cur = [], None
    for (s, e), tag in zip(words, tags):
        kind, _, label = tag.partition("-")
        label = label_key(label)
        if kind in ("B", "S") or (kind in ("I", "E", "M") and (cur is None or cur[2] != label)):
            if cur:
                spans.append(cur)
            cur = [s, e, label]
            if kind == "S":
                spans.append(cur)
                cur = None
        elif kind in ("I", "E", "M"):
            cur[1] = e
        else:
            if cur:
                spans.append(cur)
            cur = None
    if cur:
        spans.append(cur)
    return [(s, e, lab, text[s:e]) for s, e, lab in spans]


def run_finetuned(name: str, items: list[dict], device: str):
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_id, override = FINETUNED[name]
    tok = AutoTokenizer.from_pretrained(model_id, add_prefix_space=name not in ZH) if "roberta" in model_id and name not in ZH else AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForTokenClassification.from_pretrained(model_id).to(device).eval()
    id2label = override or [model.config.id2label[i] for i in range(len(model.config.id2label))]

    def predict(text: str) -> list[tuple]:
        words = words_of(name, text)
        enc = tok([text[s:e] for s, e in words], is_split_into_words=True, return_tensors="pt", truncation=True, max_length=512)
        word_ids = enc.word_ids()
        with torch.no_grad():
            logits = model(**{k: v.to(device) for k, v in enc.items()}).logits[0]
        tags, seen = ["O"] * len(words), set()
        for pos, wid in enumerate(word_ids):
            if wid is not None and wid not in seen:
                seen.add(wid)
                tags[wid] = id2label[int(logits[pos].argmax())]
        return bio_decode(tags, words, text)

    return model_id, predict


def spaced(text: str) -> tuple[str, list[int]]:
    """Chinese for whitespace-tokenising models: one char per word, with a map back to original offsets."""
    out, starts = [], []
    pos = 0
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        if out:
            pos += 1
        starts.append((pos, i))
        out.append(ch)
        pos += 1
    return " ".join(out), starts


def back(starts: list[tuple[int, int]], s: int, e: int) -> tuple[int, int] | None:
    begin = next((orig for p, orig in starts if p == s), None)
    end = next((orig + 1 for p, orig in starts if p == e - 1), None)
    return (begin, end) if begin is not None and end is not None else None


def run_gliner(name: str, model_id: str, device: str):
    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_id).to(device)
    schema = Schema.load(HERE / "schemas" / f"{name}.json")
    lower = "NuNER" in model_id
    title2key = {(t.title.lower() if lower else t.title): t.name for t in schema.types}
    labels = list(title2key)

    merge = "NuNER" in model_id

    def predict(text: str) -> list[tuple]:
        src, starts = (spaced(text) if name in ZH else (text, None))
        ents = model.predict_entities(src, labels, threshold=0.5)
        if merge:
            # NuNER-Zero predicts word-level pieces; its model card merges adjacent same-label spans.
            ents = sorted(ents, key=lambda e: e["start"])
            joined: list[dict] = []
            for e in ents:
                if joined and joined[-1]["label"] == e["label"] and src[joined[-1]["end"] : e["start"]].strip() == "":
                    joined[-1] = {**joined[-1], "end": e["end"]}
                else:
                    joined.append(dict(e))
            ents = joined
        out = []
        for e in ents:
            s, t = e["start"], e["end"]
            if starts is not None:
                mapped = back(starts, s, t)
                if not mapped:
                    continue
                s, t = mapped
            out.append((s, t, title2key[e["label"]], text[s:t]))
        return out

    return model_id, predict


def run_gliner2(name: str, device: str):
    from gliner2 import AutoExtractor

    model = AutoExtractor.from_pretrained("fastino/gliner2.5-multi-v1", map_location=device)
    model.set_word_splitter("char" if name in ZH else "whitespace")
    schema = Schema.load(HERE / "schemas" / f"{name}.json")
    labels = {t.name: t.criterion() for t in schema.types}

    def predict(text: str) -> list[tuple]:
        r = model.extract_entities(text, labels, include_confidence=True, include_spans=True)
        return [(e["start"], e["end"], lab, e["text"]) for lab, es in r["entities"].items() for e in es]

    return "fastino/gliner2.5-multi-v1", predict


def evaluate(method: str, name: str, device: str) -> dict | None:
    items = load_items(name)
    if method == "finetuned":
        if name not in FINETUNED:
            return None
        model_id, predict = run_finetuned(name, items, device)
    elif method == "gliner_multi":
        model_id, predict = run_gliner(name, "urchade/gliner_multi-v2.1", device)
    elif method == "gliner_large":
        if name in ZH:
            return None
        model_id, predict = run_gliner(name, "urchade/gliner_large-v2.1", device)
    elif method == "nuner_zero":
        if name in ZH:
            return None
        model_id, predict = run_gliner(name, "numind/NuNER_Zero", device)
    elif method == "gliner2.5":
        model_id, predict = run_gliner2(name, device)
    else:
        raise ValueError(method)
    predict(items[0]["text"])  # warm-up
    if device == "cuda":
        torch.cuda.synchronize()
    lat, preds = [], []
    for it in items:
        t = time.perf_counter()
        preds.append(predict(it["text"]))
        if device == "cuda":
            torch.cuda.synchronize()
        lat.append(time.perf_counter() - t)
    lat.sort()
    return {
        "method": method, "model": model_id, "dataset": name, "n": len(items), **score(items, preds),
        "latency_avg_s": round(sum(lat) / len(lat), 4), "latency_p90_s": round(lat[int(0.9 * (len(lat) - 1))], 4),
        "device": torch.cuda.get_device_name() if device == "cuda" else "cpu",
        "predictions": [[list(p) for p in pr] for pr in preds],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="*", default=["finetuned", "gliner_multi", "gliner_large", "nuner_zero", "gliner2.5"])
    ap.add_argument("--datasets", nargs="*", default=ALL)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default=str(HERE / "results" / "gpu"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for method in args.methods:
        for name in args.datasets:
            try:
                r = evaluate(method, name, args.device)
            except Exception as exc:  # keep the sweep going; the failure is recorded
                print(f"{method:12} {name:20} FAILED {type(exc).__name__}: {exc}", flush=True)
                continue
            if r is None:
                continue
            (out / f"{method}__{name}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
            print(f"{method:12} {name:20} strict F1 {r['strict'][2]:.3f}  relaxed {r['relaxed'][2]:.3f}  {r['latency_avg_s']*1000:.1f} ms/doc", flush=True)
            torch.cuda.empty_cache() if args.device == "cuda" else None


if __name__ == "__main__":
    main()
