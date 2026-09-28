"""Coarse-to-fine entity recognition driven entirely by Jev's highest-probability label.

1. Traverse the text and cut it into sentences (hard punctuation).
2. Ask Jev, for every segment, which label fits it as a whole:
   one of the schema's entity types, `none`, `mixed` ("contains an entity but
   also other words") or `partial` ("a truncated piece of an entity").
3. entity wins -> keep it (if it still contains delimiters, Jev first decides
   whether they belong to the name). `none` wins -> drop it. `mixed` wins ->
   cut at the next, weaker delimiter level and ask again for each piece.
4. A `mixed` segment no delimiter can cut is refined over its character/word
   windows, either
   - "choice" (default): all windows become the options of one multiple-choice
     question per entity type ("which option is exactly one complete X?"), the
     few nominated windows are verified with the per-segment question, and the
     type is asked again without them until it nominates nothing new. The
     verification of one round shares a round trip with the next nomination; or
   - "scan": every window is asked the per-segment question on its own.
5. Every recognised surface form is looked up in the rest of the document and
   each further occurrence is verified in its own sentence (propagation).

Speculative prefetch asks each segment's children (and an atomic segment's first
nomination) in the same round as the segment itself, trading a few questions for
fewer sequential round trips.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field, replace
from typing import Literal, Protocol

from .schema import DEFAULT_SCHEMA, DEFAULT_SCHEMAS, EntityType, Schema
from .segmenter import (
    LEVEL_CLAUSE,
    LEVEL_NAMES,
    split,
    Segment,
    can_bound_window,
    is_cjk,
    is_meaningful,
    split_finer,
    split_sentences,
    units,
)

NONE = "none"
MIXED = "mixed"
PARTIAL = "partial"
NONE_OPTION = "NONE"

DEFAULT_NONE_DESC = (
    "都不是：普通词语或句子、时间日期、数字金额、电话、邮箱、网址、单独的职位或称谓、产品名等，其中完全不含{titles}"
)
GENERIC_NONE_DESC = "都不是：只是普通词语、描述或句子，或者只是年份日期、数量、代词，其中完全不含任何{titles}"
MIXED_DESC = (
    "包含实体的短语：片段里含有{titles}，但整体还带有动词、介词、职位、修饰语等其他词，"
    "不是一个完整单一的实体，例如在「{example}」前后多了其他词语"
)
DEFAULT_MIXED_DESC = (
    "包含实体的短语：片段里含有人名/机构/地址，但整体还带有动词、介词、职位、修饰语等其他词，"
    "不是一个完整单一的实体，例如 '马云创办了阿里巴巴'、'就职于华为公司'、'前往杭州'、'在招商银行当柜员'"
)
DEFAULT_PARTIAL_DESC = "残缺实体：只是某个实体被截断的一部分，例如 '京大学'、'张伟教'、'海淀区中关'、'腾讯计算机系统有'"
PARTIAL_DESC = "残缺实体：只是某个实体被截断的一部分，例如把「{example}」截掉了开头或结尾的几个字"

WHOLE = "whole"
SPLIT = "split"
BOUNDARY_INSTRUCTION = "片段「{frag}」里的标点或空格，是这个名称本身的一部分，还是把不同的内容分隔开了？"
BOUNDARY_CRITERIA = {
    WHOLE: "整体是一个完整的名称，标点或空格属于名称本身，例如 '阿里巴巴（中国）有限公司'、'Austin, Texas'、'广东省 深圳市'",
    SPLIT: "标点或空格分开了不同的内容，例如前面是字段名、称呼或说明文字，后面才是实体，如 '地址：杭州市'、'张三 电话'",
}

SEGMENT_INSTRUCTION = "上文中的片段「{frag}」整体属于哪一类？只看这个片段本身，判断它是否恰好是一个完整的实体。"
NO_CONTEXT_INSTRUCTION = "片段「{frag}」整体属于哪一类？判断它是否恰好是一个完整的实体。"
# Re-asks differ only in trailing whitespace: reworded questions shift the answer
# (a bias), while these resample the same question (variance only).
VOTE_SUFFIXES = (" ", "\n", "  ")
NOMINATE_INSTRUCTION = (
    "在上文的片段「{seg}」中，哪个选项恰好是一个完整的「{title}」？{criterion}。"
    "选项必须是完整的{title}本身，不能残缺，也不能多带其他词；如果没有这样的选项，选 NONE。"
)
NOMINATE_GROUP_INSTRUCTION = (
    "在上文的片段「{seg}」中，哪个选项恰好是一个完整的实体，并且属于下列类型之一？\n{criteria}\n"
    "选项必须是完整的实体本身，不能残缺，也不能多带其他词；如果没有这样的选项，选 NONE。"
)
BOUNDARY_REFINE_INSTRUCTION = (
    "上文中「{orig}」这一处，哪个选项恰好是一个完整的「{title}」？{criterion}。"
    "边界以这个类型的定义和例子为准：通常不多带前后的连词、介词、代词、冠词、量词或修饰语，也不能截断；"
    "只有名称本身、或这个类型的定义和例子包含这些词时才保留。"
)
RETYPE_INSTRUCTION = "上文中的「{span}」最准确地属于哪一类？有更具体的类型时选更具体的。"
MAX_OPTIONS = 254
MAX_OPTION_QUESTIONS = 1000


class ChoiceBackend(Protocol):
    async def choose_many(
        self, state: str, instructions: list[str], criteria: dict[str, str | None]
    ) -> list[dict[str, float]]: ...


@dataclass
class Entity:
    text: str
    label: str
    start: int
    end: int
    score: float
    source: str
    type_probs: dict[str, float] = field(default_factory=dict, repr=False, compare=False)


@dataclass
class TraceNode:
    text: str
    start: int
    end: int
    level: str
    label: str = ""
    score: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    decision: str = ""
    children: list["TraceNode"] = field(default_factory=list)


@dataclass
class Result:
    text: str
    entities: list[Entity]
    trace: list[TraceNode]

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "entities": [{k: v for k, v in asdict(e).items() if k != "type_probs"} for e in self.entities],
            "trace": [asdict(t) for t in self.trace],
        }


def argmax(probs: dict[str, float]) -> tuple[str, float]:
    label = max(probs, key=lambda k: probs[k])
    return label, probs[label]


_EN_FUNCTION = {
    "and", "or", "but", "nor", "is", "was", "were", "are", "be", "been", "being", "has", "have", "had", "that",
    "which", "who", "whom", "whose", "this", "these", "those", "its", "their", "his", "her", "our", "your", "my",
    "it", "he", "she", "they", "we", "you", "than", "then", "also", "not", "including", "such", "while", "when",
}
_EN_PREPOSITIONS = {"of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "into", "onto"}
# Some schemas put prepositions inside entities ("in town", "near me"), so only ends reject them.
START_STOP = {"zh": set("的了是与及把被着过吗呢吧啊也都就还这我你他她它个或而但为等"), "en": _EN_FUNCTION}
END_STOP = {
    "zh": set("的了在是与及把被着过吗呢吧啊也都就还这那我你他她它或而但对为从向于"),
    "en": _EN_FUNCTION | _EN_PREPOSITIONS | {"the", "a", "an"},
}


def _bad_edge(unit: str, stop: dict[str, set[str]]) -> bool:
    """A window never starts / ends on a function word (entities may contain them inside)."""
    if len(unit) == 1 and is_cjk(unit):
        return unit in stop["zh"]
    return unit.lower() in stop["en"]


def _margin(probs: dict[str, float]) -> float:
    top = sorted(probs.values(), reverse=True)
    return top[0] - (top[1] if len(top) > 1 else 0.0)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


async def _no_answers() -> list[dict[str, float]]:
    return []


async def _no_nominations() -> dict[str, dict[str, float]]:
    return {}


@dataclass(eq=False)
class _Item:
    seg: Segment
    node: TraceNode
    verify: "_Item | None" = None
    boundary: dict[str, float] = field(default_factory=dict)


@dataclass
class _SentenceRun:
    text: str
    entities: list[Entity] = field(default_factory=list)
    leaves: list[_Item] = field(default_factory=list)
    next_frontier: list[_Item] = field(default_factory=list)
    pending_verify: list[_Item] = field(default_factory=list)
    memo: dict[str, dict[str, float]] = field(default_factory=dict)
    polished: set[int] = field(default_factory=set)
    nominations: dict[tuple[int, int], asyncio.Future] = field(default_factory=dict)


PRESETS: dict[str, dict] = {
    # One nomination question per 4 types (the default): finds low-salience entities such as genres and adjectives.
    "accurate": {},
    # All types share one nomination question: about 25% cheaper, slightly lower recall.
    "balanced": {"nominate_group_size": 0},
    # The original hierarchical pipeline (per-segment classification, per-type nomination).
    "legacy": {
        "hierarchy": True, "prune_windows": False, "boundary_refine": False, "retype": False,
        "nominate_group_size": 1, "nominate_min": 0.05, "nominate_top_group": 8, "max_rounds": 4, "stop_none": 1.01,
    },
}


class Recognizer:
    @classmethod
    def from_preset(cls, backend: "ChoiceBackend", preset: str = "accurate", **overrides) -> "Recognizer":
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
        return cls(backend, **{**PRESETS[preset], **overrides})

    def __init__(
        self,
        backend: ChoiceBackend,
        *,
        schema: Schema | None = None,
        entity_types: dict[str, str] | None = None,
        use_context: bool = True,
        ngram: bool = True,
        refine: Literal["choice", "scan"] = "choice",
        propagate: bool = True,
        speculative: bool = True,
        boundary_refine: bool = True,
        retype: bool = True,
        retype_weight: float = 0.7,
        strip_articles: bool = True,
        nominate_group_size: int | None = 4,
        nominate_top_group: int = 5,
        speculative_nominate: bool = True,
        prune_windows: bool = True,
        latin_window: int = 12,
        hierarchy: bool = False,
        compact_criteria: bool = False,
        vote_margin: float = 0.2,
        vote_variants: int = 0,
        min_score: float = 0.0,
        ngram_window: int = 32,
        ngram_max_units: int = 64,
        ngram_min_score: float = 0.5,
        contain_margin: float = 0.15,
        explore_threshold: float = 0.25,
        nominate_top: int = 3,
        nominate_min: float = 0.1,
        max_rounds: int = 2,
        stop_none: float = 0.3,
        max_state_chars: int = 4000,
    ):
        if schema is None:
            schema = Schema.from_dict(entity_types) if entity_types else DEFAULT_SCHEMA
        self.schema = schema
        self.entity_types = schema.names
        self.backend = backend
        self.use_context = use_context
        self.ngram = ngram
        self.refine = refine
        self.propagate = propagate
        self.speculative = speculative
        self.boundary_refine = boundary_refine
        self.retype = retype
        self.retype_weight = retype_weight
        self.strip_articles = strip_articles
        self.nominate_top_group = nominate_top_group
        self.speculative_nominate = speculative_nominate
        self.prune_windows = prune_windows
        self.latin_window = latin_window
        self.hierarchy = hierarchy
        self.compact_criteria = compact_criteria
        types = list(schema.types)
        size = nominate_group_size or len(types)
        self.groups: list[tuple[EntityType, ...]] = [tuple(types[i : i + size]) for i in range(0, len(types), size)]
        self.vote_margin = vote_margin
        self.vote_variants = vote_variants
        self.min_score = min_score
        self.ngram_window = ngram_window
        self.ngram_max_units = ngram_max_units
        self.ngram_min_score = ngram_min_score
        self.contain_margin = contain_margin
        self.explore_threshold = explore_threshold
        self.nominate_top = nominate_top
        self.nominate_min = nominate_min
        self.max_rounds = max_rounds
        self.stop_none = stop_none
        self.max_state_chars = max_state_chars
        self.segment_criteria = self._segment_criteria()
        self.single_char_ok = any(t.min_chars <= 1 for t in schema.types)

    def _segment_criteria(self) -> dict[str, str]:
        titles = "/".join(t.title for t in self.schema.types)
        example = next((t.examples[0] for t in self.schema.types if t.examples), self.schema.types[0].title)
        if any(self.schema is s for s in DEFAULT_SCHEMAS.values()):
            none_desc = DEFAULT_NONE_DESC.format(titles=titles)
            mixed_desc = DEFAULT_MIXED_DESC
            partial_desc = DEFAULT_PARTIAL_DESC
        else:
            none_desc = GENERIC_NONE_DESC.format(titles=titles)
            mixed_desc = MIXED_DESC.format(titles=titles, example=example)
            partial_desc = PARTIAL_DESC.format(example=example)
        types = {t.name: t.criterion(compact=self.compact_criteria) for t in self.schema.types}
        return {**types, NONE: none_desc, MIXED: mixed_desc, PARTIAL: partial_desc}

    def _types_of(self, probs: dict[str, float]) -> dict[str, float]:
        return {k: probs[k] for k in self.entity_types if k in probs}

    def _instruction(self, frag: str) -> str:
        template = SEGMENT_INSTRUCTION if self.use_context else NO_CONTEXT_INSTRUCTION
        return template.format(frag=frag)

    def _state(self, sentence: Segment) -> str:
        return sentence.text[: self.max_state_chars] if self.use_context else ""

    async def _classify(self, state: str, frags: list[str]) -> list[dict[str, float]]:
        """Per-segment question; close calls are re-asked in other wordings and averaged.

        Jev's answers vary slightly between calls, so a near-tie can flip either way.
        """
        if not frags:
            return []
        probs_list = await self.backend.choose_many(
            state, [self._instruction(f) for f in frags], self.segment_criteria
        )
        k = min(self.vote_variants, len(VOTE_SUFFIXES))
        if k <= 0:
            return probs_list
        close = [i for i, p in enumerate(probs_list) if _margin(p) < self.vote_margin]
        if not close:
            return probs_list
        extra = await self.backend.choose_many(
            state,
            [self._instruction(frags[i]) + suffix for i in close for suffix in VOTE_SUFFIXES[:k]],
            self.segment_criteria,
        )
        probs_list = list(probs_list)
        for n, i in enumerate(close):
            samples = [probs_list[i], *extra[n * k : (n + 1) * k]]
            probs_list[i] = {key: sum(s[key] for s in samples) / len(samples) for key in self.segment_criteria}
        return probs_list

    async def recognize(self, text: str) -> Result:
        sentences = split_sentences(text)
        outputs = await asyncio.gather(*(self._sentence(text, s) for s in sentences))
        entities: list[Entity] = []
        trace: list[TraceNode] = []
        for ents, node in outputs:
            entities.extend(ents)
            trace.append(node)
        if self.propagate and entities:
            entities.extend(await self._propagate(text, sentences, entities, trace))
        strip = self.strip_articles and not self.boundary_refine
        entities = [
            self._with_brackets(text, strip_article(text, e) if strip else e)
            for e in entities
            if e.score >= self.min_score and len(e.text) >= self.schema.get(e.label).min_chars
        ]
        entities.sort(key=lambda e: (e.start, -e.end))
        return Result(text=text, entities=merge_adjacent(text, entities), trace=trace)

    def _with_brackets(self, text: str, ent: Entity) -> Entity:
        """Labeling convention: some types (book / movie titles) include their 《》."""
        if (
            self.schema.get(ent.label).include_brackets
            and ent.start > 0
            and ent.end < len(text)
            and text[ent.start - 1] in "《〈" and text[ent.end] in "》〉"
        ):
            s, e = ent.start - 1, ent.end + 1
            return replace(ent, text=text[s:e], start=s, end=e)
        return ent

    async def _sentence(self, text: str, sentence: Segment) -> tuple[list[Entity], TraceNode]:
        state = self._state(sentence)
        root = TraceNode(sentence.text, sentence.start, sentence.end, LEVEL_NAMES[sentence.level])
        run = _SentenceRun(text=text)
        frontier: list[_Item] = [_Item(sentence, root)]
        if not self.hierarchy:
            # Flat mode: no per-segment classification; every clause goes straight to the window stage.
            parts = split(text, sentence.start, sentence.end, LEVEL_CLAUSE) or [sentence]
            for part in parts:
                child = TraceNode(part.text, part.start, part.end, LEVEL_NAMES[LEVEL_CLAUSE], decision="window")
                root.children.append(child)
                run.leaves.append(_Item(part, child))
            frontier = []

        while frontier:
            parents, run.pending_verify = run.pending_verify, []
            frags = self._round_fragments(text, state, frontier, run)
            probs_list, boundary_list = await asyncio.gather(
                self._classify(state, frags),
                self.backend.choose_many(
                    state, [BOUNDARY_INSTRUCTION.format(frag=p.seg.text) for p in parents], BOUNDARY_CRITERIA
                )
                if parents
                else _no_answers(),
            )
            run.memo.update(zip(frags, probs_list))
            for parent, boundary in zip(parents, boundary_list):
                parent.boundary = boundary
            groups: dict[int, list[_Item]] = {}
            for item in frontier:
                probs = run.memo[item.seg.text]
                item.node.label, item.node.score = argmax(probs)
                item.node.probabilities = probs
                if item.verify is None:
                    self._decide(item, run)
                else:
                    groups.setdefault(id(item.verify), []).append(item)
            for children in groups.values():
                self._settle_verification(children[0].verify, children, run)
            frontier, run.next_frontier = run.next_frontier, []

        if self.refine == "choice":
            window_results = await asyncio.gather(
                *(
                    self._refine_choice(
                        text, state, item.seg, item.node,
                        run.nominations.pop((item.seg.start, item.seg.end), None), sentence, run,
                    )
                    for item in run.leaves
                )
            )
        else:
            window_results = await asyncio.gather(
                *(self._refine_scan(text, state, item.seg, item.node) for item in run.leaves)
            )
        for ents in window_results:
            run.entities.extend(ents)
        if run.nominations:
            await asyncio.gather(*run.nominations.values())
        if (self.boundary_refine or self.retype) and run.entities:
            rest = [e for e in run.entities if id(e) not in run.polished]
            if rest:
                done = await self._polish_many(text, state, sentence, rest, run.entities, root)
                swap = {id(a): b for a, b in zip(rest, done)}
                run.entities = [swap.get(id(e), e) for e in run.entities]
            run.entities = resolve_overlaps(run.entities, 0.0)
        return run.entities, root

    def _boundary_variants(self, text: str, sentence: Segment, ent: Entity, taken: list[Entity]) -> dict[str, tuple[int, int]]:
        """The entity plus copies with 1-3 units trimmed or 1-2 units added at either end."""
        us = units(text, sentence.start, sentence.end)
        inside = [i for i, (s, e) in enumerate(us) if s >= ent.start and e <= ent.end]
        if not inside:
            return {}
        first, last = inside[0], inside[-1]
        variants: dict[str, tuple[int, int]] = {ent.text: (ent.start, ent.end)}
        edits = [(a, b) for a in range(0, 4) for b in range(0, 4) if 0 < a + b <= 3]
        edits += [(-a, 0) for a in (1, 2)] + [(0, -b) for b in (1, 2)]
        min_chars = self.schema.get(ent.label).min_chars
        for lead, trail in edits:
            i, j = first + lead, last - trail
            if i < 0 or j >= len(us) or i > j:
                continue
            s, e = us[i][0], us[j][1]
            frag = text[s:e]
            if not (can_bound_window(text[us[i][0] : us[i][1]]) and can_bound_window(text[us[j][0] : us[j][1]])):
                continue
            if len(frag) < min_chars or not is_meaningful(frag) or frag == NONE_OPTION:
                continue
            if (lead < 0 or trail < 0) and any(o is not ent and _overlaps(s, e, o.start, o.end) for o in taken):
                continue
            variants.setdefault(frag, (s, e))
        return variants

    async def _polish_many(
        self, text: str, state: str, sentence: Segment, ents: list[Entity], taken: list[Entity], node: TraceNode
    ) -> list[Entity]:
        """Jev re-decides the exact boundaries (and fused type) of `ents`; returns them in the same order."""
        if not ents:
            return []
        boundary_jobs: list[tuple[int, dict[str, tuple[int, int]]]] = []
        if self.boundary_refine:
            for idx, ent in enumerate(ents):
                variants = self._boundary_variants(text, sentence, ent, taken)
                if len(variants) > 1:
                    boundary_jobs.append((idx, variants))

        async def ask_boundary(idx: int, variants: dict[str, tuple[int, int]]) -> dict[str, float]:
            etype = self.schema.get(ents[idx].label)
            instruction = BOUNDARY_REFINE_INSTRUCTION.format(
                orig=ents[idx].text, title=etype.title, criterion=etype.criterion()
            )
            return (await self.backend.choose_many(state, [instruction], {k: None for k in variants}))[0]

        retype_call = (
            self.backend.choose_many(
                state, [RETYPE_INSTRUCTION.format(span=e.text) for e in ents], self.schema.criteria()
            )
            if self.retype
            else _no_answers()
        )
        type_probs, *boundary_probs = await asyncio.gather(
            retype_call, *(ask_boundary(idx, variants) for idx, variants in boundary_jobs)
        )
        polished = list(ents)
        if type_probs:
            for idx, probs in enumerate(type_probs):
                e = polished[idx]
                prior = e.type_probs or {e.label: 1.0}
                total = sum(prior.values()) or 1.0
                w = self.retype_weight
                fused = {k: w * probs.get(k, 0.0) + (1 - w) * prior.get(k, 0.0) / total for k in self.entity_types}
                label, _ = argmax(fused)
                polished[idx] = replace(e, label=label, type_probs=fused)
        for (idx, variants), probs in zip(boundary_jobs, boundary_probs):
            best, p = argmax(probs)
            e = polished[idx]
            if best != e.text:
                s, t = variants[best]
                node.children.append(
                    TraceNode(best, s, t, "boundary", e.label, p, dict(probs), f"refined from {e.text}")
                )
                polished[idx] = replace(e, text=best, start=s, end=t)
        return polished

    def _round_fragments(self, text: str, state: str, frontier: list[_Item], run: "_SentenceRun") -> list[str]:
        """Questions for this round, plus (speculatively) the next level down, asked in the same request.

        Most segments turn out `mixed`, so asking their children now saves one sequential
        round trip per level; atomic segments also get their first nomination round started.
        """
        wanted = [item.seg.text for item in frontier]
        if self.speculative:
            for item in frontier:
                finer = split_finer(text, item.seg)
                if finer:
                    wanted.extend(part.text for part in finer[1])
                elif self.ngram and self.refine == "choice" and self.speculative_nominate:
                    key = (item.seg.start, item.seg.end)
                    if key not in run.nominations and len(units(text, item.seg.start, item.seg.end)) >= 3:
                        options = self._window_options(text, item.seg)
                        if options:
                            run.nominations[key] = asyncio.ensure_future(
                                self._nominate(state, item.seg, list(self.groups), options)
                            )
        return [frag for frag in dict.fromkeys(wanted) if frag not in run.memo]

    def _decide(self, item: _Item, run: "_SentenceRun") -> None:
        """Act on Jev's top label for one segment."""
        seg, node = item.seg, item.node
        label, probs = node.label, node.probabilities
        if label in self.entity_types:
            finer = split_finer(run.text, seg)
            if finer:
                node.decision = "verify"
                run.pending_verify.append(item)
                self._push_children(item, finer, run, verify=item)
            else:
                node.decision = "entity"
                run.entities.append(Entity(seg.text, label, seg.start, seg.end, node.score, "segment", self._types_of(probs)))
        elif label == MIXED or probs.get(MIXED, 0.0) >= self.explore_threshold:
            finer = split_finer(run.text, seg)
            if finer:
                node.decision = f"split:{LEVEL_NAMES[finer[0]]}"
                self._push_children(item, finer, run)
            elif self.ngram:
                node.decision = "window"
                run.leaves.append(item)
            else:
                entity = self._fallback(seg, probs)
                node.decision = "fallback"
                if entity:
                    run.entities.append(entity)
        else:
            node.decision = "none"

    def _push_children(
        self, item: _Item, finer: tuple[int, list[Segment]], run: "_SentenceRun", verify: _Item | None = None
    ) -> None:
        level, parts = finer
        for part in parts:
            child = TraceNode(part.text, part.start, part.end, LEVEL_NAMES[level])
            item.node.children.append(child)
            run.next_frontier.append(_Item(part, child, verify))

    def _settle_verification(self, parent: _Item, children: list[_Item], run: "_SentenceRun") -> None:
        """An entity segment that still contains delimiters: Jev decides whether they belong to the name."""
        verdict, verdict_score = argmax(parent.boundary) if parent.boundary else (WHOLE, 1.0)
        parent.node.probabilities = {**parent.node.probabilities, **{f"boundary:{k}": v for k, v in parent.boundary.items()}}
        if verdict == WHOLE:
            parent.node.decision = f"entity (whole {verdict_score:.2f})"
            for c in children:
                c.node.decision = "part-of-parent"
            seg = parent.seg
            run.entities.append(
                Entity(seg.text, parent.node.label, seg.start, seg.end, parent.node.score, "segment", self._types_of(parent.node.probabilities))
            )
            return
        parent.node.decision = f"split:verified ({verdict_score:.2f})"
        for c in children:
            self._decide(_Item(c.seg, c.node), run)

    def _fallback(self, seg: Segment, probs: dict[str, float]) -> Entity | None:
        rest = {k: v for k, v in probs.items() if k not in (MIXED, PARTIAL)}
        if not rest:
            return None
        label, score = argmax(rest)
        if label in self.entity_types and score > rest.get(NONE, 0.0):
            return Entity(seg.text, label, seg.start, seg.end, score, "fallback")
        return None

    def window_spans(self, text: str, seg: Segment) -> list[tuple[int, int]]:
        us = units(text, seg.start, seg.end)
        n = len(us)
        if n > self.ngram_max_units:
            return []
        words = [text[s:e] for s, e in us]
        latin = [w[:1].isascii() and w[:1].isalnum() for w in words]
        spans: list[tuple[int, int]] = []
        for i in range(n):
            if self.prune_windows and _bad_edge(words[i], START_STOP):
                continue
            latin_count = 0
            for j in range(i + 1, min(n, i + self.ngram_window) + 1):
                latin_count += latin[j - 1]
                if self.prune_windows and latin_count > self.latin_window:
                    break
                if j - i == n and self.hierarchy:
                    continue
                if self.prune_windows and _bad_edge(words[j - 1], END_STOP):
                    continue
                s, e = us[i][0], us[j - 1][1]
                frag = text[s:e]
                if len(frag) == 1 and is_cjk(frag) and not self.single_char_ok:
                    continue
                if not can_bound_window(words[i]) or not can_bound_window(words[j - 1]):
                    continue
                if not is_meaningful(frag):
                    continue
                spans.append((s, e))
        return spans

    def _record_windows(self, node: TraceNode, candidates: list[Entity], chosen: list[Entity]) -> None:
        for cand in sorted(candidates, key=lambda c: -c.score)[:12]:
            node.children.append(
                TraceNode(
                    cand.text, cand.start, cand.end, "window", cand.label, cand.score,
                    decision="entity" if cand in chosen else "rejected",
                )
            )
        node.children.sort(key=lambda c: (c.start, -c.end))

    async def _refine_scan(self, text: str, state: str, seg: Segment, node: TraceNode) -> list[Entity]:
        spans = self.window_spans(text, seg)
        if not spans:
            entity = self._fallback(seg, node.probabilities)
            node.decision = "fallback"
            return [entity] if entity else []
        frags = [text[s:e] for s, e in spans]
        probs_list = await self.backend.choose_many(state, [self._instruction(f) for f in frags], self.segment_criteria)
        candidates: list[Entity] = []
        for (s, e), frag, probs in zip(spans, frags, probs_list):
            label, score = argmax(probs)
            if label in self.entity_types and score >= self.ngram_min_score:
                candidates.append(Entity(frag, label, s, e, score, "window", self._types_of(probs)))
        chosen = resolve_overlaps(candidates, self.contain_margin)
        self._record_windows(node, candidates, chosen)
        return chosen

    def _nominate_instruction(self, seg: Segment, group: tuple[EntityType, ...]) -> str:
        if len(group) == 1:
            etype = group[0]
            return NOMINATE_INSTRUCTION.format(seg=seg.text, title=etype.title, criterion=etype.criterion())
        lines = "\n".join(f"- {t.criterion()}" for t in group)
        return NOMINATE_GROUP_INSTRUCTION.format(seg=seg.text, criteria=lines)

    @staticmethod
    def _group_key(group: tuple[EntityType, ...]) -> str:
        return "|".join(t.name for t in group)

    async def _nominate(
        self, state: str, seg: Segment, groups: list[tuple[EntityType, ...]], options: dict[str, tuple[int, int]]
    ) -> dict[str, dict[str, float]]:
        """One multiple-choice question per type group over the window options (chunked to Jev's option limit)."""
        keys = list(options)
        chunks = [keys[i : i + MAX_OPTIONS] for i in range(0, len(keys), MAX_OPTIONS)]
        jobs: list[tuple[list[tuple[EntityType, ...]], list[str]]] = []
        for chunk in chunks:
            # Every question repeats its options, so cap option×question pairs per request.
            per_request = max(1, MAX_OPTION_QUESTIONS // (len(chunk) + 1))
            for i in range(0, len(groups), per_request):
                jobs.append((groups[i : i + per_request], chunk))
        answers = await asyncio.gather(
            *(
                self.backend.choose_many(
                    state,
                    [self._nominate_instruction(seg, g) for g in batch],
                    {**{k: None for k in chunk}, NONE_OPTION: None},
                )
                for batch, chunk in jobs
            )
        )
        merged: dict[str, dict[str, float]] = {self._group_key(g): {} for g in groups}
        for (batch, _), per_chunk in zip(jobs, answers):
            for group, probs in zip(batch, per_chunk):
                bucket = merged[self._group_key(group)]
                for k, v in probs.items():
                    bucket[k] = max(bucket.get(k, 0.0), v) if k == NONE_OPTION else v
        return merged

    def _window_options(self, text: str, seg: Segment) -> dict[str, tuple[int, int]]:
        options: dict[str, tuple[int, int]] = {}
        for s, e in self.window_spans(text, seg):
            frag = text[s:e]
            if frag != NONE_OPTION:
                options.setdefault(frag, (s, e))
        return options

    async def _refine_choice(
        self,
        text: str,
        state: str,
        seg: Segment,
        node: TraceNode,
        prefetched: asyncio.Future | None = None,
        sentence: Segment | None = None,
        run: "_SentenceRun | None" = None,
    ) -> list[Entity]:
        options = self._window_options(text, seg)
        options_all = dict(options)
        if not options:
            entity = self._fallback(seg, node.probabilities)
            node.decision = "fallback"
            return [entity] if entity else []

        verified: dict[str, tuple[str, float]] = {}
        accepted: list[Entity] = []
        chosen: list[Entity] = []
        pending: list[str] = []
        active = list(self.groups)
        # Entities verified in round r are polished together with round r+1's verification.
        early = (self.boundary_refine or self.retype) and sentence is not None and run is not None
        polished: dict[tuple[int, int, str], Entity] = {}
        to_polish: list[Entity] = []
        # Pipelined rounds: the picks of round r are verified in the same step as the
        # nomination of round r+1, so each extra round costs one round trip, not two.
        for round_no in range(self.max_rounds + 1):
            nominate = bool(active) and bool(options) and round_no < self.max_rounds
            if not nominate and not pending and not to_polish:
                break
            if nominate and round_no == 0 and prefetched is not None:
                nominate_call = prefetched
            elif nominate:
                nominate_call = self._nominate(state, seg, active, options)
            else:
                nominate_call = _no_nominations()
            verify_call = self._classify(state, pending)
            polish_call = (
                self._polish_many(text, state, sentence, to_polish, accepted, node) if to_polish else _no_answers()
            )
            nominations, verdicts, done = await asyncio.gather(nominate_call, verify_call, polish_call)
            for e, d in zip(to_polish, done):
                polished[(e.start, e.end, e.label)] = d
            to_polish = []
            for frag, probs in zip(pending, verdicts):
                label, score = argmax(probs)
                verified[frag] = (label, score)
                if label in self.entity_types:
                    s, e = options_all[frag]
                    accepted.append(Entity(frag, label, s, e, score, "window", self._types_of(probs)))
            pending = []
            chosen = resolve_overlaps(accepted, self.contain_margin)
            if early:
                to_polish = [c for c in chosen if (c.start, c.end, c.label) not in polished]
            if not nominations:
                continue
            confident: list[tuple[int, int]] = []
            still_active: list[tuple[EntityType, ...]] = []
            for group in active:
                probs = nominations[self._group_key(group)]
                top = self.nominate_top if len(group) == 1 else min(self.nominate_top_group, self.nominate_top + len(group))
                ranked = sorted(
                    ((k, v) for k, v in probs.items() if k != NONE_OPTION and k in options),
                    key=lambda kv: -kv[1],
                )
                picks = [(k, v) for k, v in ranked[:top] if v >= self.nominate_min]
                # A single-answer question concentrates probability on the most salient option,
                # so a type keeps being asked (without its picks) until it nominates nothing new.
                if picks and probs.get(NONE_OPTION, 0.0) < self.stop_none:
                    still_active.append(group)
                for k, v in picks:
                    if k not in pending:
                        pending.append(k)
                    if v >= 0.5:
                        confident.append(options[k])
            blocked = confident + [(c.start, c.end) for c in chosen]
            options = {
                k: (s, e)
                for k, (s, e) in options.items()
                if k not in pending and k not in verified and not any(_overlaps(s, e, bs, be) for bs, be in blocked)
            }
            active = still_active
        self._record_windows(node, accepted, chosen)
        if early:
            chosen = [polished.get((c.start, c.end, c.label), c) for c in chosen]
            for c in chosen:
                if (c.start, c.end, c.label) in polished or c in polished.values():
                    run.polished.add(id(c))
        return chosen

    async def _propagate(
        self, text: str, sentences: list[Segment], entities: list[Entity], trace: list[TraceNode]
    ) -> list[Entity]:
        """Verify further occurrences of every recognised surface form, each in its own sentence."""
        taken = [(e.start, e.end) for e in entities]
        by_surface: dict[str, str] = {}
        for e in entities:
            if len(e.text) >= 2:
                by_surface.setdefault(e.text, e.label)
        jobs: dict[int, list[tuple[int, int, str]]] = {}
        for surface, label in by_surface.items():
            start = text.find(surface)
            while start >= 0:
                end = start + len(surface)
                if not any(_overlaps(start, end, s, e) for s, e in taken):
                    for idx, sent in enumerate(sentences):
                        if sent.start <= start and end <= sent.end:
                            jobs.setdefault(idx, []).append((start, end, label))
                            taken.append((start, end))
                            break
                start = text.find(surface, start + 1)
        if not jobs:
            return []

        async def check(idx: int, spans: list[tuple[int, int, str]]) -> list[Entity]:
            probs_list = await self._classify(self._state(sentences[idx]), [text[s:e] for s, e, _ in spans])
            found = []
            for (s, e, label), probs in zip(spans, probs_list):
                top, score = argmax(probs)
                ok = top == label
                trace[idx].children.append(
                    TraceNode(text[s:e], s, e, "propagate", top, score, probs, "entity" if ok else "rejected")
                )
                if ok:
                    found.append(Entity(text[s:e], label, s, e, score, "propagated", self._types_of(probs)))
            return found

        results = await asyncio.gather(*(check(i, spans) for i, spans in jobs.items()))
        return [e for group in results for e in group]


def resolve_overlaps(candidates: list[Entity], contain_margin: float) -> list[Entity]:
    """Prefer the longer window when it scores almost as well, then pick greedily without overlap."""
    kept = [
        c
        for c in candidates
        if not any(
            o is not c
            and o.start <= c.start
            and c.end <= o.end
            and (o.end - o.start) > (c.end - c.start)
            and o.score >= c.score - contain_margin
            for o in candidates
        )
    ]
    kept.sort(key=lambda c: (-c.score, -(c.end - c.start), c.start))
    chosen: list[Entity] = []
    for c in kept:
        if all(c.end <= o.start or c.start >= o.end for o in chosen):
            chosen.append(c)
    chosen.sort(key=lambda c: c.start)
    return chosen


def strip_article(text: str, ent: Entity) -> Entity:
    """English NER convention: 'the National Institutes of Health' -> 'National Institutes of Health'."""
    if ent.label != "person" and ent.text[:4].lower() == "the " and len(ent.text) > 4:
        start = ent.start + 4
        return replace(ent, text=text[start : ent.end], start=start)
    return ent


def _latin(text: str) -> bool:
    return all(ch.isascii() for ch in text)


def merge_adjacent(text: str, entities: list[Entity]) -> list[Entity]:
    """Re-join entities a delimiter split apart, e.g. 'Tim' + 'Cook' or '广东省 深圳市'."""
    merged: list[Entity] = []
    for ent in entities:
        if merged:
            prev = merged[-1]
            gap = text[prev.end : ent.start]
            same = prev.label == ent.label and prev.end <= ent.start
            both_latin = _latin(prev.text) and _latin(ent.text)
            joinable = (
                (both_latin and (gap.strip() == "" or (ent.label == "address" and gap.strip() == ",")))
                or (not both_latin and ent.label == "address" and gap != "" and gap.strip() == "")
            )
            if same and joinable:
                merged[-1] = Entity(
                    text[prev.start : ent.end], prev.label, prev.start, ent.end,
                    min(prev.score, ent.score), prev.source if prev.source == ent.source else "merged",
                )
                continue
        merged.append(ent)
    return merged
