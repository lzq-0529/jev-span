"""Dataset loading and scoring shared by the local baselines (no ML framework imports)."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
ZH = {"msra", "resume", "cluener", "weibo"}
ALL = [
    "msra", "resume", "cluener", "weibo", "conll", "wnut", "mitres",
    "crossner_ai", "crossner_literature", "crossner_music", "crossner_politics", "crossner_science",
]


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


