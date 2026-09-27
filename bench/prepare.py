"""Convert public NER datasets into eval jsonl (explicit offsets) and draw fixed dev / test samples.

    bench/download.sh && uv run python bench/prepare.py

Writes bench/sets/<name>_dev.jsonl (algorithm tuning only) and bench/sets/<name>_test.jsonl (final
comparison only), sampled with a fixed seed from disjoint source splits where the dataset has them.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
SETS = HERE / "sets"
MAX_CHARS = 510  # BERT-style baselines cannot read longer inputs

MSRA = ["O", "B-LOC", "I-LOC", "B-ORG", "I-ORG", "B-PER", "I-PER"]
RESUME = [
    "O", "B-CONT", "I-CONT", "B-EDU", "I-EDU", "B-LOC", "I-LOC", "B-NAME", "I-NAME",
    "B-ORG", "I-ORG", "B-PRO", "I-PRO", "B-RACE", "I-RACE", "B-TITLE", "I-TITLE",
]
WEIBO = [
    "O", "B-GPE.NAM", "I-GPE.NAM", "B-GPE.NOM", "I-GPE.NOM", "B-LOC.NAM", "I-LOC.NAM", "B-LOC.NOM", "I-LOC.NOM",
    "B-ORG.NAM", "I-ORG.NAM", "B-ORG.NOM", "I-ORG.NOM", "B-PER.NAM", "I-PER.NAM", "B-PER.NOM", "I-PER.NOM",
]
CONLL = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"]
CROSSNER_TYPES = (
    "academicjournal album algorithm astronomicalobject award band book chemicalcompound chemicalelement "
    "conference country discipline election enzyme event field literarygenre location magazine metrics misc "
    "musicalartist musicalinstrument musicgenre organisation person poem politicalparty politician product "
    "programlang protein researcher scientist song task theory university writer"
).split()
CROSSNER = ["O"] + [f"{p}-{t}" for t in CROSSNER_TYPES for p in ("B", "I")]
CROSSNER_DOMAINS = ("ai", "literature", "music", "politics", "science")


def bio_to_item(idx: str, tokens: list[str], tags: list[str], sep: str) -> dict:
    text, offsets = "", []
    for i, tok in enumerate(tokens):
        if i and sep:
            text += sep
        offsets.append((len(text), len(text) + len(tok)))
        text += tok
    entities, cur = [], None
    for (s, e), tag in zip(offsets, tags):
        if tag.startswith("B-") or (tag.startswith("I-") and (cur is None or cur[0] != tag[2:])):
            if cur:
                entities.append(cur)
            cur = [tag[2:], s, e]
        elif tag.startswith("I-"):
            cur[2] = e
        else:
            if cur:
                entities.append(cur)
            cur = None
    if cur:
        entities.append(cur)
    return {"id": idx, "text": text, "entities": [[text[s:e], _label(lab), s, e] for lab, s, e in entities]}


def _label(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


def from_parquet(name: str, path: Path, names: list[str], sep: str) -> list[dict]:
    df = pd.read_parquet(path)
    return [
        bio_to_item(f"{name}-{i}", list(r.tokens), [names[t] for t in r.ner_tags], sep)
        for i, r in enumerate(df.itertuples())
    ]


def from_tner(name: str, path: Path, label_path: Path) -> list[dict]:
    id2label = {v: k for k, v in json.loads(label_path.read_text()).items()}
    items = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            row = json.loads(line)
            items.append(bio_to_item(f"{name}-{i}", row["tokens"], [id2label[t] for t in row["tags"]], " "))
    return items


def from_cluener(name: str, path: Path) -> list[dict]:
    df = pd.read_parquet(path)
    items = []
    for i, row in enumerate(df.itertuples()):
        ents = [[e["entity"], _label(e["label"]), int(e["start_offset"]), int(e["end_offset"])] for e in row.entities]
        for text, _, s, e in ents:
            assert row.text[s:e] == text
        items.append({"id": f"{name}-{i}", "text": row.text, "entities": ents})
    return items


def sources() -> dict[str, tuple]:
    """name -> (loader for the dev pool, loader for the test pool)."""
    out = {
        "msra": (lambda: from_parquet("msra_dev", DATA / "msra_train.parquet", MSRA, ""),
                 lambda: from_parquet("msra", DATA / "msra_test.parquet", MSRA, "")),
        "resume": (lambda: from_parquet("resume_dev", DATA / "resume_dev.parquet", RESUME, ""),
                   lambda: from_parquet("resume", DATA / "resume_test.parquet", RESUME, "")),
        "cluener": (lambda: from_cluener("cluener_dev", DATA / "cluener_train.parquet"),
                    lambda: from_cluener("cluener", DATA / "cluener_dev.parquet")),
        "weibo": (lambda: from_parquet("weibo_dev", DATA / "weibo_dev.parquet", WEIBO, ""),
                  lambda: from_parquet("weibo", DATA / "weibo_test.parquet", WEIBO, "")),
        "conll": (lambda: from_parquet("conll_dev", DATA / "conll_dev.parquet", CONLL, " "),
                  lambda: from_parquet("conll", DATA / "conll_test.parquet", CONLL, " ")),
        "wnut": (lambda: from_tner("wnut_dev", DATA / "wnut_valid.json", DATA / "wnut_label.json"),
                 lambda: from_tner("wnut", DATA / "wnut_test.json", DATA / "wnut_label.json")),
        "mitres": (lambda: from_tner("mitres_dev", DATA / "mitres_valid.json", DATA / "mitres_label.json"),
                   lambda: from_tner("mitres", DATA / "mitres_test.json", DATA / "mitres_label.json")),
    }
    for dom in CROSSNER_DOMAINS:
        out[f"crossner_{dom}"] = (
            lambda d=dom: from_parquet(f"crossner_{d}_dev", DATA / f"crossner_{d}_validation.parquet", CROSSNER, " "),
            lambda d=dom: from_parquet(f"crossner_{d}", DATA / f"crossner_{d}_test.parquet", CROSSNER, " "),
        )
    return out


def clean(items: list[dict]) -> list[dict]:
    return [it for it in items if it["text"].strip() and it["text"] != "-DOCSTART-" and len(it["text"]) <= MAX_CHARS]


def write(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=int, default=50)
    ap.add_argument("--test", type=int, default=200)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    SETS.mkdir(exist_ok=True)
    for name, (dev_pool, test_pool) in sources().items():
        if args.only and name not in args.only:
            continue
        test_items = clean(test_pool())
        dev_items = clean(dev_pool())
        test = random.Random(args.seed).sample(test_items, min(args.test, len(test_items)))
        dev = random.Random(args.seed + 1).sample(dev_items, min(args.dev, len(dev_items)))
        write(SETS / f"{name}_test.jsonl", test)
        write(SETS / f"{name}_dev.jsonl", dev)
        labels = sorted({e[1] for it in test for e in it["entities"]})
        n_ent = sum(len(it["entities"]) for it in test)
        print(f"{name:20} test={len(test):3} ({n_ent:4} entities, {len(labels):2} types)  dev={len(dev):3}  types={labels}")


if __name__ == "__main__":
    main()
