import re

import pytest

from jevspan.recognizer import (
    BOUNDARY_CRITERIA,
    MIXED,
    NONE,
    NONE_OPTION,
    PARTIAL,
    SPLIT,
    WHOLE,
    Entity,
    Recognizer,
    merge_adjacent,
    resolve_overlaps,
)
from jevspan.schema import Schema

GAZETTEER = {
    "张伟": "person",
    "王建国": "person",
    "马云": "person",
    "清华大学": "organization",
    "阿里巴巴": "organization",
    "阿里巴巴（中国）有限公司": "organization",
    "北京市海淀区": "address",
}
FRAG = re.compile(r"「(.+?)」")
TITLES = {"人名": "person", "机构": "organization", "地址": "address"}


class FakeJev:
    """Scores a fragment by looking it up in a tiny gazetteer, like a perfectly calibrated Jev."""

    def __init__(self):
        self.calls = []

    async def choose_many(self, state, instructions, criteria):
        self.calls.append((state, list(instructions), set(criteria)))
        return [self._answer(ins, criteria) for ins in instructions]

    def _answer(self, instruction, criteria):
        if NONE_OPTION in criteria:
            return self._nominate(instruction, criteria)
        frag = FRAG.search(instruction).group(1)
        if "这一处" in instruction:
            best = next((k for k in criteria if k in GAZETTEER), frag)
            return {k: float(k == best) for k in criteria}
        if "最准确地属于" in instruction:
            if frag not in GAZETTEER:
                return {k: 1.0 / len(criteria) for k in criteria}
            return {k: float(k == GAZETTEER[frag]) for k in criteria}
        return self._score(frag, criteria)

    def _nominate(self, instruction, criteria):
        title = re.search(r"完整的「(.+?)」", instruction)
        wanted = {TITLES[title.group(1)]} if title else set(TITLES.values())
        probs = {k: 0.0 for k in criteria}
        hits = [k for k in criteria if GAZETTEER.get(k) in wanted]
        probs[hits[0] if hits else NONE_OPTION] = 1.0
        return probs

    def _score(self, frag, criteria):
        if criteria.keys() == BOUNDARY_CRITERIA.keys():
            label = WHOLE if frag in GAZETTEER else SPLIT
        elif frag in GAZETTEER:
            label = GAZETTEER[frag]
        elif any(name in frag for name in GAZETTEER):
            label = MIXED
        elif any(frag in name for name in GAZETTEER):
            label = PARTIAL
        else:
            label = NONE
        probs = {k: 0.0 for k in criteria}
        probs[label] = 1.0
        return probs


LEGACY = dict(hierarchy=True, prune_windows=False, boundary_refine=False, retype=False, nominate_group_size=1)


def pairs(result):
    return [(e.text, e.label) for e in result.entities]


@pytest.fixture
def jev():
    return FakeJev()


async def test_clause_entities_come_straight_from_punctuation(jev):
    result = await Recognizer(jev, **LEGACY).recognize("联系人：王建国，地址：北京市海淀区。")
    assert pairs(result) == [("王建国", "person"), ("北京市海淀区", "address")]
    assert all(e.source == "segment" for e in result.entities)


async def test_mixed_clause_falls_through_to_sliding_window(jev):
    result = await Recognizer(jev, **LEGACY).recognize("马云创办了阿里巴巴。")
    assert pairs(result) == [("马云", "person"), ("阿里巴巴", "organization")]
    assert {e.source for e in result.entities} == {"window"}
    assert result.trace[0].decision == "window"


async def test_no_entities_yields_nothing(jev):
    result = await Recognizer(jev).recognize("今天天气不错，我们下午开会。")
    assert result.entities == []


async def test_verification_keeps_name_with_internal_brackets(jev):
    result = await Recognizer(jev, **LEGACY).recognize("甲方：阿里巴巴（中国）有限公司。")
    assert pairs(result) == [("阿里巴巴（中国）有限公司", "organization")]
    clause = result.trace[0].children[1]
    assert clause.decision.startswith("entity (whole")


async def test_offsets_point_into_original_text(jev):
    text = "据报道，张伟在清华大学演讲。"
    result = await Recognizer(jev).recognize(text)
    assert pairs(result) == [("张伟", "person"), ("清华大学", "organization")]
    for e in result.entities:
        assert text[e.start : e.end] == e.text


async def test_sentence_is_sent_as_context(jev):
    await Recognizer(jev).recognize("张伟在清华大学演讲。")
    assert all(state == "张伟在清华大学演讲" for state, _, _ in jev.calls)
    jev.calls.clear()
    await Recognizer(jev, use_context=False).recognize("张伟在清华大学演讲。")
    assert all(state == "" for state, _, _ in jev.calls)


async def test_without_window_mixed_segment_uses_fallback(jev):
    result = await Recognizer(jev, **{**LEGACY, "ngram": False}).recognize("马云创办了阿里巴巴。")
    assert result.entities == []
    assert result.trace[0].decision == "fallback"


async def test_scan_mode_finds_the_same_entities(jev):
    result = await Recognizer(jev, **{**LEGACY, "refine": "scan"}).recognize("马云创办了阿里巴巴。")
    assert pairs(result) == [("马云", "person"), ("阿里巴巴", "organization")]


async def test_choice_mode_asks_far_fewer_questions_than_scan():
    scan, choice = FakeJev(), FakeJev()
    text = "马云创办了阿里巴巴。"
    await Recognizer(scan, **{**LEGACY, "refine": "scan", "speculative": False}).recognize(text)
    await Recognizer(choice, **{**LEGACY, "refine": "choice", "speculative": False}).recognize(text)
    count = lambda j: sum(len(ins) for _, ins, _ in j.calls)
    assert count(choice) < count(scan) / 3


async def test_propagation_recovers_a_mention_the_window_stage_missed():
    class ForgetfulJev(FakeJev):
        async def choose_many(self, state, instructions, criteria):
            if NONE_OPTION in criteria and state.startswith("后来"):
                return [{**{k: 0.0 for k in criteria}, NONE_OPTION: 1.0} for _ in instructions]
            return await super().choose_many(state, instructions, criteria)

    text = "张伟来了。后来张伟又走了。"
    without = await Recognizer(ForgetfulJev(), **LEGACY, propagate=False).recognize(text)
    assert [(e.text, e.start) for e in without.entities] == [("张伟", 0)]
    result = await Recognizer(ForgetfulJev(), **LEGACY).recognize(text)
    assert [(e.text, e.start, e.source) for e in result.entities] == [("张伟", 0, "window"), ("张伟", 7, "propagated")]


async def test_zero_shot_schema_drives_labels():
    class DrugJev(FakeJev):
        def _score(self, frag, criteria):
            probs = {k: 0.0 for k in criteria}
            probs["drug" if frag == "阿莫西林" else (MIXED if "阿莫西林" in frag else NONE)] = 1.0
            return probs

        def _nominate(self, instruction, criteria):
            probs = {k: 0.0 for k in criteria}
            probs["阿莫西林" if "阿莫西林" in criteria else NONE_OPTION] = 1.0
            return probs

    schema = Schema.from_dict({"drug": {"title": "药品", "description": "药物名称", "examples": ["布洛芬"]}})
    jev = DrugJev()
    result = await Recognizer(jev, schema=schema).recognize("医生开了阿莫西林。")
    assert pairs(result) == [("阿莫西林", "drug")]
    criteria_seen = set().union(*(c for _, _, c in jev.calls))
    assert "drug" in criteria_seen and "person" not in criteria_seen


def test_schema_parsing_and_criteria():
    schema = Schema.from_dict(
        {"entities": {"drug": {"title": "药品", "description": "药物名称", "examples": ["布洛芬"], "counter_examples": ["维生素"]}},
         }
    )
    assert schema.names == ["drug"]
    assert schema.criteria()["drug"] == "药品：药物名称，例如 布洛芬（不包括 维生素）"
    assert Schema.from_dict({"brand": "品牌名称"}).get("brand").description == "品牌名称"
    assert Schema.from_dict(schema.to_dict()) == schema


async def test_default_pipeline_finds_entities_without_segment_classification(jev):
    result = await Recognizer(jev).recognize("据报道，张伟在清华大学演讲。联系人：王建国。")
    assert pairs(result) == [("张伟", "person"), ("清华大学", "organization"), ("王建国", "person")]
    asked = [ins for _, batch, _ in jev.calls for ins in batch]
    assert not any(ins.startswith("上文中的片段「据报道，张伟在清华大学演讲") for ins in asked)


async def test_boundary_refinement_trims_extra_words(jev):
    class GreedyJev(FakeJev):
        def _nominate(self, instruction, criteria):
            probs = {k: 0.0 for k in criteria}
            probs["在清华大学" if "在清华大学" in criteria else NONE_OPTION] = 1.0
            return probs

        def _score(self, frag, criteria):
            if frag == "在清华大学":
                return {k: float(k == "organization") for k in criteria}
            return super()._score(frag, criteria)

    result = await Recognizer(GreedyJev()).recognize("张伟在清华大学演讲。")
    assert ("清华大学", "organization") in pairs(result)


def test_window_pruning_skips_function_word_edges(jev):
    from jevspan.segmenter import split_sentences

    text = "and the Liberal Party won"
    seg = split_sentences(text)[0]
    frags = {text[s:e] for s, e in Recognizer(jev).window_spans(text, seg)}
    assert "the Liberal Party" in frags
    assert "and the Liberal Party" not in frags
    assert "Liberal Party won" in frags and "the" not in frags


def test_reserved_labels_are_rejected(jev):
    with pytest.raises(ValueError):
        Recognizer(jev, entity_types={"none": "x"})


def test_resolve_overlaps_prefers_longer_when_scores_are_close():
    cands = [
        Entity("北京市", "address", 0, 3, 0.97, "window"),
        Entity("北京市海淀区", "address", 0, 6, 0.95, "window"),
        Entity("京市海", "address", 1, 4, 0.99, "window"),
    ]
    chosen = resolve_overlaps(cands, contain_margin=0.15)
    assert [(c.text, c.start) for c in chosen] == [("北京市海淀区", 0)]


def test_merge_adjacent_latin_and_spaced_addresses():
    text = "Austin, Texas and 广东省 深圳市"
    ents = [
        Entity("Austin", "address", 0, 6, 0.9, "segment"),
        Entity("Texas", "address", 8, 13, 0.9, "segment"),
        Entity("广东省", "address", 18, 21, 0.9, "segment"),
        Entity("深圳市", "address", 22, 25, 0.9, "segment"),
    ]
    merged = merge_adjacent(text, ents)
    assert [e.text for e in merged] == ["Austin, Texas", "广东省 深圳市"]
