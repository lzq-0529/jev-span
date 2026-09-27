"""Command line: `jevspan "text"`, `jevspan -f file.txt`, or pipe text via stdin."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from dotenv import find_dotenv, load_dotenv

from .jev_client import JevClient
from .recognizer import Recognizer, TraceNode
from .schema import DEFAULT_SCHEMA, Schema


def _print_trace(node: TraceNode, depth: int = 0) -> None:
    probs = " ".join(f"{k}={v:.2f}" for k, v in sorted(node.probabilities.items(), key=lambda x: -x[1])[:3])
    head = f"{'  ' * depth}[{node.level}] {node.text!r} -> {node.label or '-'} {node.score:.2f} ({node.decision})"
    print(head + (f"  {probs}" if probs else ""))
    for child in node.children:
        _print_trace(child, depth + 1)


async def _run(args: argparse.Namespace, text: str) -> int:
    async with JevClient(model=args.model, cache_path=None if args.no_cache else args.cache) as client:
        schema = Schema.load(args.schema) if args.schema else DEFAULT_SCHEMA
        recognizer = Recognizer.from_preset(
            client,
            args.preset,
            schema=schema,
            use_context=not args.no_context,
            ngram=not args.no_window,
            propagate=not args.no_propagate,
            min_score=args.min_score,
        )
        result = await recognizer.recognize(text)
        if args.json:
            payload = result.as_dict()
            payload["usage"] = client.usage.as_dict()
            if not args.trace:
                payload.pop("trace")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.trace:
            for node in result.trace:
                _print_trace(node)
            print()
        if not result.entities:
            print(f"没有识别到{schema.titles}。")
        for e in result.entities:
            print(f"{schema.get(e.label).title}\t{e.text}\t[{e.start},{e.end})\t{e.score:.2f}\t{e.source}")
        u = client.usage
        print(
            f"\n请求 {u.requests} 次，问题 {u.questions} 个，缓存命中 {u.cache_hits}，"
            f"输入 {u.input_tokens} tokens，约 ${u.cost_usd:.6f}",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(find_dotenv(usecwd=True))
    p = argparse.ArgumentParser(prog="jevspan", description="用 Jev 做实体识别（默认人名/机构/地址，可用 --schema 零样本自定义）")
    p.add_argument("text", nargs="?", help="要识别的文本；省略时读 -f 或 stdin")
    p.add_argument("-f", "--file", help="从文件读取文本")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--trace", action="store_true", help="打印逐层切分与打分过程")
    p.add_argument("--model", default=None, help="Jev 模型，默认 jev-latest")
    p.add_argument("--no-context", action="store_true", help="不把所在句子作为上下文发给 Jev")
    p.add_argument("--no-window", action="store_true", help="标点切不开时不做滑动窗口细分")
    p.add_argument("--schema", help="零样本实体类型定义 JSON，见 eval/schemas/*.json")
    p.add_argument("--preset", choices=["accurate", "balanced", "legacy"], default="accurate", help="accurate（默认）召回更高；balanced 便宜约 25%%")
    p.add_argument("--no-propagate", action="store_true", help="不做全文一致性补全")
    p.add_argument("--min-score", type=float, default=0.0, help="只输出最高分不低于该值的实体")
    p.add_argument("--no-cache", action="store_true", help="不使用本地缓存")
    p.add_argument("--cache", default=".cache/jev.sqlite", help="缓存路径")
    args = p.parse_args(argv)

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()
    if not text.strip():
        p.error("没有输入文本")
    return asyncio.run(_run(args, text))


if __name__ == "__main__":
    raise SystemExit(main())
