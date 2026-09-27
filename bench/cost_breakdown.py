"""Where do tokens and round trips go? Routes every question kind to its own client and reports usage.

    uv run python bench/cost_breakdown.py --datasets conll cluener crossner_politics --limit 20 --opts '{...}'
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
from evaluate import load_dataset  # noqa: E402

from jev_ner import JevClient, Recognizer, Schema  # noqa: E402
from jev_ner.recognizer import NONE_OPTION  # noqa: E402

KINDS = ["classify", "nominate", "boundary", "retype", "whole/split", "other"]


def kind_of(instruction: str, criteria: dict) -> str:
    if NONE_OPTION in criteria:
        return "nominate"
    if instruction.startswith("上文中的片段") or instruction.startswith("片段「") and "整体属于" in instruction:
        return "classify"
    if "这一处" in instruction:
        return "boundary"
    if "最准确地属于" in instruction:
        return "retype"
    if "标点或空格" in instruction:
        return "whole/split"
    return "other"


class Router:
    def __init__(self):
        self.clients = {k: JevClient(cache_path=None) for k in KINDS}
        self.calls = {k: 0 for k in KINDS}

    async def choose_many(self, state, instructions, criteria):
        k = kind_of(instructions[0], criteria)
        self.calls[k] += 1
        return await self.clients[k].choose_many(state, instructions, criteria)


async def main() -> None:
    load_dotenv(HERE.parent / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="*", default=["conll", "cluener", "crossner_politics"])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--opts", default="{}")
    args = ap.parse_args()
    router = Router()
    opts = json.loads(args.opts)
    t0 = time.perf_counter()
    for name in args.datasets:
        items = load_dataset(HERE / "sets" / f"{name}_dev.jsonl")[: args.limit]
        rec = Recognizer(router, schema=Schema.load(HERE / "schemas" / f"{name}.json"), **opts)
        sem = asyncio.Semaphore(6)

        async def one(it):
            async with sem:
                await rec.recognize(it["text"])

        await asyncio.gather(*(one(it) for it in items))
    total = sum(c.usage.input_tokens for c in router.clients.values())
    print(f"wall {time.perf_counter() - t0:.1f}s  total tokens {total}  cost ${total * 0.042 / 1e6:.4f}")
    for k, c in router.clients.items():
        u = c.usage
        if u.questions:
            print(f"  {k:12} calls={router.calls[k]:5} requests={u.requests:5} questions={u.questions:6} "
                  f"tokens={u.input_tokens:8} ({u.input_tokens / total * 100:4.1f}%)  tokens/question={u.input_tokens / u.questions:6.0f}")
    for c in router.clients.values():
        await c.aclose()


if __name__ == "__main__":
    asyncio.run(main())
