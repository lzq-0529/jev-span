from jevspan.segmenter import (
    LEVEL_CLAUSE,
    LEVEL_ENCLOSURE,
    LEVEL_SPACE,
    split,
    split_finer,
    split_sentences,
    units,
)


def texts(segs):
    return [s.text for s in segs]


def test_sentences_cut_on_hard_punctuation_and_keep_offsets():
    text = "张三来了。李四走了！王五呢？\n赵六"
    segs = split_sentences(text)
    assert texts(segs) == ["张三来了", "李四走了", "王五呢", "赵六"]
    for s in segs:
        assert text[s.start : s.end] == s.text


def test_english_period_rules():
    text = "Dr. Smith works at Acme Inc. in Boston. Pi is 3.14 today."
    assert texts(split_sentences(text)) == ["Dr. Smith works at Acme Inc. in Boston", "Pi is 3.14 today"]


def test_clause_level_keeps_numbers_and_times_intact():
    text = "营业时间：10:00-22:00，价格1,299元"
    assert texts(split(text, 0, len(text), LEVEL_CLAUSE)) == ["营业时间", "10:00-22:00", "价格1,299元"]


def test_enclosures_are_a_finer_level_than_separators():
    text = "甲方：阿里巴巴（中国）有限公司"
    clause = split(text, 0, len(text), LEVEL_CLAUSE)
    assert texts(clause) == ["甲方", "阿里巴巴（中国）有限公司"]
    level, parts = split_finer(text, clause[1])
    assert level == LEVEL_ENCLOSURE
    assert texts(parts) == ["阿里巴巴", "中国", "有限公司"]


def test_space_level_only_cuts_around_cjk():
    text = "姓名 刘洋 单位 Goldman Sachs"
    parts = split(text, 0, len(text), LEVEL_SPACE)
    assert texts(parts) == ["姓名", "刘洋", "单位", "Goldman Sachs"]


def test_split_finer_returns_none_for_atomic_segment():
    text = "马云创办了阿里巴巴"
    (seg,) = split_sentences(text)
    assert split_finer(text, seg) is None


def test_units_mix_cjk_chars_and_latin_words():
    text = "在Amazon工作了5年"
    assert [text[s:e] for s, e in units(text, 0, len(text))] == ["在", "Amazon", "工", "作", "了", "5", "年"]


def test_punctuation_only_segments_are_dropped():
    text = "……——。！"
    assert split_sentences(text) == []
